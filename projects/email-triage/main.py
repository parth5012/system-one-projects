"""Standalone FastAPI Application Server for Email Triage (System One Decision Engine).
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from email_triage import router as email_triage_router, init_db

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite tables & seed allowlist
    init_db()
    yield

app = FastAPI(
    title="Email Triage - System One Engine",
    description="Deterministic email triage, classification, and allowlist engine powered by TypeSafe Jev & Cloudflare Clef",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=500)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "email-triage",
        "engine": "system-one",
        "providers": ["cloudflare-clef", "vercel-ai-gateway", "openrouter-jev"]
    }

# Include Triage Router
app.include_router(email_triage_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8085))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"🚀 Starting Email Triage Engine at http://{host}:{port}/email-triage")
    uvicorn.run("main:app", host=host, port=port, reload=True)
