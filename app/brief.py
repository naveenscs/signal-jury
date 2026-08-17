from __future__ import annotations

import re
from typing import Any, Dict, List


_YES = re.compile(r"\b(yes|likely|probable|will|expected to|more likely)\b", re.I)
_NO = re.compile(r"\b(no|unlikely|improbable|will not|won't|less likely)\b", re.I)


def _lean(text: str) -> str:
    if not text:
        return "unknown"
    y = len(_YES.findall(text))
    n = len(_NO.findall(text))
    if y == n:
        return "mixed"
    return "yes-leaning" if y > n else "no-leaning"


def build_brief(question: str, votes: List[Dict[str, Any]]) -> Dict[str, Any]:
    successes = [v for v in votes if v.get("status") == "success" and v.get("output")]
    leans = [_lean(v.get("output", "")) for v in successes]

    yes_n = leans.count("yes-leaning")
    no_n = leans.count("no-leaning")
    mixed_n = leans.count("mixed") + leans.count("unknown")

    if not successes:
        consensus = "no_quorum"
        summary = (
            "No live miner returned a usable answer. "
            "Check MINER_BASE_URLS and miner health — Track 3 requires live Telegraph miners."
        )
    elif yes_n > no_n and yes_n >= max(1, len(successes) // 2):
        consensus = "lean_yes"
        summary = f"Jury lean: YES-leaning ({yes_n}/{len(successes)} successful miners)."
    elif no_n > yes_n and no_n >= max(1, len(successes) // 2):
        consensus = "lean_no"
        summary = f"Jury lean: NO-leaning ({no_n}/{len(successes)} successful miners)."
    else:
        consensus = "split"
        summary = (
            f"Jury split or hedged ({yes_n} yes-lean / {no_n} no-lean / {mixed_n} mixed "
            f"of {len(successes)} successes)."
        )

    dissent = []
    if successes and consensus in ("lean_yes", "lean_no"):
        target = "yes-leaning" if consensus == "lean_yes" else "no-leaning"
        for v, lean in zip(successes, leans):
            if lean != target and lean != "unknown":
                dissent.append({"miner": v.get("name"), "lean": lean})

    return {
        "question": question,
        "consensus": consensus,
        "summary": summary,
        "miners_queried": len(votes),
        "miners_succeeded": len(successes),
        "leans": {
            "yes_leaning": yes_n,
            "no_leaning": no_n,
            "mixed_or_unknown": mixed_n,
        },
        "dissent": dissent,
        "telegraph_note": (
            "Answers come from live miner HTTPS endpoints (Telegraph supply). "
            "Heuristic lean is for UX only — not on-chain consensus."
        ),
    }
