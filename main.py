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
        # より強力なブラウザのふり（User-Agent）を設定
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        config.request_timeout = 15
        config.fetch_images = True 

        article = Article(url, language='ja', config=config)
        article.download()
        article.parse()
        
        data = {
            "title": article.title or "No Title",
            "url": url,
            "image_url": article.top_image or "https://via.placeholder.com/300x200?text=No+Image",
            "summary": article.text[:50] + "...",
            "is_archived": False
        }
        supabase.table("articles").insert(data).execute()
        return {"status": "success", "title": article.title}
    except Exception as e:
        # 失敗してもタイトルだけはURLから推測して保存を試みる（403対策の予備）
        try:
            data = {"title": url, "url": url, "is_archived": False}
            supabase.table("articles").insert(data).execute()
            return {"status": "partial_success", "message": "Saved URL only due to error"}
        except:
            return {"status": "error", "message": str(e)}

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
    
    def render_list(articles, is_archive):
        html = ""
        for a in articles:
            domain = a.get('url', '').split('/')[2] if 'url' in a and '/' in a['url'] else "link"
            action_btn = "" if is_archive else f'<button onclick="action({a["id"]}, \'archive\')" class="btn-check">Done</button>'
            html += f"""
            <div class="card" id="card-{a['id']}">
                <div class="card-img" style="background-image: url('{a.get('image_url', '') or 'https://via.placeholder.com/300x200'}')"></div>
                <div class="card-body">
                    <div class="card-domain">{domain}</div>
                    <h3 class="card-title"><a href="{a['url']}" target="_blank">{a['title']}</a></h3>
                    <div class="card-footer">
                        {action_btn}
                        <button onclick="action({a['id']}, \'delete\')" class="btn-delete">Delete</button>
                    </div>
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
        <title>My Pocket</title>
        <style>
            :root {{ --primary: #ef4056; --bg: #f3f3f3; }}
            body {{ font-family: -apple-system, sans-serif; background: var(--bg); margin: 0; padding-top: 55px; }}
            header {{ background: white; height: 45px; position: fixed; top: 0; width: 100%; display: flex; box-shadow: 0 1px 2px rgba(0,0,0,0.1); z-index: 100; }}
            .tabs {{ display: flex; width: 100%; justify-content: center; gap: 30px; }}
            .tab {{ color: #777; padding: 12px 5px; font-weight: bold; font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent; }}
            .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
            
            /* 2列表示のためのグリッド設定 */
            .container {{ 
                display: grid; 
                grid-template-columns: repeat(2, 1fr); 
                gap: 10px; 
                padding: 10px; 
                max-width: 800px; 
                margin: 0 auto; 
            }}
            
            .card {{ background: white; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .card-img {{ height: 100px; background-size: cover; background-position: center; background-color: #eee; }}
            .card-body {{ padding: 8px; flex: 1; display: flex; flex-direction: column; }}
            .card-domain {{ font-size: 9px; color: #aaa; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
            .card-title {{ margin: 0; font-size: 13px; line-height: 1.3; height: 2.6em; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
            .card-title a {{ color: #333; text-decoration: none; }}
            .card-footer {{ margin-top: auto; padding-top: 8px; display: flex; justify-content: space-between; border-top: 1px solid #f0f0f0; }}
            button {{ border: none; background: none; font-weight: bold; cursor: pointer; font-size: 11px; padding: 5px; }}
            .btn-check {{ color: var(--primary); }}
            .btn-delete {{ color: #bbb; }}
        </style>
    </head>
    <body>
        <header>
            <div class="tabs">
                <div id="t-unread" class="tab active" onclick="show('unread')">My List</div>
                <div id="t-archive" class="tab" onclick="show('archive')">Archive</div>
            </div>
        </header>
        <div id="unread-list" class="container">{render_list(unread.data, False)}</div>
        <div id="archived-list" class="container" style="display:none">{render_list(archived.data, True)}</div>
        <script>
            function show(type) {{
                document.getElementById('unread-list').style.display = type === 'unread' ? 'grid' : 'none';
                document.getElementById('archived-list').style.display = type === 'archive' ? 'grid' : 'none';
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