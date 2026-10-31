"""Summaries and before/after comparison of infra/security/audit.sh runs (review point 15, phase 4).

    python3 infra/security/compare.py --summarize audit-before > audit-before/summary.json
    python3 infra/security/compare.py audit-before audit-after > hardening.json

Standard library only, so it runs on the server being measured.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def lynis(d: Path) -> dict | None:
    f = d / "lynis-report.dat"
    if not f.exists():
        return None
    kv: dict[str, list[str]] = {}
    for line in f.read_text(errors="replace").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            kv.setdefault(k, []).append(v)

    def items(key: str) -> list[dict]:
        out = []
        for v in kv.get(key, []):
            parts = v.split("|")
            out.append({"id": parts[0], "text": parts[1] if len(parts) > 1 else ""})
        return out

    return {
        "index": int(kv.get("hardening_index", ["0"])[0]),
        "tests": int(kv.get("lynis_tests_done", ["0"])[0]),
        "warnings": items("warning[]"),
        "suggestions": items("suggestion[]"),
        "version": kv.get("lynis_version", [""])[0],
        "os": kv.get("os_fullname", [""])[0],
    }


def nmap(f: Path) -> list[dict] | None:
    if not f.exists():
        return None
    ports = []
    for p in ET.parse(f).getroot().iter("port"):
        st = p.find("state")
        if st is None or st.get("state") not in ("open", "open|filtered"):
            continue
        sv = p.find("service")
        ports.append(
            {
                "port": int(p.get("portid")),
                "proto": p.get("protocol"),
                "state": st.get("state"),
                "service": sv.get("name", "") if sv is not None else "",
                "product": " ".join(
                    x
                    for x in ((sv.get("product") or ""), (sv.get("version") or ""))
                    if x
                )
                if sv is not None
                else "",
            }
        )
    return sorted(ports, key=lambda x: (x["proto"], x["port"]))


def testssl(f: Path) -> dict | None:
    if not f.exists():
        return None
    data = json.loads(f.read_text() or "[]")
    sev = {s: [] for s in SEVERITIES}
    protocols = []
    for x in data:
        s = x.get("severity", "")
        if (
            x.get("id", "").startswith(("SSLv", "TLS1"))
            and "offered" in x.get("finding", "")
            and "not offered" not in x.get("finding", "")
        ):
            protocols.append(x["id"].replace("_", "."))
        if s in sev:
            sev[s].append({"id": x.get("id"), "finding": x.get("finding", "")[:200]})
    return {
        "protocols": protocols,
        "counts": {s: len(v) for s, v in sev.items()},
        "findings": sev,
    }


def zap(f: Path) -> dict | None:
    if not f.exists():
        return None
    data = json.loads(f.read_text())
    risk: dict[str, int] = {}
    for site in data.get("site", []):
        for a in site.get("alerts", []):
            r = re.sub(r" \(.*", "", a.get("riskdesc", "Informational"))
            risk[r] = risk.get(r, 0) + 1
    return {"alerts_by_risk": risk}


def summarize(d: Path) -> dict:
    return {
        "label": d.name,
        "lynis": lynis(d),
        "nmap_tcp": nmap(d / "nmap-tcp.xml"),
        "nmap_udp": nmap(d / "nmap-udp.xml"),
        "testssl": testssl(d / "testssl.json"),
        "zap": zap(d / "zap-baseline.json"),
    }


def compare(a: dict, b: dict) -> dict:
    out: dict = {"before": a, "after": b}
    if a["lynis"] and b["lynis"]:
        key = lambda x: (x["id"], x["text"])
        sa = {key(x) for x in a["lynis"]["suggestions"] + a["lynis"]["warnings"]}
        sb = {key(x) for x in b["lynis"]["suggestions"] + b["lynis"]["warnings"]}
        out["lynis"] = {
            "index": [a["lynis"]["index"], b["lynis"]["index"]],
            "resolved": [{"id": i, "text": t} for i, t in sorted(sa - sb)],
            "remaining": [{"id": i, "text": t} for i, t in sorted(sa & sb)],
            "new": [{"id": i, "text": t} for i, t in sorted(sb - sa)],
        }
    for k in ("nmap_tcp", "nmap_udp"):
        if a[k] is not None and b[k] is not None:
            pa = {(x["proto"], x["port"]) for x in a[k]}
            pb = {(x["proto"], x["port"]) for x in b[k]}
            out[k] = {
                "closed": sorted(pa - pb),
                "opened": sorted(pb - pa),
                "kept": sorted(pa & pb),
            }
    return out


def main() -> int:
    if sys.argv[1] == "--summarize":
        print(json.dumps(summarize(Path(sys.argv[2])), ensure_ascii=False, indent=1))
        return 0
    load = lambda p: (
        json.loads((Path(p) / "summary.json").read_text())
        if (Path(p) / "summary.json").exists()
        else summarize(Path(p))
    )
    print(
        json.dumps(
            compare(load(sys.argv[1]), load(sys.argv[2])), ensure_ascii=False, indent=1
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
