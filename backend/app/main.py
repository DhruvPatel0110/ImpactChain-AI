from fastapi import FastAPI
from app.services.rss_feed_service import RSSFeedService

app = FastAPI()
rss_feed_service = RSSFeedService()

@app.get("/")
async def home():
    return {
        "message": "ImpactChain AI Backend Running!"
    }

@app.get("/api/articles")
async def get_articles():
    articles = await rss_feed_service.fetch_articles()
    return articles