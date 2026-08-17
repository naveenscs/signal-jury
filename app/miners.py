from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import Settings
from .discover import resolve_jury_roster


def _extract_output(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return str(payload)

    for key in ("output", "result", "answer", "text", "content"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return msg["content"].strip()

    return ""


async def _post_chat(
    client: httpx.AsyncClient,
    base_url: str,
    path: str,
    question: str,
    model_hint: str,
) -> Dict[str, Any]:
    url = f"{base_url}{path}"
    body = {
        "model": model_hint,
        "messages": [{"role": "user", "content": question}],
        "max_tokens": 512,
        "temperature": 0.3,
        "stream": False,
    }
    started = time.perf_counter()
    resp = await client.post(url, json=body)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    data: Any
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text[:2000]}

    return {
        "url": url,
        "status_code": resp.status_code,
        "elapsed_ms": elapsed_ms,
        "ok": resp.is_success,
        "payload": data,
        "output": _extract_output(data) if resp.is_success else "",
        "error": None if resp.is_success else str(data)[:500],
    }


async def query_miner(
    client: httpx.AsyncClient,
    *,
    name: str,
    base_url: str,
    paths: List[str],
    question: str,
    slug_hint: str,
) -> Dict[str, Any]:
    last_error: Optional[str] = None
    for path in paths:
        try:
            result = await _post_chat(client, base_url, path, question, slug_hint)
            if result["ok"] and result["output"]:
                return {
                    "name": name,
                    "base_url": base_url,
                    "path_used": path,
                    "status": "success",
                    "elapsed_ms": result["elapsed_ms"],
                    "output": result["output"],
                    "raw": result["payload"],
                }
            last_error = result.get("error") or f"HTTP {result['status_code']}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return {
        "name": name,
        "base_url": base_url,
        "path_used": None,
        "status": "error",
        "elapsed_ms": 0,
        "output": "",
        "error": last_error or "all chat paths failed",
        "raw": None,
    }


async def query_jury(
    settings: Settings,
    question: str,
    roster: Optional[List[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Query all roster miners in parallel (asyncio.gather)."""
    if roster is None:
        roster = await resolve_jury_roster(settings)
    paths = settings.chat_paths()
    timeout = httpx.Timeout(settings.miner_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            query_miner(
                client,
                name=name,
                base_url=url,
                paths=paths,
                question=question,
                slug_hint=name.lower().replace(" ", "-"),
            )
            for name, url in roster
        ]
        return list(await asyncio.gather(*tasks))
