from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.router import api_router

app = FastAPI(
    title="MarketEval Intelligence API",
    description="Backend API powering internal dashboards, desktop overlays, and Telegram bots.",
    version="1.0.0",
)

# CORS setup for Streamlit and external clients [cite: 5, 6]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the API routes
app.include_router(api_router, prefix="/api")

@app.get("/", tags=["Health Check"])
async def root():
    return {"status": "online", "message": "MarketEval API is running."}