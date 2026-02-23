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
            .search-box {{ padding: 12px 16px; background: white; border-bottom: 0.5px solid var(--line); position: sticky; top: 50px; z-index: 90; }}
            .search-input {{ width: 100%; padding: 10px 14px; border: none; background: #f2f2f7; border-radius: 12px; font-size: 15px; outline: none; box-sizing: border-box; }}
            .list-item {{ display: flex; align-items: center; padding: 10px 16px; border-bottom: 0.5px solid var(--line); gap: 12px; }}
            .thumb {{ width: 55px; height: 38px; border-radius: 4px; object-fit: cover; background: #f0f0f5; flex-shrink: 0; }}
            .item-content {{ flex: 1; min-width: 0; }}
            .item-meta {{ font-size: 10px; font-weight: 700; color: var(--sub); margin-bottom: 2px; display: flex; align-items: center; gap: 4px; }}
            .item-title {{ font-size: 13px; font-weight: 500; line-height: 1.3; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
            .item-title a {{ color: var(--text); text-decoration: none; }}
            .favicon {{ width: 14px; height: 14px; border-radius: 2px; }}
            .btn {{ border: none; background: #f0f0f5; font-size: 10px; font-weight: 700; padding: 6px 12px; border-radius: 6px; cursor: pointer; }}
            .btn-done {{ color: white; background: var(--primary); }}
        </style>
    </head>
    <body>
        <header><div class="tabs">
            <a href="/" class="tab" style="{unread_style}">マイリスト</a>
            <a href="/archived" class="tab" style="{archive_style}">アーカイブ</a>
        </div></header>
        <div class="container">
            <div class="search-box"><input type="text" id="searchInput" class="search-input" placeholder="タイトルやサイト名で検索..." onkeyup="fuzzySearch()"></div>
            <div id="articleList">{content}</div>
        </div>
        <script>
            function fuzzySearch() {{
                const q = document.getElementById('searchInput').value.toLowerCase();
                const items = document.getElementsByClassName('list-item');
                for (let i of items) {{
                    const t = (i.getAttribute('data-title') + i.getAttribute('data-domain')).toLowerCase();
                    i.style.display = t.includes(q) ? 'flex' : 'none';
                }}
            }}
        </script>
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
            "is_archived": False, "ai_reason": (article.text[:100] or "")
        }).execute()
        return HTMLResponse("<html><body onload='window.close()'>保存完了</body></html>")
    except:
        supabase.table("articles").insert({"title": url, "url": url, "is_archived": False}).execute()
        return RedirectResponse(url="/", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index():
    if not supabase: return HTMLResponse("Server connection error")
    try:
        res = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
        articles = res.data or []
        rows = ""
        for a in articles:
            url = a.get('url', '')
            domain = 'WEB'
            try:
                if url.startswith('http'):
                    domain = url.split('/')[2].replace('www.', '')
            except:
                pass
            
            favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
            img_html = f'<img src="{a["image_url"]}" class="thumb">' if a.get('image_url') else '<div style="width:55px;"></div>'
            time_str = time_ago(a.get('created_at',''))
            
            rows += f"""
            <div class="list-item" data-title="{a['title']}" data-domain="{domain}">
                {img_html}
                <div class="item-content">
                    <div class="item-meta"><img src="{favicon}" class="favicon"> {domain} • {time_str}</div>
                    <div class="item-title"><a href="{a['url']}" target="_blank">{a['title']}</a></div>
                </div>
                <form action="/archive-action/{a['id']}" method="post"><button class="btn btn-done">完了</button></form>
            </div>
            """
        return get_layout(rows if rows else '<div style="padding:40px; text-align:center;">記事はありません</div>', "unread")
    except Exception as e:
        return HTMLResponse(f"Database Error: {e}")

@app.post("/archive-action/{id}")
async def action_archive(id: int):
    supabase.table("articles").update({"is_archived": True}).eq("id", id).execute()
    return RedirectResponse(url="/", status_code=303)

@app.get("/archived", response_class=HTMLResponse)
async def archived_page():
    res = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    articles = res.data or []
    rows = ""
    for a in articles:
        rows += f'<div class="list-item" style="opacity:0.6;"><div class="item-title">{a["title"]}</div></div>'
    return get_layout(rows if rows else '<div style="padding:40px; text-align:center;">アーカイブは空です</div>', "archive")