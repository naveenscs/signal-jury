from __future__ import annotations

from copy import copy
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .brief import build_brief
from .config import get_settings
from .miners import query_jury

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

app = FastAPI(
    title="Signal Jury",
    description="Track 3 app — multi-miner forecast briefs on live Telegraph miners",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


class DeliberateRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    miner_base_urls: Optional[List[str]] = None


@app.get("/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "app": "signal-jury",
        "track": 3,
        "protocol": "telegraph",
        "miners_configured": len(s.base_urls()),
        "miner_base_urls": s.base_urls(),
    }


@app.get("/api/miners")
async def list_miners():
    s = get_settings()
    return [
        {"name": name, "base_url": url}
        for name, url in zip(s.names(), s.base_urls())
    ]


@app.post("/api/deliberate")
async def deliberate(req: DeliberateRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    settings = get_settings()
    if req.miner_base_urls:
        settings = copy(settings)
        object.__setattr__(
            settings,
            "miner_base_urls",
            ",".join(u.strip().rstrip("/") for u in req.miner_base_urls if u.strip()),
        )

    if not settings.base_urls():
        raise HTTPException(status_code=500, detail="No MINER_BASE_URLS configured")

    votes = await query_jury(settings, question)
    brief = build_brief(question, votes)
    return {
        "brief": brief,
        "votes": [
            {
                "name": v.get("name"),
                "base_url": v.get("base_url"),
                "path_used": v.get("path_used"),
                "status": v.get("status"),
                "elapsed_ms": v.get("elapsed_ms"),
                "output": v.get("output"),
                "error": v.get("error"),
            }
            for v in votes
        ],
        "hackathon": {
            "track": 3,
            "requirement": "live_telegraph_miners",
            "mocks": False,
        },
    }


@app.get("/")
async def index():
    index_path = STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="UI missing")
    return FileResponse(index_path)


@app.get("/styles.css")
async def styles():
    return FileResponse(STATIC / "styles.css", media_type="text/css")


@app.get("/app.js")
async def app_js():
    return FileResponse(STATIC / "app.js", media_type="application/javascript")
