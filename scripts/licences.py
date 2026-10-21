#!/usr/bin/env python3
"""Licence check of the shipped dependencies (phase 10 §6.4, V22).

  scripts/licences.py python <requirements.txt>...   # from `uv export --frozen --no-dev` (PyPI metadata)
  scripts/licences.py npm <app dir>...               # production tree of node_modules (`npm ls --omit=dev`)

A dependency passes when its licence (SPDX expression, or the licences it declares: any one of them may be chosen)
is on the allow list below, or when it is listed in .github/licence-exceptions.yml with a reason. A copyleft or
unknown licence fails. The result is printed as a table; exit 1 on any failure.
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / ".github" / "licence-exceptions.yml"

ALLOWED = {
    "MIT",
    "MIT-0",
    "MIT-CMU",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "ISC",
    "MPL-2.0",
    "PSF-2.0",
    "Python-2.0",
    "Unlicense",
    "0BSD",
    "CC0-1.0",
    "BlueOak-1.0.0",
    "Zlib",
    "HPND",
    # Weak copyleft used as a dynamically linked library only (never modified or statically linked).
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MPL-1.1",
}
# Trove classifiers and free-text names, mapped to SPDX.
ALIASES = {
    "MIT License": "MIT",
    "BSD License": "BSD-3-Clause",
    "Apache Software License": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "ISC License (ISCL)": "ISC",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Mozilla Public License 1.1 (MPL 1.1)": "MPL-1.1",
    "Python Software Foundation License": "PSF-2.0",
    "The Unlicense (Unlicense)": "Unlicense",
    "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1-or-later",
    "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
    "GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0-or-later",
    "GNU General Public License v2 or later (GPLv2+)": "GPL-2.0-or-later",
    "GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
    "GNU Affero General Public License v3": "AGPL-3.0-only",
    "Historical Permission Notice and Disclaimer (HPND)": "HPND",
    "zlib/libpng License": "Zlib",
    "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": "CC0-1.0",
    "BSD": "BSD-3-Clause",
    "3-Clause BSD License": "BSD-3-Clause",
    "MIT-style": "MIT",
}


def exceptions() -> dict[str, str]:
    """``package: reason`` from the exceptions file (a list of ``- package: …`` / ``reason: …`` entries)."""
    found: dict[str, str] = {}
    if not EXCEPTIONS.exists():
        return found
    current: dict[str, str] = {}
    for raw in EXCEPTIONS.read_text(encoding="utf-8").splitlines():
        line = raw.split(" #")[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s*(-\s+)?(\w+):\s*(.*)$", line)
        if not m:
            continue
        if m[1] and current:
            found[current.get("package", "")] = current.get("reason", "")
            current = {}
        current[m[2]] = m[3].strip().strip('"')
    if current:
        found[current.get("package", "")] = current.get("reason", "")
    return found


def _spdx(name: str) -> str:
    name = name.strip()
    name = re.sub(r"^License :: (OSI Approved :: )?", "", name)
    return ALIASES.get(name, name)


def acceptable(licences: list[str]) -> bool:
    """Any declared licence (or OR branch) that is fully allowed (every AND term) is enough."""
    for declared in licences:
        for branch in re.split(r"\s+OR\s+", declared.strip("() ")):
            terms = [_spdx(t.strip("() ")) for t in re.split(r"\s+AND\s+", branch)]
            if terms and all(t in ALLOWED for t in terms):
                return True
    return False


def python_licences(name: str, version: str) -> list[str]:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 (fixed https host)
        info = json.load(r)["info"]
    if info.get("license_expression"):
        return [info["license_expression"]]
    classifiers = [c for c in info.get("classifiers", []) if c.startswith("License ::")]
    licences = [_spdx(c) for c in classifiers if _spdx(c) not in ("OSI Approved", "Other/Proprietary License")]
    if licences:
        return licences
    text = (info.get("license") or "").strip()
    return [text.splitlines()[0][:60]] if text else []


def python_packages(path: Path) -> list[tuple[str, str]]:
    packages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", line.strip())
        if m:
            packages.append((m[1], m[2]))
    return packages


def npm_packages(app: Path) -> list[tuple[str, str, list[str]]]:
    out = subprocess.run(
        ["npm", "ls", "--omit=dev", "--all", "--parseable", "--long"],
        cwd=app,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    found = []
    for line in out.splitlines()[1:]:
        path = Path(line.split(":")[0])
        manifest = path / "package.json"
        if not manifest.exists():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        lic = data.get("license") or data.get("licenses") or []
        if isinstance(lic, dict):
            lic = lic.get("type", "")
        if isinstance(lic, list):
            lic = [x.get("type", "") if isinstance(x, dict) else str(x) for x in lic]
        found.append((data.get("name", path.name), data.get("version", "?"), lic if isinstance(lic, list) else [lic]))
    return sorted(set((n, v, tuple(lic)) for n, v, lic in found))  # type: ignore[misc]


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("python", "npm"):
        print(__doc__, file=sys.stderr)
        return 2
    allowed_by_exception = exceptions()
    rows: list[tuple[str, str, str, str]] = []
    if sys.argv[1] == "python":
        seen: set[tuple[str, str]] = set()
        for arg in sys.argv[2:]:
            for name, version in python_packages(Path(arg)):
                if (name.lower(), version) in seen:
                    continue
                seen.add((name.lower(), version))
                try:
                    licences = python_licences(name, version)
                except Exception as exc:  # network or metadata error: unknown, fails below
                    licences = [f"<error: {type(exc).__name__}>"]
                rows.append((name, version, " | ".join(licences) or "<none>", _verdict(name, licences, allowed_by_exception)))
    else:
        for arg in sys.argv[2:]:
            for name, version, licences in npm_packages(Path(arg)):
                rows.append((name, version, " | ".join(licences) or "<none>", _verdict(name, list(licences), allowed_by_exception)))
    failed = [r for r in rows if r[3] == "FAIL"]
    for name, version, licences, verdict in sorted(rows, key=lambda r: (r[3] != "FAIL", r[0].lower())):
        if verdict != "ok":
            print(f"{verdict:9} {name}=={version}  {licences}")
    print(f"{len(rows)} packages, {len(failed)} failing, {sum(r[3] == 'exception' for r in rows)} by exception")
    return 1 if failed else 0


def _verdict(name: str, licences: list[str], allowed_by_exception: dict[str, str]) -> str:
    if acceptable(licences):
        return "ok"
    if name in allowed_by_exception or name.lower() in allowed_by_exception:
        return "exception"
    return "FAIL"


if __name__ == "__main__":
    sys.exit(main())
