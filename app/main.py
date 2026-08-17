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
from .discover import discover_miners, discovery_debug, resolve_jury_roster
from .miners import query_jury

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

app = FastAPI(
    title="Signal Jury",
    description="Track 3 app — multi-miner forecast briefs on live Telegraph miners",
    version="0.2.1",
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
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        examples=["Will Claude system prompts be widely adopted?"],
    )
    # Omit this field (or null) to use MINER_BASE_URLS + discovery.
    # Only set it to override with explicit Telegraph miner HTTPS base URLs.
    miner_base_urls: Optional[List[str]] = Field(
        default=None,
        examples=[None],
        description="Optional override list of miner base URLs. Leave null to use env + discovery.",
    )
    discover: Optional[bool] = Field(
        default=None,
        examples=[True],
        description="None = use DISCOVERY_ENABLED from settings",
    )


@app.get("/health")
async def health():
    s = get_settings()
    return {
        "status": "ok",
        "app": "signal-jury",
        "version": "0.2.1",
        "track": 3,
        "protocol": "telegraph",
        "miners_configured": len(s.base_urls()),
        "miner_base_urls": s.base_urls(),
        "discovery_enabled": s.discovery_enabled,
        "telegraph_node_url": s.telegraph_node_url,
        "max_jury_size": s.max_jury_size,
    }


@app.get("/api/miners")
async def list_miners(discover: bool = True):
    s = get_settings()
    if discover and s.discovery_enabled:
        roster = await resolve_jury_roster(s)
        discovered = await discover_miners(s)
    else:
        roster = list(zip(s.names(), s.base_urls()))
        discovered = []
    return {
        "jury": [{"name": n, "base_url": u, "role": "primary" if i == 0 else "peer"} for i, (n, u) in enumerate(roster)],
        "discovered_catalog_count": len(discovered),
        "discovery_enabled": s.discovery_enabled,
    }


@app.get("/api/discovery/debug")
async def discovery_debug_endpoint():
    """Show why catalog miners are kept or skipped (clears discovery cache)."""
    return await discovery_debug(get_settings())


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
        object.__setattr__(settings, "discovery_enabled", False)

    use_discovery = settings.discovery_enabled if req.discover is None else req.discover
    if not use_discovery:
        settings = copy(settings)
        object.__setattr__(settings, "discovery_enabled", False)

    roster = await resolve_jury_roster(settings)
    if not roster:
        raise HTTPException(status_code=500, detail="No miners available (check MINER_BASE_URLS)")

    votes = await query_jury(settings, question, roster=roster)
    brief = build_brief(question, votes)
    return {
        "brief": brief,
        "roster": [{"name": n, "base_url": u} for n, u in roster],
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
            "mode": "parallel_jury",
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
