import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from newspaper import Article
from supabase import create_client, Client
app = FastAPI()

# 提供いただいたSupabaseの情報
SUPABASE_URL = "https://vdpxribywidmbvwnmplu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkcHhyaWJ5d2lkbWJ2d25tcGx1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4MTkyODgsImV4cCI6MjA4MjM5NTI4OH0.FQgAMLKW7AxPgK-pPO0IC7lrrCTOtzcJ9DNlbqH3pUk"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 1. 記事を解析してSupabaseへ保存 ---
@app.get("/extract")
def extract_and_save(url: str):
    try:
        article = Article(url, language='ja')
        article.download()
        article.parse()
        
        data = {
            "title": article.title,
            "url": url,
            "image_url": article.top_image,
            "summary": article.text[:100] + "...",
            "is_archived": False
        }
        supabase.table("articles").insert(data).execute()
        return {"status": "success", "title": article.title}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- 2. アーカイブ機能 ---
@app.post("/archive/{id}")
def archive_article(id: int):
    supabase.table("articles").update({"is_archived": True}).eq("id", id).execute()
    return {"status": "archived"}

# --- 3. 削除機能 ---
@app.post("/delete/{id}")
def delete_article(id: int):
    supabase.table("articles").delete().eq("id", id).execute()
    return {"status": "deleted"}

# --- 4. メインUI画面 (HTML) ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 未読記事を取得
    unread = supabase.table("articles").select("*").eq("is_archived", False).order("created_at", desc=True).execute()
    # アーカイブ済み記事を取得
    archived = supabase.table("articles").select("*").eq("is_archived", True).order("created_at", desc=True).execute()
    
    def render_cards(articles, is_archive_tab):
        html = ""
        for a in articles:
            btn = f'<button onclick="action({a["id"]}, \'archive\')">既読</button>' if not is_archive_tab else ""
            html += f"""
            <div class="card" id="card-{a['id']}">
                <img src="{a['image_url']}" onerror="this.src='https://via.placeholder.com/150'">
                <div class="content">
                    <h3><a href="{a['url']}" target="_blank">{a['title']}</a></h3>
                    <p>{a['summary']}</p>
                    <div class="actions">
                        {btn}
                        <button class="del" onclick="action({a['id']}, 'delete')">削除</button>
                    </div>
                </div>
            </div>
            """
        return html

    return f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; background: #f0f2f5; margin: 0; padding: 10px; }}
                .card {{ background: white; border-radius: 8px; margin-bottom: 15px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: flex; }}
                .card img {{ width: 100px; object-fit: cover; }}
                .content {{ padding: 10px; flex: 1; }}
                h3 {{ margin: 0 0 5px; font-size: 16px; }}
                h3 a {{ color: #1a73e8; text-decoration: none; }}
                p {{ font-size: 12px; color: #666; margin: 0; }}
                .actions {{ margin-top: 10px; display: flex; gap: 10px; }}
                button {{ padding: 5px 10px; border: none; border-radius: 4px; background: #34a853; color: white; cursor: pointer; }}
                button.del {{ background: #ea4335; }}
                .tabs {{ display: flex; gap: 20px; margin-bottom: 20px; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
                .tab {{ cursor: pointer; font-weight: bold; color: #666; }}
                .active {{ color: #1a73e8; border-bottom: 3px solid #1a73e8; }}
            </style>
        </head>
        <body>
            <div class="tabs">
                <div class="tab active" onclick="show('unread')">未読</div>
                <div class="tab" onclick="show('archived')">アーカイブ</div>
            </div>
            <div id="unread-list">{render_cards(unread.data, False)}</div>
            <div id="archived-list" style="display:none">{render_cards(archived.data, True)}</div>
            
            <script>
                function show(type) {{
                    document.getElementById('unread-list').style.display = type === 'unread' ? 'block' : 'none';
                    document.getElementById('archived-list').style.display = type === 'archived' ? 'block' : 'none';
                    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active'));
                }}
                async def action(id, type) {{
                    if(!confirm('実行しますか？')) return;
                    await fetch('/' + type + '/' + id, {{method: 'POST'}});
                    document.getElementById('card-' + id).remove();
                }}
            </script>
        </body>
    </html>
    """
