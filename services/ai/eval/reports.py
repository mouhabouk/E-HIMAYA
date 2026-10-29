"""Misses of the structured reading of a report by language variety (docs/phase-l/design-l5.md §4.1, model cards).

Reads every report of ``eval/reports.json`` with the configured local language model (Ollama, as in production) and
counts, per variety (Modern Standard Arabic, Derja in Arabic or Latin script, French):

* lives missed: the text says lives are at risk and the model says they are not (the false negative that costs most);
* category missed: the model's category differs from the expected one (the citizen's own choice is set to "other");
* invalid: the model's answer failed the JSON schema (the report then keeps the rules alone).

Each rate carries its 95 % Wilson interval and is flagged ``small`` below 30 reports.

    AI_OLLAMA_URL=http://localhost:11434 AI_LLM_MODEL=qwen3:1.7b python eval/reports.py --json eval/reports-results.json
"""

import argparse
import asyncio
import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.config import get_settings  # noqa: E402
from app.extract import extract  # noqa: E402

SMALL = 30
GROUPS = {
    "ar_msa": ("ar_msa",),
    "derja": ("ar_derja", "ar_latn"),
    "ar_derja": ("ar_derja",),
    "ar_latn": ("ar_latn",),
    "fr": ("fr",),
}


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def share(k: int, n: int) -> dict:
    return {"count": k, "of": n, "rate": round(k / n, 3) if n else None, "interval": wilson(k, n), "small": n < SMALL}


async def read_all(reports: list[dict]) -> list[dict]:
    out = []
    async with httpx.AsyncClient() as client:
        for report in reports:
            try:
                extraction, _ = await extract(report["text"], "other", client)
                out.append({**report, "got": extraction.model_dump(mode="json")})
            except ValueError:
                out.append({**report, "got": None})
    return out


def summary(rows: list[dict]) -> dict:
    valid = [r for r in rows if r["got"] is not None]
    at_risk = [r for r in valid if r["lives_at_risk"]]
    return {
        "reports": len(rows),
        "invalid": share(len(rows) - len(valid), len(rows)),
        "lives_missed": share(sum(not r["got"]["lives_at_risk"] for r in at_risk), len(at_risk)),
        "lives_false_alarm": share(
            sum(r["got"]["lives_at_risk"] for r in valid if not r["lives_at_risk"]),
            sum(not r["lives_at_risk"] for r in valid),
        ),
        "category_missed": share(sum(r["got"]["category"] != r["category"] for r in valid), len(valid)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reports", type=Path, default=HERE / "reports.json")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    reports = json.loads(args.reports.read_text())["reports"]
    rows = asyncio.run(read_all(reports))

    results: dict = {
        "model": get_settings().llm_model,
        "measured_on": date.today().isoformat(),
        "all": summary(rows),
        "varieties": {name: summary([r for r in rows if r["variety"] in members]) for name, members in GROUPS.items()},
        "confusions": Counter(
            f"{r['category']}→{r['got']['category']}"
            for r in rows
            if r["got"] is not None and r["got"]["category"] != r["category"]
        ).most_common(),
    }
    print(f"model: {results['model']}")
    print("\n| variety | reports | lives missed | category missed | invalid |")
    print("|---|---|---|---|---|")
    for name, s in [("all", results["all"]), *results["varieties"].items()]:
        lm, cm, inv = s["lives_missed"], s["category_missed"], s["invalid"]
        print(
            f"| {name} | {s['reports']} | {lm['count']}/{lm['of']} | {cm['count']}/{cm['of']} "
            f"| {inv['count']}/{inv['of']} |"
        )
    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
