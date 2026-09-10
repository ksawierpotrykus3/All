#!/usr/bin/env python3
# Temporary helper: generate per-file summary of validator findings.
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, r"vinted\testy_camoufox\tools")
import validate_confidence_tags as v  # noqa: E402

bases = [
    Path(r"vinted") / "testy_camoufox" / "docs" / "synthesis",
    Path(r"vinted") / "testy_camoufox" / "docs" / "reports",
    Path(r"vinted") / "raporty",
]

findings = []
for base in bases:
    if not base.exists():
        continue
    for md_path in base.rglob("*.md"):
        findings.extend(v.scan_file(md_path))

untagged = [f for f in findings if f.reason == "untagged_claim"]
unknown = [f for f in findings if f.reason == "unknown_tag"]
per_file = Counter(f.file for f in untagged)
unknown_per_file = Counter(f.file for f in unknown)

report = {
    "untagged_claims": len(untagged),
    "unknown_tags": len(unknown),
    "files_scanned": sum(1 for b in bases for _ in b.rglob("*.md")),
    "per_file_untagged": dict(per_file),
    "per_file_unknown": dict(unknown_per_file),
    "findings": [asdict(f) for f in findings],
}
out = Path(r"_audyt_tags.json")
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"zapisano: {out} | untagged={len(untagged)} unknown={len(unknown)}")
