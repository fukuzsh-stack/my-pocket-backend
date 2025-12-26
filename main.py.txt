import os
from fastapi import FastAPI
from newspaper import Article

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Pocket API is running"}

@app.get("/extract")
def extract(url: str):
    try:
        article = Article(url, language='ja')
        article.download()
        article.parse()
        return {
            "title": article.title,
            "text": article.text,
            "image": article.top_image,
            "domain": url.split('/')[2]
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Renderは環境変数PORTを指定してくるため、それに合わせます
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)