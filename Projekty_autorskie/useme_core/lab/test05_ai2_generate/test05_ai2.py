import json
import os
import re
import requests

# Ścieżki
detail_path = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test03_parse_detail\detail.json"
output_path = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test05_ai2_generate\ai2_response.json"

# 1. Wczytaj dane oferty
if os.path.exists(detail_path):
    with open(detail_path, "r", encoding="utf-8-sig") as f:
        raw_text = f.read()
    # Plik może mieć podwójnie escape'owane cudzysłowy
    raw_text = raw_text.replace('\\"', '"')
    detail = json.loads(raw_text)
    offer = {
        "title": detail.get("title", ""),
        "description": detail.get("full_desc", detail.get("short_desc", "")),
        "budget": detail.get("budget", "Do negocjacji"),
        "category": detail.get("category", ""),
        "author": detail.get("author", ""),
    }
    print(f"[INFO] Wczytano ofertę z detail.json: {offer['title']}")
else:
    offer = {
        "title": "Stworzenie narzędzia do drukowania w pdf zestawów z Płatnika",
        "description": "Szukam programisty/freelancera, który stworzy prostą aplikację desktopową do generowania wydruków w pdf zestawów stworzonych w Płatniku.",
        "budget": "500,00 PLN",
        "category": "Oprogramowanie",
        "author": "RADI",
    }
    print("[INFO] detail.json nie istnieje – użyto testowej oferty.")

# 2. Przygotuj prompt
prompt = f"""Jesteś freelancerem-programistą Python. Poniżej dane oferty z Useme. Napisz profesjonalną, krótką propozycję (3-8 zdań) odpowiedzi na to zlecenie. Jeśli budżet jest 'Do negocjacji', zaproponuj stawkę. Zwróć JSON z polami: proposal_text i proposed_rate.

Dane oferty:
- Tytuł: {offer['title']}
- Kategoria: {offer['category']}
- Autor: {offer['author']}
- Budżet: {offer['budget']}
- Opis: {offer['description']}

Zwróć TYLKO surowy JSON (bez markdown, bez komentarzy)."""

print(f"[INFO] Prompt:\n{prompt}\n")

# 3. Wywołaj API przez requests (nie openai lib – omija problemy z proxy/SSE)
api_url = "http://localhost:4570/v1/chat/completions"
headers = {"Content-Type": "application/json"}
payload = {
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.7,
    "max_tokens": 500,
    "stream": False,
}

print("[INFO] Wysyłam request do API (stream=False)...")
resp = requests.post(api_url, json=payload, headers=headers, timeout=60)
resp.raise_for_status()

data = resp.json()
print(f"[DEBUG] Struktura odpowiedzi: {list(data.keys())}")

# Wyciągnij content z choices
if "choices" in data and len(data["choices"]) > 0:
    content = data["choices"][0]["message"]["content"].strip()
else:
    content = str(data)
print(f"[INFO] Surowa odpowiedź AI:\n{content}\n")

# 4. Parsuj odpowiedź
# Usuń potencjalne znaczniki proxy
content = re.sub(r'<!-- PROXY_SID:.*?-->', '', content, flags=re.DOTALL).strip()

# Usuń potencjalne markdown code fences
if content.startswith("```"):
    lines = content.split("\n")
    start = 0
    end = len(lines)
    if lines[0].startswith("```"):
        start = 1
    if lines[-1].startswith("```"):
        end = -1
    content = "\n".join(lines[start:end]).strip()

try:
    result = json.loads(content)
except json.JSONDecodeError as e:
    print(f"[WARN] Nie udało się sparsować JSON: {e}")
    # Spróbuj wyodrębnić JSON z tekstu
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        content = match.group(0)
        result = json.loads(content)
    else:
        result = {"proposal_text": content, "proposed_rate": None, "parse_error": str(e)}

# 5. Zapisz wynik
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"[OK] Zapisano do: {output_path}")
print(json.dumps(result, ensure_ascii=False, indent=2))