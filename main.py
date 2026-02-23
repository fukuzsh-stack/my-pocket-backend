import os
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from newspaper import Article, Config
from supabase import create_client, Client

app = FastAPI()

# --- 設定（環境変数から確実に取得） ---
SUPABASE_URL = "https://vdpxribywidmbvwnmplu.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 【機能追加】時間を「〜前」と表示する人間中心のロジック
def time_ago(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.days > 0: return f"{diff.days}日前"
        seconds = diff.seconds
        if seconds < 60: return "たった今"
        if seconds < 3600: return f"{seconds // 60}分前"
        return f"{seconds // 3600}時間前"
    except: return ""

def get_layout(content: str, active_tab: str):
    unread_style = "color: #ef4056; border-bottom: 3px solid #ef4056;" if active_tab == "unread" else "color: #8e8e93;"
    archive_style = "color: #ef4056; border-bottom: 3px solid #ef4056;" if active_tab == "archive" else "color: #8e8e93;"
    
    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            :root {{ --primary: #ef4056; --bg: #ffffff; --line: #f2f2f7; --text: #1c1c1e; --sub: #8e8e93; }}
            body {{ font-family: -apple-system, sans-serif; background: #f2f2f7; margin: 0; padding-top: 50px; color: var(--text); }}
            header {{ background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); position: fixed; top: 0; width: 100%; height: 50px; display: flex; border-bottom: 0.5px solid #d1d1d6; z-index: 100; }}
            .tabs {{ display: flex; width: 100%; justify-content: center; gap: 40px; }}
            .tab {{ text-decoration: none; padding: 14px 10px; font-weight: 700; font-size: 13px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; min-height: 100vh; }}
            .list-item {{ display: flex; align-items: center; padding: 12px 16px; border-bottom: 0.5px solid var(--line); gap: 12px; }}
            .thumb {{ width: 60px; height: 45px; border-radius: 6px; object-fit: cover; background: #f0f0f5; flex-shrink: 0; }}
            .item-content {{ flex: 1; min-width: 0; }}
            .item-meta {{ font-size: 10px; font-weight: 700; color: var(--sub); margin-bottom: 2px; display: flex; align-items: center; gap: 4px; }}
            .item-title {{ font-size: 14px; font-weight: 500; line-height: 1.4; }}
            .item-title a {{ color: var(--text); text-decoration: none; }}
            .actions {{ display: flex; flex-direction: column; gap: 6px; }}
            .btn {{ border: none; font-size: 10px; font-weight: 700; padding: 6px 10px; border-radius: 6px; cursor: pointer; text-align: center; }}
            .btn-done {{ color: white; background: var(--primary); }}
            .btn-delete {{ color: white; background: #8e8e93; }}
            .btn-restore {{ color: white; background: #34c759; }}
        </style>
    </head>
    <body>
        <header><div class="tabs">
            <a href="/" class="tab" style="{unread_style}">マイリスト</a>
            <a href="/archived" class="tab" style="{archive_style}">アーカイブ</a>
        </div></header>
        <div class="container">{content}</div>
    </body>
    </html>
    """

@app.get("/extract")
async def extract_and_save(url: str = Query(...)):
    if not supabase: return HTMLResponse("Database error")
    try:
        config = Config(); config.browser_user_agent = 'Mozilla/5.0'; config.request_timeout = 10
        article = Article(url, language='ja', config=config)
        article.download(); article.parse()
        supabase.table("articles").insert({
            "title": article.title or url, "url": url, "image_url": article.top_image or "",
            "is_archived": False
        }).execute()
        return HTMLResponse("<html><body onload='window.close()'>保存完了</body></html>")
    except:
        supabase.table("articles").insert({"title": url, "url": url, "is_archived": False}).execute()
        return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index():
    if not supabase: return HTMLResponse("Database Error")
    res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    articles = res.data or []
    rows = ""
    for a in articles:
        url = a.get('url', '')
        domain = url.split('/')[2].replace('www.', '') if 'http' in url else 'WEB'
        img_html = f'<img src="{a["image_url"]}" class="thumb">' if a.get('image_url') else '<div style="width:60px;"></div>'
        rows += f"""
        <div class="list-item">
            {img_html}
            <div class="item-content">
                <div class="item-meta">{domain} • {time_ago(a.get('created_at',''))}</div>
                <div class="item-title"><a href="{a['url']}" target="_blank">{a['title']}</a></div>
            </div>
            <div class="actions">
                <form action="/update-status/{a['id']}" method="post">
                    <input type="hidden" name="status" value="archive">
                    <button class="btn btn-done">完了</button>
                </form>
                <form action="/delete-article/{a['id']}" method="post">
                    <button class="btn btn-delete" onclick="return confirm('削除しますか？')">削除</button>
                </form>
            </div>
        </div>
        """
    return get_layout(rows if rows else '<div style="padding:40px; text-align:center; color:gray;">記事はありません</div>', "unread")

@app.get("/archived", response_class=HTMLResponse)
async def archived_page():
    if not supabase: return HTMLResponse("Database Error")
    res = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    articles = res.data or []
    rows = ""
    for a in articles:
        url = a.get('url', '')
        domain = url.split('/')[2].replace('www.', '') if 'http' in url else 'WEB'
        img_html = f'<img src="{a["image_url"]}" class="thumb">' if a.get('image_url') else '<div style="width:60px;"></div>'
        rows += f"""
        <div class="list-item">
            {img_html}
            <div class="item-content">
                <div class="item-meta">{domain} • {time_ago(a.get('created_at',''))}</div>
                <div class="item-title"><a href="{a['url']}" target="_blank">{a['title']}</a></div>
            </div>
            <div class="actions">
                <form action="/update-status/{a['id']}" method="post" style="display:inline;">
                    <input type="hidden" name="status" value="restore">
                    <button class="btn btn-restore">復元</button>
                </form>
                <form action="/delete-article/{a['id']}" method="post" style="display:inline;">
                    <button class="btn btn-delete">削除</button>
                </form>
            </div>
        </div>
        """
    return get_layout(rows if rows else '<div style="padding:40px; text-align:center; color:gray;">アーカイブは空です</div>', "archive")

@app.post("/update-status/{id}")
async def update_status(id: int, status: str = Form(...)):
    new_status = True if status == "archive" else False
    supabase.table("articles").update({"is_archived": new_status}).eq("id", id).execute()
    # 復元した時はマイリストへ、完了した時はアーカイブへ移動
    return RedirectResponse(url="/archived" if status == "archive" else "/", status_code=303)

@app.post("/delete-article/{id}")
async def delete_article(id: int, request: Request):
    supabase.table("articles").delete().eq("id", id).execute()
    referer = request.headers.get("referer", "/")
    return RedirectResponse(url=referer, status_code=303)