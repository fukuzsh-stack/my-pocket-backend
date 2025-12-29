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
        # Supabaseの時刻(UTC)を解析
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days}日前"
        seconds = diff.seconds
        if seconds < 60:
            return "たった今"
        if seconds < 3600:
            return f"{seconds // 60}分前"
        return f"{seconds // 3600}時間前"
    except:
        return ""

# 【UI改善】人間工学に基づいたコンパクト・リストデザイン
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
            :root {{ --primary: #ef4056; --bg: #ffffff; --line: #f2f2f7; --text: #1c1c1e; --sub: #8e8e93; --blue: #007aff; }}
            body {{ font-family: -apple-system, sans-serif; background: #f2f2f7; margin: 0; padding-top: 50px; color: var(--text); }}
            header {{ background: rgba(255,255,255,0.9); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); position: fixed; top: 0; width: 100%; height: 50px; display: flex; border-bottom: 0.5px solid #d1d1d6; z-index: 100; }}
            .tabs {{ display: flex; width: 100%; justify-content: center; gap: 40px; }}
            .tab {{ text-decoration: none; padding: 14px 10px; font-weight: 700; font-size: 13px; transition: 0.2s; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; min-height: 100vh; box-shadow: 0 0 10px rgba(0,0,0,0.05); }}
            
            /* スリム・リストレイアウト */
            .list-item {{ 
                display: flex; align-items: center; padding: 12px 16px; border-bottom: 0.5px solid var(--line); gap: 12px;
            }}
            .favicon {{ width: 18px; height: 18px; flex-shrink: 0; border-radius: 3px; background: #f9f9f9; }}
            .item-content {{ flex: 1; min-width: 0; }}
            .item-meta {{ display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 700; color: var(--sub); margin-bottom: 2px; text-transform: uppercase; }}
            .item-title {{ font-size: 14px; line-height: 1.4; font-weight: 500; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
            .item-title a {{ color: var(--text); text-decoration: none; }}
            
            .item-actions {{ display: flex; gap: 8px; align-items: center; }}
            .btn {{ border: none; background: #f0f0f5; font-size: 11px; font-weight: 700; cursor: pointer; padding: 8px 12px; border-radius: 6px; transition: 0.2s; }}
            .btn-done {{ color: white; background: var(--primary); }}
            .btn-restore {{ color: white; background: var(--blue); }}
            .btn-del {{ background: none; color: #ccc; font-size: 20px; padding: 0 4px; }}
            .btn:active {{ transform: scale(0.92); opacity: 0.7; }}
            
            .empty-msg {{ text-align: center; color: var(--sub); padding-top: 100px; font-size: 14px; }}
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
    try:
        config = Config(); config.browser_user_agent = 'Mozilla/5.0'; config.request_timeout = 15
        article = Article(url, language='ja', config=config)
        article.download(); article.parse()
        supabase.table("articles").insert({"title": article.title or url, "url": url, "is_archived": False}).execute()
        # Safariから追加した時に自動で閉じる
        return HTMLResponse("<html><body onload='window.close()'>保存完了</body></html>")
    except:
        supabase.table("articles").insert({"title": url, "url": url, "is_archived": False}).execute()
        return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index():
    res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    articles = res.data or []
    rows = ""
    for a in articles:
        # ドメイン抽出とFavicon取得
        domain = a['url'].split('/')[2].replace('www.', '') if 'url' in a else 'WEB'
        favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        time_display = time_ago(a.get('created_at', ''))
        
        rows += f"""
        <div class="list-item">
            <img src="{favicon}" class="favicon" onerror="this.style.display='none'">
            <div class="item-content">
                <div class="item-meta"><span>{domain}</span> • <span>{time_display}</span></div>
                <div class="item-title"><a href="{a['url']}" target="_blank">{a['title']}</a></div>
            </div>
            <div class="item-actions">
                <form action="/archive-action/{a['id']}" method="post"><button class="btn btn-done">完了</button></form>
                <form action="/delete-action/{a['id']}" method="post" onsubmit="return confirm('この記事を削除しますか？')"><button class="btn btn-del">×</button></form>
            </div>
        </div>
        """
    return get_layout(rows if rows else '<div class="empty-msg">まだ記事はありません</div>', "unread")

@app.get("/archived", response_class=HTMLResponse)
async def archived_page():
    res = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    articles = res.data or []
    rows = ""
    for a in articles:
        domain = a['url'].split('/')[2].replace('www.', '') if 'url' in a else 'WEB'
        favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        rows += f"""
        <div class="list-item" style="opacity: 0.65;">
            <img src="{favicon}" class="favicon">
            <div class="item-content">
                <div class="item-title"><a href="{a['url']}" target="_blank">{a['title']}</a></div>
            </div>
            <div class="item-actions">
                <form action="/unarchive-action/{a['id']}" method="post"><button class="btn btn-restore">復元</button></form>
                <form action="/delete-action/{a['id']}" method="post" onsubmit="return confirm('完全に削除しますか？')"><button class="btn btn-del">×</button></form>
            </div>
        </div>
        """
    return get_layout(rows if rows else '<div class="empty-msg">アーカイブは空です</div>', "archive")

@app.post("/archive-action/{id}")
async def action_archive(id: int):
    supabase.table("articles").update({"is_archived": True}).eq("id", id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.post("/unarchive-action/{id}")
async def action_unarchive(id: int):
    supabase.table("articles").update({"is_archived": False}).eq("id", id).execute()
    return RedirectResponse(url="/archived", status_code=303)

@app.post("/delete-action/{id}")
async def action_delete(id: int, request: Request):
    supabase.table("articles").delete().eq("id", id).execute()
    # 削除したページ（マイリストかアーカイブか）に戻る
    ref = request.headers.get("referer", "/")
    return RedirectResponse(url=ref, status_code=303)