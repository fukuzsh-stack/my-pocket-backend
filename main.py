import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from newspaper import Article, Config
from supabase import create_client, Client

app = FastAPI()

# --- あなたのSupabase情報 ---
SUPABASE_URL = "https://vdpxribywidmbvwnmplu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkcHhyaWJ5d2lkbWJ2d25tcGx1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4MTkyODgsImV4cCI6MjA4MjM5NTI4OH0.FQgAMLKW7AxPgK-pPO0IC7lrrCTOtzcJ9DNlbqH3pUk"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/extract")
def extract_and_save(url: str):
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
        return {"status": "success"}
    except:
        supabase.table("articles").insert({"title": url, "url": url, "is_archived": False}).execute()
        return {"status": "partial_success"}

@app.post("/archive/{id}")
def archive_article(id: int):
    supabase.table("articles").update({"is_archived": True}).eq("id", id).execute()
    return {"status": "success"}

@app.post("/delete/{id}")
def delete_article(id: int):
    supabase.table("articles").delete().eq("id", id).execute()
    return {"status": "success"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    unread = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    archived = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    
    def render_rows(articles, is_archive):
        html = ""
        for a in articles:
            domain = a.get('url', '').split('/')[2] if 'url' in a and '/' in a['url'] else ""
            img_tag = f'<div class="row-img" style="background-image: url(\'{a["image_url"]}\')"></div>' if a.get('image_url') else '<div class="row-img no-img"></div>'
            btn = f'<button onclick="action({a["id"]}, \'archive\')" class="btn-check">Done</button>' if not is_archive else ""
            html += f"""
            <div class="list-row" id="card-{a['id']}">
                {img_tag}
                <div class="row-content">
                    <div class="row-domain">{domain}</div>
                    <div class="row-title"><a href="{a['url']}" target="_blank">{a['title']}</a></div>
                </div>
                <div class="row-actions">
                    {btn}
                    <button onclick="action({a['id']}, \'delete\')" class="btn-delete">×</button>
                </div>
            </div>
            """
        return html

    return f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{ --primary: #ef4056; --bg: #ffffff; }}
            body {{ font-family: -apple-system, sans-serif; background: var(--bg); margin: 0; padding-top: 50px; color: #333; }}
            header {{ background: white; height: 45px; position: fixed; top: 0; width: 100%; display: flex; border-bottom: 1px solid #eee; z-index: 100; }}
            .tabs {{ display: flex; width: 100%; justify-content: center; gap: 40px; }}
            .tab {{ color: #999; padding: 12px 0; font-weight: bold; font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent; }}
            .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
            
            /* スリムな1列リスト表示 */
            .list-row {{ 
                display: flex; 
                align-items: center; 
                padding: 10px 15px; 
                border-bottom: 1px solid #f0f0f0; 
                gap: 12px;
            }}
            .row-img {{ width: 50px; height: 50px; border-radius: 4px; background-size: cover; background-position: center; flex-shrink: 0; background-color: #f9f9f9; }}
            .no-img {{ border: 1px solid #eee; }}
            .row-content {{ flex: 1; min-width: 0; }}
            .row-domain {{ font-size: 10px; color: #aaa; margin-bottom: 2px; }}
            .row-title {{ font-size: 14px; line-height: 1.3; font-weight: 500; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
            .row-title a {{ color: #333; text-decoration: none; }}
            .row-actions {{ display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }}
            button {{ border: none; background: none; font-weight: bold; cursor: pointer; font-size: 12px; padding: 2px 5px; }}
            .btn-check {{ color: var(--primary); }}
            .btn-delete {{ color: #ccc; font-size: 18px; }}
        </style>
    </head>
    <body>
        <header>
            <div class="tabs">
                <div id="t-unread" class="tab active" onclick="show('unread')">MY LIST</div>
                <div id="t-archive" class="tab" onclick="show('archive')">ARCHIVE</div>
            </div>
        </header>
        <div id="unread-list">{render_rows(unread.data, False)}</div>
        <div id="archived-list" style="display:none">{render_rows(archived.data, True)}</div>
        <script>
            function show(type) {{
                document.getElementById('unread-list').style.display = type === 'unread' ? 'block' : 'none';
                document.getElementById('archived-list').style.display = type === 'archive' ? 'block' : 'none';
                document.getElementById('t-unread').classList.toggle('active', type === 'unread');
                document.getElementById('t-archive').classList.toggle('active', type === 'archive');
            }}
            async function action(id, type) {{
                if(!confirm('実行しますか？')) return;
                await fetch('/' + type + '/' + id, {{ method: 'POST' }});
                location.reload();
            }}
        </script>
    </body>
    </html>
    """