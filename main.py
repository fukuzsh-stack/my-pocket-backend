import os
from typing import List, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import google.generativeai as genai
from tavily import TavilyClient
from supabase import create_client, Client

# --- 設定（Renderの環境変数から読み込む） ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# クライアント初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()

async def get_user_preference():
    try:
        res = supabase.table("articles").select("title").order("created_at", desc=True).limit(20).execute()
        if not res.data: return "最新のトレンド"
        titles = [r['title'] for r in res.data]
        prompt = f"以下のタイトルから興味関心を3つ抽出して: {', '.join(titles)}"
        response = model.generate_content(prompt)
        return response.text
    except: return "最新ニュース"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    articles = supabase.table("articles").select("*").order("created_at", desc=True).execute().data
    summary = "記事を保存するとAIが要約します。"
    if articles and len(articles) > 0:
        top_titles = [a['title'] for a in articles[:5]]
        summary_res = model.generate_content("以下を3行でまとめて:\n" + "\n".join(top_titles))
        summary = summary_res.text

    html_content = f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; background: #f0f2f5; padding: 15px; }}
                .card {{ background: white; border-radius: 10px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .summary {{ background: #e3f2fd; padding: 10px; border-left: 4px solid #2196f3; font-size: 0.9em; }}
                textarea {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }}
                button {{ background: #2196f3; color: white; border: none; padding: 12px; width: 100%; border-radius: 5px; font-weight: bold; }}
                .item {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 10px; display: block; text-decoration: none; color: #333; }}
                .reason {{ font-size: 0.8em; color: #666; font-style: italic; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h3>🤖 今日のAI要約</h3>
                <div class="summary">{summary.replace('\n', '<br>')}</div>
                <hr>
                <form action="/ai-collect" method="post">
                    <textarea name="urls" rows="3" placeholder="参考URL（複数可）"></textarea>
                    検索件数: <input type="number" name="count" value="5" min="1" max="10">
                    <button type="submit">AIにお任せ収集</button>
                </form>
            </div>
            {"".join([f'<a href="{a["url"]}" class="item"><b>{a["title"]}</b><br><span class="reason">💡 {a.get("ai_reason", "")}</span></a>' for a in articles])}
        </body>
    </html>
    """
    return html_content

@app.post("/ai-collect")
async def ai_collect(urls: str = Form(""), count: int = Form(5)):
    pref = await get_user_preference()
    query_res = model.generate_content(f"関心:{pref} URL:{urls} に基づく検索クエリを1つ作って")
    search_results = tavily.search(query=query_res.text, max_results=count)
    for item in search_results['results']:
        reason = model.generate_content(f"『{item['title']}』を『{pref}』に基づいて選んだ理由を1行で")
        supabase.table("articles").insert({{"title": item['title'], "url": item['url'], "ai_reason": reason.text, "is_archived": False}}).execute()
    return HTMLResponse("<script>alert('収集完了'); window.location.href='/';</script>")