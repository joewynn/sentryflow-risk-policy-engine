from fastapi import FastAPI
from src.api.router import router

# Create the FastAPI application
app = FastAPI(title="SentryFlow Risk Engine", version="2026.03")

# Include the router with all endpoints
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)