# coding: utf-8
"""Znajdz endpoint zwracajacy liste pay_in_methods (id/code/enabled)."""
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
# szukamy: api.get/api.post z fraza pay_in lub payment_methods lub checkout payment
TERMS = ["pay_in_methods", "payment_methods", "payInMethods", "pay-in-method",
         "checkout/payment_methods", "payment_methods_list"]

seen = set()
for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        start = 0
        while True:
            idx = txt.find(term, start)
            if idx == -1:
                break
            # szukaj wstecz "get(" / "post(" / "'/" przed terminem (endpoint)
            ctx = txt[max(0, idx-200):idx+150]
            key = (f.name, idx // 500)  # dedup po fragmencie
            if key not in seen:
                seen.add(key)
                # wypisz tylko jesli wyglada na definicje endpointu
                if "api.get" in ctx or "api.post" in ctx or ".get(" in ctx or ".post(" in ctx or "i.api" in ctx or "u.get" in ctx:
                    print(f"\n===== {f.name} @ {idx} :: {term} =====")
                    print(ctx)
            start = idx + 1