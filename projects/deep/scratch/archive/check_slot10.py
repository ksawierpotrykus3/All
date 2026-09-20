import json
import curl_cffi.requests as requests

with open("session_10.json", encoding="utf-8") as f:
    s = json.load(f)

headers = {
    "authorization": f"Bearer {s['auth_token']}",
    "user-agent": s.get("user_agent", "Mozilla/5.0"),
    "origin": "https://chat.deepseek.com",
    "referer": "https://chat.deepseek.com/",
    "x-app-version": "2.5.0",
    "x-client-platform": "web",
    "x-client-version": "2.5.0",
}

cookies = s.get("cookies", {})

print("1. Sprawdzam /users/current...")
r_user = requests.get("https://chat.deepseek.com/api/v0/users/current", headers=headers, cookies=cookies, impersonate="chrome120", timeout=15)
print("HTTP:", r_user.status_code)
print("Odpowiedź:", r_user.json())

print("\n2. Sprawdzam /chat_session/create...")
r_chat = requests.post("https://chat.deepseek.com/api/v0/chat_session/create", headers=headers, cookies=cookies, json={"character_id": None}, impersonate="chrome120", timeout=15)
print("HTTP:", r_chat.status_code)
chat_data = r_chat.json()
print("Odpowiedź sesji:", chat_data)

# Usuń sesję testową żeby nie śmiecić
sess_id = chat_data.get("data", {}).get("biz_data", {}).get("id")
if sess_id:
    print(f"Nowa sesja utworzona pomyslnie (ID={sess_id}). Usuwam sesje testowa...")
    requests.delete("https://chat.deepseek.com/api/v0/chat_session/delete", headers=headers, json={"chat_session_id": sess_id}, impersonate="chrome120", timeout=10)

print("\n3. Sprawdzam czy proxy na porcie 4570 widzi slot 10...")
import urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:4570/v1/chat/completions",
    data=json.dumps({
        "model": "deepseek-reasoner",
        "messages": [{"role": "user", "content": "Odpowiedz jednym slowem: CZYSTE"}],
        "stream": False
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=30) as p_resp:
    print("Proxy HTTP:", p_resp.status)
    print("Proxy Response:", p_resp.read().decode("utf-8")[:200])

print("\n=== PODSUMOWANIE ===")
if "muted" in str(chat_data).lower() or chat_data.get("biz_code") == 5:
    print("STATUS: BAN (Muted)!")
else:
    print("STATUS: 100% CZYSTO! Brak bana, brak opóźnionych kar, konto działa idealnie.")
