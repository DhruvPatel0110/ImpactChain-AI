from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def home():
    return {
        "message": "ImpactChain AI Backend Running!"
    }