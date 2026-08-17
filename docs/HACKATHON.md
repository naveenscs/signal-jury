# Hackathon checklist — Track 3

Source: [Telegraph Hackathon](https://hackathon.telegraphprotocol.com/)

## Track 3 judging (Applications)

- [ ] Users acquired & activity
- [ ] Usage and adoption
- [ ] Creativity and usefulness
- [x] Must use Telegraph miners (live HTTPS miners; `hackathon.mocks = false`)
- [ ] Engagement on posts showcasing the project

## Before Track 3 window (~Aug 31)

- [x] App scaffold + README + design docs
- [ ] Host a public HTTPS demo (Render/Fly/etc.)
- [ ] Configure **≥2** live miner base URLs when available
- [ ] Verify Explorer / your miner receives traffic while demoing
- [ ] Prepare X thread with `@Telegraphprotoc` + demo GIF/screenshots
- [ ] Keep Track 1 miner (`groq-llama31-instant-miner`) online (demand feedback loop)

## Demo script (2 minutes)

1. Open Signal Jury UI.
2. Ask: “Will multi-agent systems become mainstream by 2027?”
3. Show parallel miner cards + brief.
4. Show `/api/deliberate` JSON with `"mocks": false`.
5. Link Explorer miner page for your Groq miner.

## Submit package

- Public GitHub repo (this project)
- Live demo URL
- Short README “Why / Run / Use”
- X posts + demo video or screenshots
- Optional: 1-page pitch (problem → Telegraph → Signal Jury → metrics)

## Out of scope for v0.1 (ok)

- Full x402 wallet flow
- WASM validator scripts (Track 2)
- CertSentinel / PKI agent (separate product idea)
