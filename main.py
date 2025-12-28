import os
import traceback
from fastapi import FastAPI, Request, Form
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
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    # モデル名を最新の安定版に指定
    model = genai.GenerativeModel('gemini-1.5-flash')
    return supabase, model, tavily

# UIテンプレート（Pocket風）
def get_html_layout(content: str, active_tab: str):
    home_style = "border-bottom: 3px solid #2196f3; font-weight: bold; color: #2196f3;" if active_tab == "home" else ""
    archive_style = "border-bottom: 3px solid #2196f3; font-weight: bold; color: #2196f3;" if active_tab == "archive" else ""
    return f"""
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; background: #f4f4f7; margin: 0; padding-bottom: 30px; }}
            .nav {{ background: white; display: flex; justify-content: space-around; padding: 15px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); position: sticky; top: 0; }}
            .nav a {{ text-decoration: none; color: #666; font-size: 0.9em; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 0 15px; }}
            .card {{ background: white; border-radius: 12px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
            textarea {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin: 10px 0; box-sizing: border-box; }}
            .collect-btn {{ width: 100%; background: #2196f3; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer; }}
            .article-link {{ display: block; font-weight: bold; color: #1a73e8; text-decoration: none; margin-bottom: 5px; }}
            .reason {{ font-size: 0.8em; color: #666; font-style: italic; }}
        </style></head>
        <body>
            <div class="nav"><a href="/" style="{home_style}">マイリスト</a><a href="/archived" style="{archive_style}">アーカイブ</a></div>
            <div class="container">{content}</div>
        </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def index():
    supabase, model, _ = initialize_clients()
    res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    articles = res.data or []
    
    summary = "記事を読み込んで要約します..."
    if articles:
        try:
            titles = [a.get('title', '無題') for a in articles[:5]]
            summary_res = model.generate_content("以下を3行でまとめて:\n" + "\n".join(titles))
            summary = summary_res.text
        except: summary = "要約を生成できませんでした。"

    items_html = f"""
    <div class="card">
        <h3 style="margin-top:0;">🤖 AI要約</h3>
        <p style="font-size:0.9em; border-left:4px solid #2196f3; padding-left:10px;">{summary.replace('\n', '<br>')}</p>
        <hr style="border:0; border-top:1px solid #eee; margin:20px 0;">
        <form action="/ai-collect" method="post">
            <textarea name="urls" rows="2" placeholder="URLを貼り付け（空でもOK）"></textarea>
            <button type="submit" class="collect-btn">AIにお任せ収集を実行</button>
        </form>
    </div>
    """
    for a in articles:
        items_html += f"""
        <div class="card">
            <a href="{a.get('url', '#')}" target="_blank" class="article-link">{a.get('title', '無題')}</a>
            <span class="reason">💡 {a.get('ai_reason', 'AIおすすめ')}</span>
        </div>
        """
    return get_html_layout(items_html, "home")

# AIサーチ実行
@app.post("/ai-collect")
async def ai_collect(urls: str = Form(""), count: int = Form(5)):
    try:
        supabase, model, tavily = initialize_clients()
        
        # 1. 傾向分析
        res = supabase.table("articles").select("title").order("created_at", desc=True).limit(5).execute()
        pref = ",".join([r['title'] for r in res.data]) if res.data else "最新ニュース"
        
        # 2. クエリ作成
        query_res = model.generate_content(f"関心:{pref} URL:{urls} に基づく日本語検索クエリを1つ作って")
        search_results = tavily.search(query=query_res.text, max_results=count)
        
        # 3. 保存
        for item in search_results['results']:
            reason = model.generate_content(f"『{item['title']}』を選んだ理由を1行で")
            supabase.table("articles").insert({
                "title": item['title'], 
                "url": item['url'], 
                "ai_reason": reason.text.strip(), 
                "is_archived": False
            }).execute()
            
        return RedirectResponse(url="/", status_code=303)
    except Exception:
        # エラーの詳細をブラウザに表示する
        return HTMLResponse(content=f"<h3>エラー発生</h3><pre>{traceback.format_exc()}</pre>")