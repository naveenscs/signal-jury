"""Telegraph Engine consume client (Track 3) — POST /engine/v1/ask."""

from __future__ import annotations

import time
from typing import Any, Dict

import httpx

from .config import Settings


def _extract_engine_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        return str(payload)

    result = payload.get("result")
    if isinstance(result, str) and result.strip():
        return result.strip()
    if isinstance(result, dict):
        for key in ("output", "answer", "text", "content", "message"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"].strip()

    for key in ("output", "answer", "text", "content"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return ""


async def engine_ask(settings: Settings, query: str) -> Dict[str, Any]:
    """
    Auto-routed: POST {engine}/engine/v1/ask  {"query": "..."}.

    Optional direct: POST {engine}/engine/v1/ask/{minerId}
      {"method":"POST","endpoint":"/v1/chat/completions","payload":{...}}

    Docs host: https://devnode.telegraphprotocol.com
    Public engine may return HTTP 402 (x402); callers fall back to direct miners.
    """
    base = settings.telegraph_engine_url.rstrip("/")
    timeout = httpx.Timeout(settings.miner_timeout_seconds)
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if settings.telegraph_payment_header.strip():
        headers["X-PAYMENT"] = settings.telegraph_payment_header.strip()

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        auto_url = f"{base}/engine/v1/ask"
        try:
            resp = await client.post(auto_url, json={"query": query}, headers=headers)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}

            if resp.is_success:
                text = _extract_engine_text(data)
                if text:
                    return {
                        "ok": True,
                        "consume_path": "engine_ask",
                        "url": auto_url,
                        "status_code": resp.status_code,
                        "elapsed_ms": elapsed_ms,
                        "output": text,
                        "miner_id": data.get("miner_id") if isinstance(data, dict) else None,
                        "miner_name": data.get("miner_name") if isinstance(data, dict) else None,
                        "intent": data.get("intent") if isinstance(data, dict) else None,
                        "raw": data,
                        "error": None,
                    }
            if resp.status_code == 402:
                return {
                    "ok": False,
                    "consume_path": "engine_ask",
                    "url": auto_url,
                    "status_code": 402,
                    "elapsed_ms": elapsed_ms,
                    "output": "",
                    "raw": data,
                    "error": "engine_ask_payment_required_402",
                }
            auto_err = f"HTTP {resp.status_code}: {str(data)[:300]}"
        except Exception as exc:  # noqa: BLE001
            auto_err = str(exc)
            elapsed_ms = int((time.perf_counter() - started) * 1000)

        miner_id = settings.telegraph_miner_id.strip()
        if not miner_id:
            return {
                "ok": False,
                "consume_path": "engine_ask",
                "url": auto_url,
                "status_code": None,
                "elapsed_ms": elapsed_ms,
                "output": "",
                "raw": None,
                "error": auto_err,
            }

        direct_url = f"{base}/engine/v1/ask/{miner_id}"
        body = {
            "method": "POST",
            "endpoint": "/v1/chat/completions",
            "payload": {
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 512,
                "temperature": 0.3,
            },
        }
        try:
            resp = await client.post(direct_url, json=body, headers=headers)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}
            if resp.is_success:
                text = _extract_engine_text(data)
                if text:
                    return {
                        "ok": True,
                        "consume_path": "engine_ask_direct",
                        "url": direct_url,
                        "status_code": resp.status_code,
                        "elapsed_ms": elapsed_ms,
                        "output": text,
                        "miner_id": miner_id,
                        "miner_name": data.get("miner_name") if isinstance(data, dict) else None,
                        "raw": data,
                        "error": None,
                    }
            return {
                "ok": False,
                "consume_path": "engine_ask_direct",
                "url": direct_url,
                "status_code": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "output": "",
                "raw": data,
                "error": f"auto_failed={auto_err}; direct=HTTP {resp.status_code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "consume_path": "engine_ask_direct",
                "url": direct_url,
                "status_code": None,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "output": "",
                "raw": None,
                "error": f"auto_failed={auto_err}; direct={exc}",
            }
