from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def home():
    return {
        "message": "ImpactChain AI Backend Running!"
    }
@app.get("/api/articles")
async def get_articles():

    return [
        {
            "title": "Sample Article 1",
            "source": "BBC World",
            "published_at": "2026-07-10T12:00:00Z"
        },
        {
            "title": "Sample Article 2",
            "source": "Economic Times",
            "published_at": "2026-07-10T12:30:00Z"
        }
    ]