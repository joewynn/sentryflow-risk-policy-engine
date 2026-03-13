from fastapi import FastAPI
from src.api.router import get_risk

from fastapi import FastAPI
from src.api.router import app as sentry_app

app = sentry_app  # Re-export the app from router.py

@app.post("/v1/risk-score")
async def risk_score(payload: dict):
    return get_risk(payload)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)