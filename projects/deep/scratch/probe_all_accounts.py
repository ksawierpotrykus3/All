import json
from pathlib import Path
from curl_cffi import requests
import datetime

print("Probing all 11 DeepSeek accounts directly from DeepSeek API...")
results = []
for s in range(11):
    p = Path(f"session_{s}.json")
    if not p.exists():
        print(f"Slot {s}: session file missing")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    tok = d.get("auth_token", "")
    cookies = d.get("cookies", {})
    ua = d.get("user_agent", "Mozilla/5.0")
    email = d.get("email", "unknown")
    try:
        r = requests.get(
            "https://chat.deepseek.com/api/v0/users/current",
            headers={"authorization": f"Bearer {tok}", "user-agent": ua},
            cookies=cookies,
            impersonate="chrome120",
            timeout=10,
        )
        res = r.json()
        code = res.get("code")
        msg = res.get("msg")
        biz = res.get("data", {}).get("biz_data", {})
        chat = biz.get("chat", {})
        is_muted = chat.get("is_muted", 0)
        mute_until = chat.get("mute_until")
        until_str = ""
        if mute_until:
            until_dt = datetime.datetime.fromtimestamp(float(mute_until), datetime.timezone(datetime.timedelta(hours=2)))
            until_str = until_dt.strftime("%Y-%m-%d %H:%M:%S CEST")
        
        info = {
            "slot": s,
            "email": email,
            "code": code,
            "msg": msg,
            "is_muted": is_muted,
            "mute_until": mute_until,
            "until_str": until_str,
            "chat": chat,
            "user_id": biz.get("id"),
            "region": biz.get("region"),
            "status": biz.get("status")
        }
        results.append(info)
        print(f"Slot {s:2d} | {email} | code={code} | muted={is_muted} | until={until_str or 'N/A'}")
    except Exception as e:
        print(f"Slot {s:2d} | {email} | ERROR: {e}")

Path("data/all_accounts_probe.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print("\nSaved complete probe data to data/all_accounts_probe.json")
