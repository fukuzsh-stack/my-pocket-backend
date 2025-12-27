import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from newspaper import Article, Config  # Configを追加してブラウザのふりをさせる
from supabase import create_client, Client

app = FastAPI()

# --- あなたのSupabase情報をここに貼り付けてください ---
SUPABASE_URL = "https://vdpxribywidmbvwnmplu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkcHhyaWJ5d2lkbWJ2d25tcGx1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4MTkyODgsImV4cCI6MjA4MjM5NTI4OH0.FQgAMLKW7AxPgK-pPO0IC7lrrCTOtzcJ9DNlbqH3pUk"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 1. 記事を解析してSupabaseへ保存 (403エラー回避設定済み) ---
@app.get("/extract")
def extract_and_save(url: str):
    try:
        # ブラウザ(Safari)のふりをするための設定を追加
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
        config.request_timeout = 10

        # 設定を適用して記事を取得
        article = Article(url, language='ja', config=config)
        article.download()
        article.parse()
        
        data = {
            "title": article.title,
            "url": url,
            "image_url": article.top_image or "https://via.placeholder.com/300x200?text=No+Image",
            "summary": article.text[:80] + "...",
            "is_archived": False
        }
        # Supabaseに保存
        supabase.table("articles").insert(data).execute()
        return {"status": "success", "title": article.title}
    except Exception as e:
        # エラーが起きた場合はiPhoneにその理由を返す
        return {"status": "error", "message": str(e)}

# --- 2. アーカイブ機能 ---
@app.post("/archive/{id}")
def archive_article(id: int):
    supabase.table("articles").update({"is_archived": True}).eq("id", id).execute()
    return {"status": "success"}

# --- 3. 削除機能 ---
@app.post("/delete/{id}")
def delete_article(id: int):
    supabase.table("articles").delete().eq("id", id).execute()
    return {"status": "success"}

# --- 4. メインUI画面 (Pocket風デザイン) ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 未読とアーカイブ済みのデータを取得
    unread = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    archived = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    
    def render_list(articles, is_archive):
        html = ""
        for a in articles:
            domain = a['url'].split('/')[2] if '/' in a['url'] else ""
            # 未読タブの時だけDone(アーカイブ)ボタンを表示
            action_btn = "" if is_archive else f'<button onclick="action({a["id"]}, \'archive\')" class="btn-check">Done</button>'
            html += f"""
            <div class="card" id="card-{a['id']}">
                <div class="card-img" style="background-image: url('{a['image_url']}')"></div>
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
            :root {{ --primary: #ef4056; --bg: #f6f6f6; }}
            body {{ font-family: -apple-system, sans-serif; background: var(--bg); margin: 0; padding-top: 60px; }}
            header {{ background: white; height: 50px; position: fixed; top: 0; width: 100%; display: flex; box-shadow: 0 1px 3px rgba(0,0,0,0.1); z-index: 100; }}
            .tabs {{ display: flex; width: 100%; justify-content: space-around; }}
            .tab {{ color: #666; padding: 15px; font-weight: bold; cursor: pointer; border-bottom: 3px solid transparent; }}
            .tab.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
            .container {{ max-width: 1000px; margin: 0 auto; padding: 15px; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
            .card {{ background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
            .card-img {{ height: 160px; background-size: cover; background-position: center; }}
            .card-body {{ padding: 15px; }}
            .card-domain {{ font-size: 11px; color: #999; margin-bottom: 5px; }}
            .card-title {{ margin: 0; font-size: 16px; line-height: 1.4; height: 3em; overflow: hidden; }}
            .card-title a {{ color: #333; text-decoration: none; }}
            .card-footer {{ margin-top: 15px; display: flex; gap: 20px; border-top: 1px solid #eee; padding-top: 10px; }}
            button {{ border: none; background: none; font-weight: bold; cursor: pointer; }}
            .btn-check {{ color: var(--primary); }}
            .btn-delete {{ color: #999; }}
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