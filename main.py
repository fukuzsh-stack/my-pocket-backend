import os
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from newspaper import Article, Config
from supabase import create_client, Client

app = FastAPI()

# --- あなたのSupabase情報（直書きで確実に接続） ---
SUPABASE_URL = "https://vdpxribywidmbvwnmplu.supabase.co"
# Supabase KeyはRenderのEnvironment Variablesにあるものを使用
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/extract")
async def extract_and_save(url: str = Query(...)):
    try:
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        config.request_timeout = 15
        article = Article(url, language='ja', config=config)
        article.download()
        article.parse()
        
        data = {
            "title": article.title or url,
            "url": url,
            "image_url": article.top_image or "",
            "is_archived": False
        }
        supabase.table("articles").insert(data).execute()
        # iPhoneショートカット向けに小さな成功画面を返す
        return HTMLResponse("<html><body onload='window.close()'>保存完了</body></html>")
    except:
        # 解析に失敗してもURLだけは保存する
        supabase.table("articles").insert({"title": url, "url": url, "is_archived": False}).execute()
        return RedirectResponse(url="/", status_code=303)

@app.post("/archive/{id}")
async def archive_article(id: int):
    supabase.table("articles").update({"is_archived": True}).eq("id", id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{id}")
async def delete_article(id: int):
    supabase.table("articles").delete().eq("id", id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 未読記事のみを取得
    unread = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    
    html_rows = ""
    for a in unread.data or []:
        html_rows += f"""
        <div style="background:white; padding:15px; margin-bottom:10px; border-radius:8px; border-bottom:1px solid #eee;">
            <div style="font-size:14px; font-weight:bold; margin-bottom:10px;">
                <a href="{a['url']}" target="_blank" style="color:#333; text-decoration:none;">{a['title']}</a>
            </div>
            <div style="display:flex; gap:15px;">
                <form action="/archive/{a['id']}" method="post"><button style="color:#ef4056; background:none; border:none; font-weight:bold; cursor:pointer;">完了</button></form>
                <form action="/delete/{a['id']}" method="post"><button style="color:#ccc; background:none; border:none; cursor:pointer;">削除</button></form>
            </div>
        </div>
        """
    
    return f"""
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
        <body style="font-family:-apple-system, sans-serif; background:#f9f9f9; padding:20px;">
            <h2 style="color:#ef4056; border-bottom:2px solid #ef4056; padding-bottom:10px;">MY LIST</h2>
            {html_rows if html_rows else "<p style='color:#999;'>記事はありません</p>"}
        </body>
    </html>
    """