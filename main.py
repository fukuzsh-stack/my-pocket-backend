import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import google.generativeai as genai
from tavily import TavilyClient
from supabase import create_client, Client

# --- 設定（Renderの環境変数から読み込む） ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = FastAPI()

def initialize_clients():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    # 修正版モデル指定：404エラー対策済
    model = genai.GenerativeModel('gemini-1.5-flash')
    return supabase, model, tavily

# --- UIテンプレート ---
def get_html_layout(content: str, active_tab: str):
    home_style = "border-bottom: 3px solid #2196f3; font-weight: bold; color: #2196f3;" if active_tab == "home" else ""
    archive_style = "border-bottom: 3px solid #2196f3; font-weight: bold; color: #2196f3;" if active_tab == "archive" else ""
    
    return f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, sans-serif; background: #f4f4f7; margin: 0; padding-bottom: 50px; }}
                .nav {{ background: white; display: flex; justify-content: space-around; padding: 15px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); position: sticky; top: 0; z-index: 100; }}
                .nav a {{ text-decoration: none; color: #666; padding: 5px 20px; font-size: 0.9em; }}
                .container {{ max-width: 600px; margin: 20px auto; padding: 0 15px; }}
                .card {{ background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
                .summary-box {{ background: #e3f2fd; padding: 15px; border-radius: 8px; font-size: 0.9em; line-height: 1.6; margin-bottom: 20px; border-left: 4px solid #2196f3; color: #333; }}
                .article-title {{ display: block; font-weight: bold; color: #1a1a1a; text-decoration: none; font-size: 1.05em; margin-bottom: 5px; }}
                .ai-reason {{ font-size: 0.8em; color: #777; font-style: italic; margin-bottom: 10px; display: block; }}
                .btn-group {{ display: flex; gap: 10px; }}
                .btn {{ border: none; padding: 8px 15px; border-radius: 6px; font-size: 0.8em; cursor: pointer; font-weight: bold; }}
                .btn-archive {{ background: #e8f0fe; color: #1967d2; }}
                .btn-delete {{ background: #fce8e6; color: #d93025; }}
                .btn-restore {{ background: #e6ffed; color: #1a7f37; }}
                textarea {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin: 10px 0; box-sizing: border-box; font-size: 14px; }}
                .collect-btn {{ width: 100%; background: #2196f3; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="nav">
                <a href="/" style="{home_style}">マイリスト</a>
                <a href="/archived" style="{archive_style}">アーカイブ</a>
            </div>
            <div class="container">{content}</div>
        </body>
    </html>
    """

# --- マイリスト（未読記事） ---
@app.get("/", response_class=HTMLResponse)
async def index():
    supabase, model, _ = initialize_clients()
    res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    articles = res.data or []
    
    summary_html = ""
    if articles:
        try:
            titles = [a.get('title', '無題') for a in articles[:5]]
            summary_res = model.generate_content("以下を3行でまとめて:\n" + "\n".join(titles))
            summary_html = f'<div class="summary-box"><b>🤖 AIの要約</b><br>{summary_res.text.replace("\n", "<br>")}</div>'
        except:
            summary_html = '<div class="summary-box">AI要約を生成中です...</div>'

    items_html = f"""
    <div class="card">
        <h3>🔍 AIサーチ</h3>
        <form action="/ai-collect" method="post">
            <textarea name="urls" rows="2" placeholder="参考にしたいURLを貼り付け（空欄でもOK）"></textarea>
            <button type="submit" class="collect-btn">AIにお任せ収集を実行</button>
        </form>
    </div>
    {summary_html}
    """
    
    for a in articles:
        items_html += f"""
        <div class="card">
            <a href="{a.get('url', '#')}" class="article-title" target="_blank">{a.get('title', '無題')}</a>
            <span class="ai-reason">💡 {a.get('ai_reason', 'AIおすすめ')}</span>
            <div class="btn-group">
                <form action="/archive/{a['id']}" method="post"><button class="btn btn-archive">アーカイブ</button></form>
                <form action="/delete/{a['id']}" method="post" onsubmit="return confirm('削除しますか？')"><button class="btn btn-delete">削除</button></form>
            </div>
        </div>
        """
    return get_html_layout(items_html, "home")

# --- アーカイブページ ---
@app.get("/archived", response_class=HTMLResponse)
async def archived_page():
    supabase, _, _ = initialize_clients()
    res = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    articles = res.data or []
    
    items_html = "<h3>アーカイブ済み</h3>"
    if not articles:
        items_html += "<p style='color:#999;'>アーカイブされた記事はありません。</p>"
        
    for a in articles:
        items_html += f"""
        <div class="card" style="opacity: 0.7;">
            <a href="{a.get('url', '#')}" class="article-title" target="_blank">{a.get('title', '無題')}</a>
            <div class="btn-group">
                <form action="/unarchive/{a['id']}" method="post"><button class="btn btn-restore">リストに戻す</button></form>
                <form action="/delete/{a['id']}" method="post" onsubmit="return confirm('完全に削除しますか？')"><button class="btn btn-delete">削除</button></form>
            </div>
        </div>
        """
    return get_html_layout(items_html, "archive")

# --- 操作用 ---
@app.post("/archive/{{article_id}}")
async def archive_article(article_id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").update({{"is_archived": True}}).eq("id", article_id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/unarchive/{{article_id}}")
async def unarchive_article(article_id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").update({{"is_archived": False}}).eq("id", article_id).execute()
    return RedirectResponse(url="/archived", status_code=303)

@app.post("/delete/{{article_id}}")
async def delete_article(article_id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").delete().eq("id", article_id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/ai-collect")
async def ai_collect(urls: str = Form(""), count: int = Form(5)):
    supabase, model, tavily = initialize_clients()
    res = supabase.table("articles").select("title").order("created_at", desc=True).limit(10).execute()
    pref = ",".join([r['title'] for r in res.data]) if res.data else "最新ニュース"
    
    query_res = model.generate_content(f"関心:{pref} URL:{urls} に基づく日本語検索クエリを1つ作って")
    search_results = tavily.search(query=query_res.text, max_results=count)
    
    for item in search_results['results']:
        reason = model.generate_content(f"『{item['title']}』を選んだ理由を1行で")
        supabase.table("articles").insert({{
            "title": item['title'], "url": item['url'], 
            "ai_reason": reason.text.strip(), "is_archived": False
        }}).execute()
    return RedirectResponse(url="/", status_code=303)