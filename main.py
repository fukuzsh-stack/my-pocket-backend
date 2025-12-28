import os
import asyncio
from typing import List, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import google.generativeai as genai
from tavily import TavilyClient
from supabase import create_client, Client
from newspaper import Article

# --- 設定 ---
SUPABASE_URL = "https://vdpxribywidmbvwnmplu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkcHhyaWJ5d2lkbWJ2d25tcGx1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4MTkyODgsImV4cCI6MjA4MjM5NTI4OH0.FQgAMLKW7AxPgK-pPO0IC7lrrCTOtzcJ9DNlbqH3pUk"
GEMINI_API_KEY = "AIzaSyAXFni7owoiD2kjwPPvdKej55Tki70vrKw"
TAVILY_API_KEY = "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"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()

# --- プロンプト・関数 ---
async def get_user_preference():
    """過去の保存記事から傾向を分析する"""
    res = supabase.table("articles").select("title").order("created_at", desc=True).limit(20).execute()
    titles = [r['title'] for r in res.data]
    prompt = f"以下の記事タイトルリストから、このユーザーの興味関心を3つのキーワードで抽出して: {', '.join(titles)}"
    response = model.generate_content(prompt)
    return response.text

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    articles = supabase.table("articles").select("*").order("created_at", desc=True).execute().data
    
    # AIサマリー（最新5件から生成）
    summary = "AI分析中..."
    if len(articles) > 0:
        top_titles = [a['title'] for a in articles[:5]]
        summary_res = model.generate_content(f"以下の最新記事5件を読み、今日の重要トピックを3行でまとめて:\n" + "\n".join(top_titles))
        summary = summary_res.text

    # HTML (UI部分)
    html_content = f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; background: #f4f4f9; padding: 10px; }}
                .ai-panel {{ background: #fff; border-radius: 8px; padding: 15px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .summary-board {{ background: #e3f2fd; border-left: 5px solid #2196f3; padding: 10px; margin-bottom: 15px; font-size: 0.9em; }}
                .article-row {{ background: #fff; padding: 10px; border-bottom: 1px solid #eee; display: flex; align-items: center; text-decoration: none; color: #333; }}
                .reason {{ font-size: 0.75em; color: #666; font-style: italic; display: block; }}
                input, textarea {{ width: 100%; margin-bottom: 10px; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }}
                button {{ background: #2196f3; color: white; border: none; padding: 10px; width: 100%; border-radius: 4px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="ai-panel">
                <h3>🤖 今日のAI要約</h3>
                <div class="summary-board">{summary.replace('\n', '<br>')}</div>
                <form action="/ai-collect" method="post">
                    <textarea name="urls" placeholder="参考URLを複数貼り付け（任意）"></textarea>
                    <input type="number" name="count" value="5" min="1" max="10"> 件検索する
                    <button type="submit">AIにお任せ収集</button>
                </form>
            </div>
            <h3>📚 MY LIST</h3>
            {"".join([f'<a href="{a["url"]}" class="article-row"><div>{a["title"]}<span class="reason">{a.get("ai_reason", "")}</span></div></a>' for a in articles])}
        </body>
    </html>
    """
    return html_content

@app.post("/ai-collect")
async def ai_collect(urls: str = Form(...), count: int = Form(...)):
    # 1. 傾向分析
    pref = await get_user_preference()
    
    # 2. 検索クエリ生成
    query_prompt = f"ユーザーの好み: {pref}\n参考URL: {urls}\nこれらを元に、今探すべき最新記事の検索クエリを1つ作って。"
    query = model.generate_content(query_prompt).text
    
    # 3. Tavilyで検索
    search_res = tavily.search(query=query, max_results=count)
    
    # 4. 保存
    for res in search_res['results']:
        # 選定理由を生成
        reason_res = model.generate_content(f"記事『{res['title']}』を、ユーザーの好み『{pref}』に基づいて選んだ理由を1行で説明して。")
        supabase.table("articles").insert({{
            "title": res['title'],
            "url": res['url'],
            "ai_reason": reason_res.text,
            "is_archived": False
        }}).execute()
        
    return HTMLResponse("<script>alert('収集完了！'); window.location.href='/';</script>")