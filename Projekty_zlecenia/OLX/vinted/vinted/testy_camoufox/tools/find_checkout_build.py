import json

with open(r'f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']
for e in entries:
    url = e['request']['url']
    if 'checkout' in url and 'build' in url:
        print(f'FOUND: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        if 'postData' in e['request'] and e['request']['postData']:
            print(f'  Body: {e["request"]["postData"].get("text", "")[:300]}')
        print()