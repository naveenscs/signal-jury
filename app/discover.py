from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .config import Settings

logger = logging.getLogger("signal-jury.discover")

# In-memory cache so we don't hit the node on every deliberate
_cache: Dict[str, Any] = {"at": 0.0, "miners": []}
_CACHE_TTL_SEC = 120.0

# Public SaaS APIs that sometimes appear in catalogs but are NOT Telegraph chat miners
_BLOCKED_HOST_FRAGMENTS = (
    "openweathermap.org",
    "weatherapi.com",
    "coingecko.com",
    "openrouter.ai",
    "api.openai.com",
    "api.groq.com",  # raw provider, not a miner base_url
    "api.together.xyz",
    "api.fireworks.ai",
    "googleapis.com",
    "binance.com",
    "coinbase.com",
    "alchemy.com",
    "infura.io",
)

_CHAT_INTENT_MARKERS = (
    "chat_completion",
    "chat-completion",
    "chat completion",
    "language_generation",
    "language generation",
    "text_generation",
    "text generation",
    "llm",
)


def _normalize_text(value: str) -> str:
    return (
        value.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
    )


def _host_blocked(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return any(b in host for b in _BLOCKED_HOST_FRAGMENTS)


def _intent_blob(item: Dict[str, Any]) -> str:
    intents = item.get("supported_intents") or item.get("intents") or []
    bits: List[str] = []
    if isinstance(intents, list):
        bits.extend(_normalize_text(str(x)) for x in intents)
    elif isinstance(intents, str):
        bits.append(_normalize_text(intents))
    for key in ("slug", "name", "description", "protocol", "kind"):
        val = item.get(key)
        if isinstance(val, str):
            bits.append(_normalize_text(val))
    semantics = item.get("semantics") or {}
    if isinstance(semantics, dict):
        bits.append(_normalize_text(str(semantics)))
    return " ".join(bits)


def _endpoint_blob(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("endpoints", "endpoint", "paths", "routes"):
        val = item.get(key)
        if val is None:
            continue
        parts.append(_normalize_text(str(val)))
    cfg = item.get("config") or item.get("yaml") or {}
    if isinstance(cfg, dict):
        for key in ("endpoints", "endpoint"):
            if key in cfg:
                parts.append(_normalize_text(str(cfg[key])))
    return " ".join(parts)


def _looks_chat_capable(item: Dict[str, Any], base_url: str) -> bool:
    """Strict: Telegraph CHAT_COMPLETION miners only — not raw SaaS APIs."""
    if _host_blocked(base_url):
        return False

    intents = _intent_blob(item)
    endpoints = _endpoint_blob(item)

    # Normalize markers the same way (underscores/hyphens → spaces)
    markers = [_normalize_text(m) for m in _CHAT_INTENT_MARKERS]
    has_chat_intent = any(m in intents for m in markers)
    has_chat_path = any(
        m in endpoints
        for m in (
            "chat",
            "v1 chat",
            "chat completions",
            "completions",
        )
    )

    name_slug = _normalize_text(f"{item.get('name', '')} {item.get('slug', '')}")
    if any(k in name_slug for k in ("openrouter", "openweather", "weatherapi", "coingecko")):
        return False

    # Knowledge Chatbot / similar: name alone is a strong signal
    if "chatbot" in name_slug or "chat completion" in name_slug:
        return True

    if not (has_chat_intent or has_chat_path):
        return False

    return True


def _extract_base_url(item: Dict[str, Any]) -> Optional[str]:
    for key in ("base_url", "baseUrl"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().rstrip("/")
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
        if val is not None and key == "id":
            return str(val)
    return base_url


def _normalize_list(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("integrations", "miners", "data", "items", "results"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if _extract_base_url(payload):
            return [payload]
    return []


def clear_discovery_cache() -> None:
    _cache["at"] = 0.0
    _cache["miners"] = []


async def discover_miners(settings: Settings) -> List[Tuple[str, str]]:
    """Return list of (name, base_url) from Telegraph node catalog."""
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
        if not _looks_chat_capable(item, base):
            continue
        key = base.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append((_extract_name(item, base), base))

    _cache["at"] = now
    _cache["miners"] = found
    logger.info("Discovered %s chat-capable miners from catalog", len(found))
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
