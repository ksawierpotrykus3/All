"""F5f5: Pełna inspekcja wpisów 31, 85 z HAR (j3r4zw/v1/config i /consume)."""
import json
from pathlib import Path

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\wynik_spike_F5f5_j3r4zw.json")

d = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))["log"]["entries"]

# Sprawdzamy j3r4zw
items = []
for idx, e in enumerate(d):
    url = e.get("request", {}).get("url", "")
    if "j3r4zw" in url:
        items.append({
            "idx": idx,
            "url": url,
            "method": e["request"]["method"],
            "status": e["response"]["status"],
            "req_headers": [{"name": h["name"], "value": h["value"]} for h in e["request"]["headers"]],
            "req_body": e["request"].get("postData", {}).get("text", "")[:1500],
            "resp_headers": [{"name": h["name"], "value": h["value"]} for h in e["response"]["headers"]],
            "resp_body": e["response"]["content"].get("text", ""),
            "resp_size": e["response"]["content"].get("size"),
            "resp_transferSize": e["response"]["content"].get("_transferSize"),
            "resp_encoding": e["response"]["content"].get("encoding"),
            "resp_mime": e["response"]["content"].get("mimeType"),
        })

OUT.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Zapisano {len(items)} wpisów do {OUT}")
print(f"Rozmiar: {OUT.stat().st_size:,} B")
