#!/usr/bin/env python3
"""Dependency audit (phase 10 §3): pip-audit on every Python lock, npm audit on the web apps.

  scripts/dep_audit.py            # every service and app
  scripts/dep_audit.py python     # only the Python locks
  scripts/dep_audit.py npm        # only the web apps

A finding fails unless .github/audit-allowlist.yml lists its id with a reason and an expiry date not yet passed.
Needs `uv` (pip-audit runs with `uvx`) and `npm`.
"""

import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / ".github" / "audit-allowlist.yml"
PYTHON = ["services/api", "services/ai", "services/vision", "services/notify-sim"]
NPM = ["apps/dashboard", "apps/portal"]
PIP_AUDIT = "pip-audit==2.9.0"


def allowlist(today: dt.date) -> tuple[set[str], list[str]]:
    """Ids still allowed, and the problems of the file (missing reason, expired entries)."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    if ALLOWLIST.exists():
        for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            m = re.match(r"^\s*(-\s+)?(\w+):\s*(.*)$", raw)
            if not m:
                continue
            if m[1] and current:
                entries.append(current)
                current = {}
            current[m[2]] = m[3].strip().strip('"')
        if current:
            entries.append(current)
    allowed: set[str] = set()
    notes: list[str] = []
    for e in entries:
        rid = e.get("id", "")
        try:
            expires = dt.date.fromisoformat(e.get("expires", ""))
        except ValueError:
            notes.append(f"{rid}: no valid expiry date, ignored")
            continue
        if not e.get("reason"):
            notes.append(f"{rid}: no reason, ignored")
        elif expires < today:
            notes.append(f"{rid}: expired on {expires}, fails again")
        else:
            allowed.add(rid)
    return allowed, notes


def python_findings(service: str) -> list[tuple[str, str, str]]:
    with tempfile.NamedTemporaryFile("w+", suffix=".txt") as req:
        subprocess.run(
            ["uv", "export", "--frozen", "--no-hashes", "--no-dev", "--all-extras", "--format", "requirements-txt",
             "-o", req.name],
            cwd=ROOT / service, check=True, capture_output=True,
        )
        out = subprocess.run(
            ["uvx", "--from", PIP_AUDIT, "pip-audit", "-r", req.name, "--no-deps", "--disable-pip",
             "--progress-spinner", "off", "-f", "json"],
            capture_output=True, text=True, check=False,
        )
    if not out.stdout.strip().startswith("{"):
        raise RuntimeError(f"pip-audit failed for {service}: {out.stderr.strip()[-400:]}")
    found = []
    for dep in json.loads(out.stdout)["dependencies"]:
        for v in dep.get("vulns", []):
            ids = [v["id"], *v.get("aliases", [])]
            found.append((dep["name"], dep["version"], " / ".join(ids)))
    return found


def npm_findings(app: str) -> list[tuple[str, str, str]]:
    out = subprocess.run(
        ["npm", "audit", "--omit=dev", "--audit-level=high", "--json"],
        cwd=ROOT / app, capture_output=True, text=True, check=False,
    )
    data = json.loads(out.stdout or "{}")
    found = []
    for name, vuln in data.get("vulnerabilities", {}).items():
        if vuln.get("severity") not in ("high", "critical"):
            continue
        for via in vuln.get("via", []):
            if isinstance(via, dict):
                ghsa = via.get("url", "").rsplit("/", 1)[-1]
                found.append((name, vuln.get("range", "?"), ghsa or via.get("title", "?")))
    return found


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    allowed, notes = allowlist(dt.date.today())
    for note in notes:
        print(f"allow list: {note}")
    failed = 0
    targets = ([("python", s) for s in PYTHON] if which in ("all", "python") else []) + (
        [("npm", a) for a in NPM] if which in ("all", "npm") else []
    )
    for kind, target in targets:
        findings = python_findings(target) if kind == "python" else npm_findings(target)
        open_ = [f for f in findings if not any(i in allowed for i in f[2].split(" / "))]
        print(f"{target}: {len(findings)} finding(s), {len(findings) - len(open_)} allow-listed")
        for name, version, ids in open_:
            print(f"  FAIL {name} {version}: {ids}")
        failed += len(open_)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
