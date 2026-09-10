#!/usr/bin/env python3
# coding: utf-8
"""
validate_confidence_tags.py
============================
Skanuje dokumentację Markdown (.md) pod kątem twierdzeń wymagających oznaczenia
poziomu pewności. Cel: wykryć "gołe" twierdzenia bez tagu [UDOWODNIONE]/[HIPOTEZA]
zgodnie z AGENTS.md sekcja "Hierarchia prawdy".

Manifest tagów (canonical, see AGENTS.md L100-149):
    [UDOWODNIONE]      - potwierdzone twardymi dowodami (captured_requests.json)
    [POTWIERDZONE]     - potwierdzone analizą istniejących danych (HAR, logi)
    [DOMNIEMANE]       - ekspercka ocena / analiza kodu JS
    [HIPOTEZA]         - hipoteza bez testów / sprzeczne sygnały
    [NIEPOTWIERDZONE]  - niezweryfikowane, brak dowodów
    [NAKAZ]            - nakaz systemowy (nie claim, ale proceduralny)
    [SPRZECZNOŚĆ]      - wykryty konflikt w dokumentacji
    [MIT]              - obalone twierdzenie

Tryby:
    --strict    fail-exit na nieznanych tagach
    --ci-only   skanuj tylko docs/synthesis/, docs/reports/, raporty/
    --json      wynik jako JSON do CI

Użycie:
    python validate_confidence_tags.py                    # domyślny skan
    python validate_confidence_tags.py --ci-only --json   # tryb CI
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# Canonical tags (single source of truth: AGENTS.md L100-149)
KNOWN_TAGS: set[str] = {
    "UDOWODNIONE",
    "POTWIERDZONE",
    "DOMNIEMANE",
    "HIPOTEZA",
    "NIEPOTWIERDZONE",
    "NAKAZ",
    "SPRZECZNOŚĆ",
    "MIT",
    "FAKT",
}

# Metadata tags that appear in brackets but are NOT confidence markers.
# These are report headers/sections and should NOT trigger unknown_tag.
METADATA_TAGS: set[str] = {
    "WNIOSEK",
    "DANE",
    "ŹRÓDŁO",
    "DATA",
    "AGENT",
    "AKCJA",
    "KONFLIKT",
    "NEXT",
    "TODO",
    "PLAN",
    "ZADANIE",
    "BLOKER",
    "PRIORYTET",
    "CZAS",
    "ŚRODOWISKO",
    "ŚCIEŻKA",
    "DOKUMENTACJA",
}

# Patterns that strongly suggest a factual claim (Polish + English)
CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bjest\s+(?:to\s+)?[a-z]"),                    # "jest to X"
    re.compile(r"\bdzia[łl]a\b", re.IGNORECASE),                # "działa"
    re.compile(r"\bwymaga\s+[a-z]"),                            # "wymaga weryfikacji"
    re.compile(r"\bzweryfikowano\b", re.IGNORECASE),
    re.compile(r"\bz[\u0142e]amano\b", re.IGNORECASE),          # "złamano"
    re.compile(r"\bconfirmed\b", re.IGNORECASE),
    re.compile(r"\bverified\b", re.IGNORECASE),
    re.compile(r"\brequires\s+verification\b", re.IGNORECASE),
    re.compile(r"^\s*-\s+Endpointy\b"),                          # list "Endpointy: ..."
    re.compile(r"\bwynosi\b"),                                  # "wynosi 0.83 req/s"
    re.compile(r"\bResult\b.*\b\d{2,}\b"),                      # "Result: 403"
]

# Tags block (line where any tag is present)
TAG_REGEX = re.compile(r"\[([A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż]+)\]")

# Markdown links "[text](url)" / "[![alt](url)](url)" must not count as tags
MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")


@dataclass(slots=True)
class Finding:
    """A single location where a claim may lack confidence tagging."""
    file: str
    line: int
    text: str
    reason: str  # 'untagged_claim' | 'unknown_tag' | 'tag_present'


def scan_file(path: Path) -> list[Finding]:
    """Scan a single Markdown file for untagged claims and unknown tags."""
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings

    for line_no, line in enumerate(text.splitlines(), start=1):
        # Strip markdown links so "[ClassName](file://...)" is not read as a tag
        clean = MD_LINK_RE.sub("", line)
        # 1. Unknown tag detection (skip metadata tags — not confidence markers)
        for match in TAG_REGEX.finditer(clean):
            tag = match.group(1)
            if tag in KNOWN_TAGS or tag in METADATA_TAGS:
                continue
            findings.append(Finding(
                file=str(path),
                line=line_no,
                text=line.strip()[:120],
                reason="unknown_tag",
            ))

        # 2. Claim without tag — heuristic: line looks like a factual claim
        #    AND no known tag appears within ±1 lines
        if any(p.search(clean) for p in CLAIM_PATTERNS):
            # Look at +/-1 lines for a tag
            context = "\n".join(
                text.splitlines()[max(0, line_no - 2):line_no + 1]
            )
            if not TAG_REGEX.search(context):
                findings.append(Finding(
                    file=str(path),
                    line=line_no,
                    text=line.strip()[:120],
                    reason="untagged_claim",
                ))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--ci-only",
        action="store_true",
        help="Skanuj tylko docs/synthesis/, docs/reports/, raporty/ (szybki tryb CI)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero na unknown_tag (domyślnie: tylko raport)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Wynik jako JSON",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent  # .../vinted
    if args.ci_only:
        targets = [
            root / "testy_camoufox" / "docs" / "synthesis",
            root / "testy_camoufox" / "docs" / "reports",
            root / "raporty",
        ]
    else:
        targets = [
            root / "testy_camoufox" / "docs",
            root / "raporty",
            root.parent,  # root AGENTS.md, README.md
        ]

    all_findings: list[Finding] = []
    files_scanned = 0
    for base in targets:
        if not base.exists():
            continue
        for md_path in base.rglob("*.md"):
            all_findings.extend(scan_file(md_path))
            files_scanned += 1

    untagged = sum(1 for f in all_findings if f.reason == "untagged_claim")
    unknown = sum(1 for f in all_findings if f.reason == "unknown_tag")

    if args.json:
        payload = {
            "files_scanned": files_scanned,
            "untagged_claims": untagged,
            "unknown_tags": unknown,
            "findings": [asdict(f) for f in all_findings],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"[INFO] Przeskanowano {files_scanned} plików .md")
        print(f"[INFO] Znaleziono {untagged} twierdzeń bez oznaczenia pewności")
        print(f"[INFO] Znaleziono {unknown} nieznanych tagów")
        for f in all_findings[:20]:
            print(f"  [{f.reason}] {f.file}:{f.line} — {f.text}")

    if args.strict and unknown > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
