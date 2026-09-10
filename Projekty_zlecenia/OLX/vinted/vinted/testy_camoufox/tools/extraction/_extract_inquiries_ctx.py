# coding: utf-8
"""Wyciąga pełny kontekst nowego backendu messaging/main/inquiries."""
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
TERMS = ["messaging/main/inquiries", "svc_messaging_phase_1_v2", "web_new_messaging_backend",
         "conversation_id", "transaction_id", "readAfterWriteTokenResponseBodyInterceptor",
         "withInquiryDuration", "initiator"]

for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        idx = txt.find(term)
        if idx != -1:
            start = max(0, idx - 400)
            end = min(len(txt), idx + 700)
            print(f"\n===== {f.name} :: {term} =====")
            print(txt[start:end])