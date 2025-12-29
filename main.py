import os
import traceback
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import google.generativeai as genai
from tavily import TavilyClient
from supabase import create_client, Client
from newspaper import Article, Config

# --- 設定（環境変数） ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = FastAPI()

def initialize_clients():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    return supabase, model, tavily

# --- 【修正版】ショートカットからの保存窓口 ---
@app.get("/extract")
async def extract_and_save(url: str):
    supabase, _, _ = initialize_clients()
    try:
        config = Config()
        # iPhoneからのアクセスであることを明示し、タイムアウトを調整
        config.browser_user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        config.request_timeout = 10
        
        article = Article(url, language='ja', config=config)
        article.download()
        article.parse()
        
        data = {
            "title": article.title or url,
            "url": url,
            "image_url": article.top_image or "",
            "is_archived": False,
            "ai_reason": "Safariから保存"
        }
        supabase.table("articles").insert(data).execute()
        
        # iPhoneが解析しやすいよう、以前成功していた時と同じJSON形式で返す
        return {"status": "success", "title": article.title}
        
    except Exception as e:
        # 失敗してもURLだけは保存する（以前の安定ロジック）
        try:
            supabase.table("articles").insert({
                "title": url, 
                "url": url, 
                "is_archived": False, 
                "ai_reason": "保存エラー(URLのみ)"
            }).execute()
        except:
            pass
        return {"status": "partial_success", "error": str(e)}

# --- UIレイアウト ---
def get_html_layout(content: str, active_tab: str):
    home_style = "border-bottom: 3px solid #ef4056; font-weight: bold; color: #ef4056;" if active_tab == "home" else ""
    archive_style = "border-bottom: 3px solid #ef4056; font-weight: bold; color: #ef4056;" if active_tab == "archive" else ""
    return f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, sans-serif; background: #f9f9f9; margin: 0; padding-bottom: 60px; }}
                .nav {{ background: white; display: flex; justify-content: space-around; padding: 15px 0; position: sticky; top: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); z-index: 100; }}
                .nav a {{ text-decoration: none; color: #999; font-size: 13px; font-weight: bold; }}
                .container {{ max-width: 600px; margin: 20px auto; padding: 0 15px; }}
                .card {{ background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px; border-bottom: 1px solid #eee; }}
                .btn-main {{ background: #ef4056; color: white; width: 100%; padding: 12px; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }}
                .article-title {{ display: block; font-weight: bold; color: #333; text-decoration: none; font-size: 15px; margin-bottom: 5px; }}
                .row-img {{ width: 50px; height: 50px; border-radius: 4px; background-size: cover; background-position: center; flex-shrink: 0; background-color: #f0f0f0; }}
                .article-row {{ display: flex; gap: 12px; align-items: flex-start; }}
            </style>
        </head>
        <body>
            <div class="nav">
                <a href="/" style="{home_style}">MY LIST</a>
                <a href="/archived" style="{archive_style}">ARCHIVE</a>
            </div>
            <div class="container">{content}</div>
        </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def index():
    supabase, model, _ = initialize_clients()
    res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    articles = res.data or []
    
    # AI要約
    summary = "記事を読み込んで要約を作成中..."
    if articles:
        try:
            titles = [a.get('title', '無題') for a in articles[:5]]
            summary_res = model.generate_content("以下を3行で箇条書きでまとめて:\n" + "\n".join(titles))
            summary = summary_res.text
        except:
            summary = "要約を生成できませんでした。"

    content = f"""
    <div class="card">
        <h3 style="margin:0 0 10px; color:#ef4056;">🤖 AI要約 (最新5件)</h3>
        <p style="font-size:13px; line-height:1.6; color:#555;">{summary.replace('\\n', '<br>')}</p>
        <form action="/ai-collect" method="post" style="border-top:1px solid #eee; padding-top:15px;">
            <textarea name="urls" rows="2" style="width:100%; padding:10px; margin-bottom:10px; border:1px solid #ddd; border-radius:4px;" placeholder="URLやキーワード（任意）"></textarea>
            <div style="font-size:12px; margin-bottom:10px;">
                取得本数: <select name="count"><option value="1">1本</option><option value="3">3本</option><option value="5" selected>5本</option></select>
            </div>
            <button type="submit" class="btn-main">AIサーチを実行</button>
        </form>
    </div>
    """
    for a in articles:
        img_url = a.get('image_url')
        img_tag = f'<div class="row-img" style="background-image: url(\'{img_url}\')"></div>' if img_url else '<div class="row-img"></div>'
        
        content += f"""
        <div class="card">
            <div class="article-row">
                {img_tag}
                <div style="flex:1;">
                    <a href="{a.get('url', '#')}" target="_blank" class="article-title">{a.get('title', '無題')}</a>
                    <div style="font-size:11px; color:#aaa;">{a.get('ai_reason', '')}</div>
                </div>
            </div>
            <div style="display:flex; gap:20px; margin-top:10px; border-top:1px solid #f9f9f9; padding-top:10px;">
                <form action="/archive/{a['id']}" method="post"><button style="color:#ef4056; background:none; border:none; font-weight:bold; cursor:pointer;">Done</button></form>
                <form action="/delete/{a['id']}" method="post"><button style="color:#ccc; background:none; border:none; cursor:pointer;">削除</button></form>
            </div>
        </div>
        """
    return get_html_layout(content, "home")

# --- アクション ---
@app.post("/archive/{{id}}")
async def archive(id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").update({{"is_archived": True}}).eq("id", id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{{id}}")
async def delete(id: int):
    supabase, _, _ = initialize_clients()
    supabase.table("articles").delete().eq("id", id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/ai-collect")
async def ai_collect(urls: str = Form(""), count: int = Form(5)):
    try:
        supabase, model, tavily = initialize_clients()
        res = supabase.table("articles").select("title").order("created_at", desc=True).limit(5).execute()
        pref = ",".join([r['title'] for r in res.data]) if res.data else "最新ニュース"
        query_res = model.generate_content(f"関心:{pref} {urls} に基づく最新情報の検索クエリを1つ日本語で作って。余計な解説は不要")
        search_results = tavily.search(query=query_res.text, max_results=count)
        for item in search_results['results']:
            supabase.table("articles").insert({
                "title": item['title'], 
                "url": item['url'], 
                "is_archived": False, 
                "ai_reason": "AIサーチ"
            }).execute()
        return RedirectResponse(url="/", status_code=303)
    except:
        return RedirectResponse(url="/", status_code=303)

@app.get("/archived", response_class=HTMLResponse)
async def archived_page():
    supabase, _, _ = initialize_clients()
    res = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    articles = res.data or []
    content = "<h3>ARCHIVE</h3>"
    for a in articles:
        content += f'<div class="card"><a href="{a["url"]}" target="_blank" class="article-title">{a["title"]}</a></div>'
    return get_html_layout(content, "archive")