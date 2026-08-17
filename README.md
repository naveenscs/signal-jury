# Signal Jury

**Telegraph Protocol Hackathon Season I — Track 3 (Applications & Agents)**

Signal Jury asks a forecast / decision question to **multiple live Telegraph miners in parallel**, then returns a short **jury brief** (consensus lean + dissent) plus each miner’s raw answer.

> Latest related protocol note ([@Telegraphprotoc](https://x.com/Telegraphprotoc/status/2089212150548185354)): miners that **fail to answer** are scored zero and can lose **epoch routing eligibility**. This app always expects miners to return a real completion — it never substitutes mocks.

## Why this is required (Track 3)

| Track 3 criterion | How Signal Jury addresses it |
| --- | --- |
| Must use Telegraph miners | Calls real miner HTTPS `/chat` or `/v1/chat/completions` — **no mocked inference** |
| Creativity & usefulness | Multi-miner “jury” for uncertain “Will X…?” questions (common on Explorer) |
| Users & activity | Simple web UI: ask → brief → shareable narrative for demos / X |
| Engagement | Built to demo live disagreement / agreement across supply nodes |

It also creates **demand** on Track 1 miners (including `groq-llama31-instant-miner`).

## Architecture (short)

```text
Browser UI  →  Signal Jury API  →  Miner A (live)
                              ├→  Miner B (live)
                              └→  Miner C (live)
                     ↓
              Heuristic brief (agree / split / no quorum)
```

## Quick start

```bash
cd signal-jury
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edit MINER_BASE_URLS
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open http://127.0.0.1:8080

### Configure live miners

In `.env`:

```env
MINER_BASE_URLS=https://telegraph-miner-node.onrender.com,https://OTHER-LIVE-MINER
MINER_NAMES=Telegraph Groq LPU Miner,Other Miner
```

Add only **public HTTPS miners** that accept OpenAI-style chat POSTs (as registered on Telegraph).

## How to use

1. Open the UI.
2. Enter a forecast-style question (or use the sample).
3. Click **Convene jury**.
4. Read the **Jury brief**, then each miner card (success/error, latency, answer).

API:

```bash
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:8080/api/miners
curl -sS -X POST http://127.0.0.1:8080/api/deliberate \
  -H 'Content-Type: application/json' \
  -d '{"question":"Will multi-agent systems become mainstream by 2027?"}'
```

Interactive OpenAPI: http://127.0.0.1:8080/docs

## Hackathon notes

- Track 3 window (Season I): applications build on live miners after Track 1/2 — see [hackathon.telegraphprotocol.com](https://hackathon.telegraphprotocol.com/).
- Docs: [docs/DESIGN.md](docs/DESIGN.md), [docs/HACKATHON.md](docs/HACKATHON.md), [docs/X_POSTS.md](docs/X_POSTS.md).
- This app’s lean/consensus is a **UX heuristic**, not Telegraph’s on-chain stake-weighted median.

## Note: Track 1 miner model migration (Aug 16, 2026)

Groq shut down `llama-3.1-8b-instant` on **2026-08-16** ([deprecations](https://console.groq.com/docs/deprecations)).  
If your miner returns `model_not_found`, set Render env:

```env
GROQ_MODEL=openai/gpt-oss-20b
```

Then restart. Signal Jury will work again once the miner answers 200.

## Deploy (optional)

Any host that can reach miner URLs (Render, Fly, VPS):

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set the same `MINER_BASE_URLS` in the host environment.

## License

MIT — see [LICENSE](LICENSE).
