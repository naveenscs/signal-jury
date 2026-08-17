# Signal Jury — Design Document

## 1. Problem

Telegraph Explorer already shows many forecast questions (“Will X happen?”) answered by **different** miners (chat, weather, news, etc.). Users and agents lack a simple product that:

1. Asks the **same** question to several **live** miners,
2. Shows agreement / dissent,
3. Produces a short decision-oriented brief.

Generic chat UIs hide the multi-miner nature of the protocol. Signal Jury makes the **supply layer visible**.

## 2. Goals

- Track 3 compliant: **live miners only** (no mock LLM).
- Demoable in &lt; 30 seconds.
- Extensible miner list via env config.
- Clear separation: transport to miners vs brief synthesis.

## 3. Non-goals

- Replacing Telegraph validators / WASM scripts.
- On-chain payment (x402) in v0.1 (can be added later).
- Claiming heuristic lean equals protocol Canonical_Score.

## 4. Components

| Component | Responsibility |
| --- | --- |
| `static/*` | Minimal UI for ask → brief → votes |
| `app/main.py` | FastAPI routes, health, deliberate |
| `app/miners.py` | Parallel HTTPS chat calls to miner base URLs |
| `app/brief.py` | Lightweight yes/no/mixed lean + summary |
| `app/config.py` | Env-based miner roster |

## 5. Request flow

```text
POST /api/deliberate { question }
  → for each configured miner base_url:
       try POST {base}/chat then /v1/chat/completions
       body: OpenAI-style messages (model may be miner slug; miners should map to real LLM)
  → collect success/error + latency + output text
  → build_brief()
  → return { brief, votes, hackathon: { mocks: false } }
```

## 6. Alignment with protocol incentives

Per Telegraph transmissions on **non-response** ([example](https://x.com/Telegraphprotoc/status/2089212150548185354)):

- Missing / malformed miner answers are punished at epoch level.
- Signal Jury surfaces **errors explicitly** instead of inventing text.
- Successful answers remain visible for humans to compare quality.

## 7. Security & ops

- Server-side calls only (browser does not hold miner secrets).
- Timeouts per miner (`MINER_TIMEOUT_SECONDS`).
- No private keys in repo.
- CORS open for hackathon demos; tighten for production.

## 8. Future extensions

- Discover miners from dispatcher `/miner-dispatcher/integrations`.
- Optional Alexandria / MCP `tg_engine_ask` path.
- x402 paid calls when Track 3 tooling requires it.
- Embeddable brief permalinks + usage analytics for judging “users & activity”.
