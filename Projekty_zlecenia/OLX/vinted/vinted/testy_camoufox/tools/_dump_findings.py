#!/usr/bin/env python3
# coding: utf-8
"""Temp helper: dump validator findings per requested scope (raporty root / subfolder)."""
import json
import subprocess
import sys

BS = chr(92)


def run_scan():
    r = subprocess.run(
        [sys.executable, "validate_confidence_tags.py", "--ci-only", "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(r.stdout)


def rel(f):
    return f.replace(BS, "/")


if __name__ == "__main__":
    scope = sys.argv[1] if len(sys.argv) > 1 else "root"
    d = run_scan()
    for f in d["findings"]:
        p = rel(f["file"])
        rest = p.split("/raporty/")[-1]
        parts = rest.split("/")
        if scope == "root" and len(parts) != 1:
            continue
        if scope != "root" and (len(parts) < 2 or parts[0] != scope):
            continue
        print("### %s | %s | L%s" % (rest, f["reason"], f["line"]))
        print(f["text"])
        print()
