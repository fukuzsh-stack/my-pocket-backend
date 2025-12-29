import os
import traceback
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import google.generativeai as genai
from tavily import TavilyClient
from supabase import create_client, Client

# --- 設定（環境変数） ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = FastAPI()

def initialize_clients():
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        genai.configure(api_key=GEMINI_API_KEY)
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        # 404エラー対策：ライブラリが古いAPIを探しに行くのを防ぐため、モデル名のみを明示的に指定
        model = genai.GenerativeModel(model_name='gemini-1.5-flash')
        return supabase, model, tavily
    except Exception as e:
        print(f"DEBUG: 初期化失敗 - {str(e)}")
        raise e

# UIテンプレート（Pocket風）
def get_html_layout(content: str, active_tab: str):
    home_style = "border-bottom: 3px solid #007aff; font-weight: bold; color: #007aff;" if active_tab == "home" else ""
    archive_style = "border-bottom: 3px solid #007aff; font-weight: bold; color: #007aff;" if active_tab == "archive" else ""
    return f"""
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #f2f2f7; margin: 0; padding-bottom: 50px; }}
            .nav {{ background: white; display: flex; justify-content: space-around; padding: 15px 0; position: sticky; top: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); z-index: 100; }}
            .nav a {{ text-decoration: none; color: #8e8e93; font-size: 14px; padding: 5px 10px; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 0 15px; }}
            .card {{ background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
            .ai-summary {{ background: #f0f7ff; border-left: 4px solid #007aff; padding: 12px; font-size: 14px; margin-bottom: 15px; border-radius: 4px; color: #333; }}
            .article-title {{ display: block; font-weight: 600; color: #1c1c1e; text-decoration: none; margin-bottom: 4px; font-size: 17px; line-height: 1.4; }}
            .ai-reason {{ font-size: 12px; color: #8e8e93; display: block; margin-bottom: 12px; }}
            .btn-main {{ background: #007aff; color: white; width: 100%; padding: 12px; border: none; border-radius: 8px; font-weight: 600; margin-top: 10px; cursor: pointer; }}
            textarea, select {{ width: 100%; border: 1px solid #d1d1d6; border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 14px; box-sizing: border-box; }}
            .actions {{ display: flex; gap: 12px; }}
            .btn-action {{ border: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; }}
        </style></head>
        <body>
            <div class="nav"><a href="/" style="{home_style}">マイリスト</a><a href="/archived" style="{archive_style}">アーカイブ</a></div>
            <div class="container">{content}</div>
        </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        supabase, model, _ = initialize_clients()
        res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
        articles = res.data or []
        
        summary = "AI要約を作成中..."
        if articles:
            try:
                titles = [a.get('title', '無題') for a in articles[:5]]
                summary_res = model.generate_content("以下を3行でまとめて:\n" + "\n".join(titles))
                summary = summary_res.text
            except: summary = "要約を生成できませんでした。"

        content = f"""
        <div class="card">
            <h3 style="margin:0 0 10px;">🤖 AI要約</h3>
            <div class="ai-summary">{summary.replace('\n', '<br>')}</div>
            <form action="/ai-collect" method="post" style="border-top: 1px solid #eee; padding-top: 15px;">
                <label style="font-size:13px; color:#333; font-weight:600;">🔍 AIにお任せ収集</label>
                <textarea name="urls" rows="2" placeholder="URL（任意）"></textarea>
                <div style="font-size:13px; color:#666;">
                    取得記事数: 
                    <select name="count" style="width:auto; display:inline-block;">
                        <option value="auto">AIにお任せ</option>
                        <option value="1">1本</option>
                        <option value="3">3本</option>
                        <option value="5" selected>5本</option>
                        <option value="10">10本</option>
                    </select>
                </div>
                <button type="submit" class="btn-main">AIサーチを実行</button>
            </form>
        </div>
        """
        for a in articles:
            content += f"""
            <div class="card">
                <a href="{a.get('url', '#')}" target="_blank" class="article-title">{a.get('title', '無題')}</a>
                <span class="ai-reason">💡 {a.get('ai_reason', '保存済み')}</span>
                <div class="actions">
                    <form action="/archive/{a['id']}" method="post" style="margin:0;"><button class="btn-action" style="background:#e5e5ea; color:#007aff;">アーカイブ</button></form>
                    <form action="/delete/{a['id']}" method="post" style="margin:0;" onsubmit="return confirm('削除しますか？')"><button class="btn-action" style="background:#ffe5e5; color:#ff3b30;">削除</button></form>
                </div>
            </div>
            """
        return get_html_layout(content, "home")
    except Exception as e:
        return f"システムエラー: {e}"

# --- 【復活】Safariショートカット用窓口（/extract） ---
@app.get("/extract")
async def extract_url(url: str = Query(...)):
    supabase, model, _ = initialize_clients()
    try:
        # Geminiでタイトルを自動生成（競馬サイトなどに対応）
        ai_res = model.generate_content(f"このURLから記事タイトルを1つ抽出して答えて: {url}")
        title = ai_res.text.strip().split('\n')[0][:50]
        supabase.table("articles").insert({
            "title": title, "url": url, "ai_reason": "Safariから保存", "is_archived": False
        }).execute()
        return HTMLResponse("<html><body onload='window.close()'>保存完了</body></html>")
    except:
        supabase.table("articles").insert({"title": "保存済み記事", "url": url, "is_archived": False}).execute()
        return RedirectResponse(url="/", status_code=303)

@app.post("/archive/{article_id}")
async def archive_article(article_id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").update({"is_archived": True}).eq("id", article_id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/unarchive/{article_id}")
async def unarchive_article(article_id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").update({"is_archived": False}).eq("id", article_id).execute()
    return RedirectResponse(url="/archived", status_code=303)

@app.post("/delete/{article_id}")
async def delete_article(article_id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").delete().eq("id", article_id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/ai-collect")
async def ai_collect(urls: str = Form(""), count: str = Form("5")):
    try:
        supabase, model, tavily = initialize_clients()
        res = supabase.table("articles").select("title").order("created_at", desc=True).limit(5).execute()
        pref = ",".join([r['title'] for r in res.data]) if res.data else "競馬 予想 AI"

        search_count = 5 if count == "auto" else int(count)
        query_res = model.generate_content(f"関心:{pref} に基づく最新記事の日本語検索クエリを1つ作って")
        search_results = tavily.search(query=query_res.text + " " + urls, max_results=search_count)
        
        for item in search_results['results']:
            reason = model.generate_content(f"『{item['title']}』を選んだ理由を15文字以内で")
            supabase.table("articles").insert({
                "title": item['title'], "url": item['url'], "ai_reason": reason.text.strip(), "is_archived": False
            }).execute()
        return RedirectResponse(url="/", status_code=303)
    except Exception:
        return HTMLResponse(content=f"<h3>AIサーチエラー</h3><pre>{traceback.format_exc()}</pre>")

@app.get("/archived", response_class=HTMLResponse)
async def archived_page():
    supabase, _, _ = initialize_clients()
    res = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    articles = res.data or []
    items_html = "<h3>アーカイブ済み</h3>"
    for a in articles:
        items_html += f"""
        <div class="card" style="opacity: 0.8;">
            <a href="{a.get('url', '#')}" target="_blank" class="article-title">{a.get('title', '無題')}</a>
            <form action="/unarchive/{a['id']}" method="post"><button class="btn-action" style="background:#e1f5fe; color:#0288d1;">戻す</button></form>
        </div>
        """
    return get_html_layout(items_html, "archive")