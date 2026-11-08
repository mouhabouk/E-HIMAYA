#!/usr/bin/env python3
"""Merges e-Himaya's settings into /etc/docker/daemon.json without removing any key already there.

Usage: docker-daemon-merge.py <daemon.json> [--dns 10.0.0.1,1.1.1.1]
Prints the merged JSON on stdout; the caller backs up, validates (dockerd --validate) and installs it.

- Log rotation: added only when no log setting exists (an administrator's own values are kept).
- DNS: written only when --dns is given and not empty. The list replaces the "dns" key, in the given order: on a
  local network the internal resolver must come FIRST, because a public resolver answers NXDOMAIN for internal names
  (*.ehimaya.lan) and the next server is then never asked.
"""

import ipaddress
import json
import sys


def main() -> int:
    path = sys.argv[1]
    dns: list[str] = []
    if "--dns" in sys.argv:
        raw = sys.argv[sys.argv.index("--dns") + 1]
        dns = [d.strip() for d in raw.replace(" ", ",").split(",") if d.strip()]
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
        current = json.loads(text) if text else {}
    except FileNotFoundError:
        current = {}
    except json.JSONDecodeError as e:
        print(f"{path}: JSON غير صالح ({e}); صحّحه يدويا أولا", file=sys.stderr)
        return 2
    if not isinstance(current, dict):
        print(f"{path}: يجب أن يكون كائن JSON", file=sys.stderr)
        return 2
    merged = dict(current)
    if "log-driver" not in merged and "log-opts" not in merged:
        merged["log-driver"] = "json-file"
        merged["log-opts"] = {"max-size": "50m", "max-file": "5"}
    if dns:
        for d in dns:
            try:
                ip = ipaddress.ip_address(d)
            except ValueError:
                print(f"عنوان DNS غير صالح: {d}", file=sys.stderr)
                return 2
            if ip.is_loopback:
                print(f"{d}: عنوان حلقة محلية لا تصله الحاويات؛ استعمل عنوان خادم الأسماء نفسه", file=sys.stderr)
                return 2
        merged["dns"] = list(dict.fromkeys(dns))
    json.dump(merged, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
