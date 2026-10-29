"""Accuracy of the reading of a commander's text (AI5a, docs/phase-ai5/design-ai5.md §6, model card).

Reads every text of the two sets with the rules alone, the local language model alone and the combination
used in production, and counts per variety (Modern Standard Arabic, Derja in Arabic or Latin script, French):

* intent: question or order, right;
* action: the action of an order right (dispatch, alert, escalate, volunteers, call, route, note);
* exact: intent, action, resource kind, count and level all right — the card the commander sees needs no edit;
* invalid: the model's answer failed the JSON schema (production then shows the rules' reading).

Two sets: ``orders.json`` (development: the lexicon and the prompt were tuned on it) and ``orders-heldout.json``
(written before any measure on it and never used for tuning). The held-out figures are the ones the model card states.

Each rate carries its 95 % Wilson interval and is flagged ``small`` below 30 texts. Without ``--ollama`` only the rules
are measured.

    python eval/orders.py --ollama http://localhost:11434 --model qwen3:1.7b --json eval/orders-results.json
"""

import argparse
import asyncio
import json
import math
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.modules.decision import orders  # noqa: E402
from app.modules.decision.llm import LlmRejected, OllamaClient  # noqa: E402

SMALL = 30
GROUPS = {
    "all": ("ar_msa", "ar_derja", "ar_latn", "fr"),
    "ar_msa": ("ar_msa",),
    "derja": ("ar_derja", "ar_latn"),
    "fr": ("fr",),
}
SETS = {"heldout": "orders-heldout.json", "dev": "orders.json"}
FIELDS = ("intent", "action", "resource_kind", "count", "level")


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def share(k: int, n: int) -> dict:
    return {"count": k, "of": n, "rate": round(k / n, 3) if n else None, "interval": wilson(k, n), "small": n < SMALL}


def summary(rows: list[dict], reader: str) -> dict:
    valid = [r for r in rows if r[reader] is not None]
    order_rows = [r for r in valid if r["intent"] == "order"]
    return {
        "texts": len(rows),
        "invalid": share(len(rows) - len(valid), len(rows)),
        "intent": share(sum(r[reader]["intent"] == r["intent"] for r in valid), len(valid)),
        "action": share(sum(r[reader]["action"] == r["action"] for r in order_rows), len(order_rows)),
        "exact": share(sum(all(r[reader][f] == r[f] for f in FIELDS) for r in valid), len(valid)),
    }


async def read_all(items: list[dict], llm: OllamaClient | None) -> list[dict]:
    out = []
    for item in items:
        rules = orders.read_rules(item["text"])
        row = {**item, "rules": orders.finish(orders.Reading(**{**rules.as_dict()})).as_dict()}
        row["model"] = row["combined"] = None
        if llm is not None:
            try:
                model = await orders.read_model(item["text"], llm)
                row["model"] = orders.finish(orders.Reading(**model.as_dict())).as_dict()
                row["combined"] = orders.finish(orders.combine(rules, model)).as_dict()
            except LlmRejected:
                row["combined"] = row["rules"]
        out.append(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama", help="Ollama URL; without it only the rules are measured")
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--misses", action="store_true", help="print every text a reader got wrong")
    args = parser.parse_args()
    llm = OllamaClient(args.ollama, args.model, 300, 4096) if args.ollama else None
    readers = ("rules", "model", "combined") if llm else ("rules",)
    result: dict = {"date": date.today().isoformat(), "model": args.model if llm else None, "sets": {}}
    print("| set | reader | group | texts | intent | action | exact | invalid |")
    print("|---|---|---|---|---|---|---|---|")
    misses = []
    texts = {name: json.loads((HERE / file).read_text(encoding="utf-8"))["orders"] for name, file in SETS.items()}

    async def read_sets() -> dict[str, list[dict]]:
        # One event loop for every set: the model's HTTP client belongs to the loop it first ran in.
        return {name: await read_all(items, llm) for name, items in texts.items()}

    read = asyncio.run(read_sets())
    for name, rows in read.items():
        result["sets"][name] = {
            reader: {g: summary([r for r in rows if r["variety"] in v], reader) for g, v in GROUPS.items()}
            for reader in readers
        }
        for reader, groups in result["sets"][name].items():
            for group, m in groups.items():
                cells = [f"{m[k]['rate']} {m[k]['interval']}" for k in ("intent", "action", "exact", "invalid")]
                print(f"| {name} | {reader} | {group} | {m['texts']} | " + " | ".join(cells) + " |")
        for reader in readers:
            for r in rows:
                got = r[reader]
                if got is None or any(got[f] != r[f] for f in FIELDS):
                    want = {f: r[f] for f in FIELDS}
                    misses.append(f"{name} {reader} {r['id']} {r['text']}\n   want {want}\n   got  {got}")
    if args.misses:
        print("\n".join(misses))
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
