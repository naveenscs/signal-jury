from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import Settings

logger = logging.getLogger("signal-jury.discover")

# In-memory cache so we don't hit the node on every deliberate
_cache: Dict[str, Any] = {"at": 0.0, "miners": []}
_CACHE_TTL_SEC = 120.0


def _looks_chat_capable(item: Dict[str, Any]) -> bool:
    blob = " ".join(
        str(item.get(k, ""))
        for k in (
            "slug",
            "name",
            "description",
            "supported_intents",
            "intents",
            "protocol",
        )
    ).lower()
    intents = item.get("supported_intents") or item.get("intents") or []
    if isinstance(intents, list):
        blob += " " + " ".join(str(x).lower() for x in intents)

    # Prefer chat / language miners; skip obvious weather/news-only if we can tell
    positive = any(
        k in blob
        for k in (
            "chat",
            "completion",
            "language",
            "text_generation",
            "llm",
            "groq",
            "openai",
            "llama",
            "generic",
        )
    )
    negative_only = any(
        k in blob
        for k in ("storm", "weather_forecast", "zeus", "bittensor-sn18", "deepfake", "virustotal")
    )
    if negative_only and not positive:
        return False
    # If unclear, still allow — jury will error fast on wrong APIs
    return True


def _extract_base_url(item: Dict[str, Any]) -> Optional[str]:
    for key in ("base_url", "baseUrl", "url", "endpoint", "host"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().rstrip("/")
    # nested yaml-ish
    cfg = item.get("config") or item.get("yaml") or {}
    if isinstance(cfg, dict):
        for key in ("base_url", "baseUrl"):
            val = cfg.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip().rstrip("/")
    return None


def _extract_name(item: Dict[str, Any], base_url: str) -> str:
    for key in ("name", "slug", "id", "title"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return base_url


def _normalize_list(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("integrations", "miners", "data", "items", "results"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        # single object
        if _extract_base_url(payload):
            return [payload]
    return []


async def discover_miners(settings: Settings) -> List[Tuple[str, str]]:
    """Return list of (name, base_url) from Telegraph node catalog."""
    import time

    now = time.time()
    if _cache["miners"] and now - float(_cache["at"]) < _CACHE_TTL_SEC:
        return list(_cache["miners"])

    if not settings.discovery_enabled:
        return []

    node = settings.telegraph_node_url.rstrip("/")
    url = f"{node}/miner-dispatcher/integrations"
    found: List[Tuple[str, str]] = []

    try:
        timeout = httpx.Timeout(settings.discovery_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            items = _normalize_list(resp.json())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Miner discovery failed (%s): %s", url, exc)
        return []

    seen = set()
    for item in items:
        base = _extract_base_url(item)
        if not base:
            continue
        if settings.discovery_require_https and not base.lower().startswith("https://"):
            continue
        if not _looks_chat_capable(item):
            continue
        key = base.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append((_extract_name(item, base), base))

    _cache["at"] = now
    _cache["miners"] = found
    logger.info("Discovered %s candidate miners from catalog", len(found))
    return found


async def resolve_jury_roster(settings: Settings) -> List[Tuple[str, str]]:
    """Primary miners first, then discovered peers, capped by max_jury_size."""
    roster: List[Tuple[str, str]] = []
    seen = set()

    for name, url in zip(settings.names(), settings.base_urls()):
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        roster.append((name, url))

    if settings.discovery_enabled and len(roster) < settings.max_jury_size:
        for name, url in await discover_miners(settings):
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            roster.append((name, url))
            if len(roster) >= settings.max_jury_size:
                break

    return roster[: settings.max_jury_size]
