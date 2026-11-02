from fastapi import FastAPI

app = FastAPI(
    title="Repost Cleaner API",
    description="Backend API for Repost Cleaner",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to Repost Cleaner API",
        "status": "running"
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "repost-cleaner-api"
    }