import json

with open(r'f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

print("=== CHECKOUT/BUILD REQUESTS ===")
for e in entries:
    url = e['request']['url']
    if 'checkout' in url.lower() or 'build' in url.lower():
        print(f'CHECKOUT: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        print(f'  Req Headers: {list(req_headers.keys())}')
        if 'x-incognia-request-token' in req_headers:
            print(f'  x-incognia-request-token: {req_headers["x-incognia-request-token"][:80]}...')
        if 'x-datadome-clientid' in req_headers:
            print(f'  x-datadome-clientid: {req_headers["x-datadome-clientid"]}')
        if 'cookie' in req_headers:
            print(f'  Cookie: {req_headers["cookie"][:200]}...')
        resp_headers = {h['name']: h['value'] for h in e['response']['headers']}
        print(f'  Resp Headers: {list(resp_headers.keys())}')
        print()

print("\n=== INCOGNIA REQUESTS ===")
for e in entries:
    url = e['request']['url']
    if 'incognia' in url.lower() or 'j3r4zw' in url.lower() or 'consume' in url.lower():
        print(f'INCOGNIA: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        print(f'  Req Headers: {list(req_headers.keys())}')
        if 'content' in e['request'] and 'text' in e['request']['content']:
            print(f'  Request body: {e["request"]["content"]["text"][:200]}...')
        if 'content' in e['response'] and 'text' in e['response']['content']:
            print(f'  Response body: {e["response"]["content"]["text"][:200]}...')
        print()

print("\n=== DATADOME REQUESTS ===")
for e in entries:
    url = e['request']['url']
    if 'datadome' in url.lower():
        print(f'DATADOME: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        print(f'  Req Headers: {list(req_headers.keys())}')
        print()

print("\n=== CCHD_CONFIG REQUESTS ===")
for e in entries:
    url = e['request']['url']
    if 'cchd_config' in url.lower():
        print(f'CCHD_CONFIG: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        print(f'  Req Headers: {list(req_headers.keys())}')
        if 'content' in e['response'] and 'text' in e['response']['content']:
            print(f'  Response body: {e["response"]["content"]["text"][:200]}...')
        print()

print("\n=== ALL UNIQUE DOMAINS ===")
domains = set()
for e in entries:
    from urllib.parse import urlparse
    domains.add(urlparse(e['request']['url']).netloc)
for d in sorted(domains):
    print(f'  {d}')