import os
import traceback
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

app = FastAPI()

# 初期化チェック用の関数
def initialize_clients():
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        genai.configure(api_key=GEMINI_API_KEY)
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        # モデル名を最新の指定方法に変更
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        return supabase, model, tavily
    except Exception as e:
        raise Exception(f"初期化に失敗しました: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        supabase, model, _ = initialize_clients()
        
        # データベースから取得
        res = supabase.table("articles").select("*").order("created_at", desc=True).execute()
        articles = res.data or []
        
        # AI要約（失敗しても画面を止めない）
        summary = "AI要約を準備中..."
        if articles:
            try:
                titles = [a.get('title', '無題') for a in articles[:5]]
                response = model.generate_content(f"以下を3行でまとめて:\n" + "\n".join(titles))
                summary = response.text
            except Exception as ai_err:
                summary = f"AI要約エラー: {ai_err}"

        # HTML表示
        items_html = "".join([f"""
            <div style="background:white; padding:15px; border-radius:8px; margin-bottom:10px; box-shadow:0 2px 4px rgba(0,0,0,0.05);">
                <a href="{a.get('url', '#')}" target="_blank" style="text-decoration:none; color:#333; font-weight:bold;">{a.get('title', '無題')}</a>
                <p style="font-size:0.8em; color:#666; margin:5px 0 0;">💡 {a.get('ai_reason', '保存済み')}</p>
            </div>
        """ for a in articles])

        return f"""
        <html>
            <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
            <body style="font-family:sans-serif; background:#f0f2f5; padding:20px;">
                <div style="max-width:600px; margin:0 auto;">
                    <div style="background:white; padding:20px; border-radius:12px; margin-bottom:20px; border-left:5px solid #2196f3;">
                        <h3>🤖 今日のAI要約</h3>
                        <p style="font-size:0.9em; line-height:1.6;">{summary.replace('\n', '<br>')}</p>
                        <form action="/ai-collect" method="post" style="margin-top:20px; border-top:1px solid #eee; padding-top:20px;">
                            <textarea name="urls" style="width:100%; height:80px; padding:10px;" placeholder="URLを入力"></textarea><br>
                            <button type="submit" style="width:100%; background:#2196f3; color:white; border:none; padding:12px; border-radius:5px; font-weight:bold; margin-top:10px;">AI収集を実行</button>
                        </form>
                    </div>
                    {items_html}
                </div>
            </body>
        </html>
        """
    except Exception as e:
        # エラーが発生したらその詳細を画面に表示する
        error_detail = traceback.format_exc()
        return HTMLResponse(content=f"<h3>エラーが発生しました</h3><pre>{error_detail}</pre>", status_code=500)

@app.post("/ai-collect")
async def collect(urls: str = Form("")):
    # 収集ロジック（中略）
    return HTMLResponse("<script>location.href='/';</script>")