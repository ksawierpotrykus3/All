import requests
import json
import os
import re

# Wczytaj oferty z pliku test02
offers_file = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test02_parse_list\offers.json"
with open(offers_file, "r", encoding="utf-8") as f:
    offers = json.load(f)

# Dla czytelności promptu, ograniczamy do kluczowych pól
offers_simplified = []
for o in offers:
    offers_simplified.append({
        "title": o["title"],
        "category": o["category"],
        "budget": o["budget"],
        "description": o["description"][:300]
    })

prompt = (
    "Przeanalizuj poniższe oferty i wybierz te, które pasują dla programisty Python "
    "specjalizującego się w web scrapingu i automatyzacji. "
    "Zwróć JSON z polami: selected (lista wybranych) i rejected (lista odrzuconych) "
    "z uzasadnieniem dla każdej decyzji.\n\n"
    + json.dumps(offers_simplified, ensure_ascii=False, indent=2)
)

print("=== PROMPT ===")
print(prompt)
print("\n=== WYSYŁANIE DO AI ===")

# Użyj bezpośrednio requests, bo openai library ma problem z SSE odpowiedzią
api_url = "http://localhost:4570/v1/chat/completions"
payload = {
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.7,
    "stream": False
}
headers = {"Content-Type": "application/json"}

resp = requests.post(api_url, json=payload, headers=headers, timeout=120)
resp.raise_for_status()

# Jeśli odpowiedź to SSE (text/event-stream), parsuj chunki
content_type = resp.headers.get("Content-Type", "")
if "text/event-stream" in content_type or resp.text.strip().startswith("data:"):
    # Parsowanie SSE
    full_content = ""
    for line in resp.text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content_piece = delta.get("content", "")
                full_content += content_piece
            except json.JSONDecodeError:
                pass
    result = full_content
else:
    # Normalna odpowiedź JSON
    data = resp.json()
    result = data.get("choices", [{}])[0].get("message", {}).get("content", "")

# Wyczyść znaczniki markdown ```json ... ```
result = result.strip()
if result.startswith("```"):
    lines = result.split("\n")
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    result = "\n".join(lines).strip()

output_dir = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test04_ai1_select"
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, "ai1_response.json")
with open(output_file, "w", encoding="utf-8") as f:
    f.write(result)

# Zapisz też kopię promptu dla raportu
prompt_file = os.path.join(output_dir, "prompt.txt")
with open(prompt_file, "w", encoding="utf-8") as f:
    f.write(prompt)

print("\n=== ODPOWIEDŹ AI ===")
print(result)
print(f"\nZapisano do: {output_file}")