import json

with open(r'f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']
print(f'Total entries: {len(entries)}')

# Find checkout/build requests
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
        if 'postData' in e['request'] and e['request']['postData']:
            print(f'  Body: {e["request"]["postData"].get("text", "")[:500]}')
        print()

# Find purchase/checkout requests
for e in entries:
    url = e['request']['url']
    if 'purchase' in url.lower() and 'checkout' in url.lower():
        print(f'PURCHASE CHECKOUT: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        print(f'  Req Headers: {list(req_headers.keys())}')
        if 'x-incognia-request-token' in req_headers:
            print(f'  x-incognia-request-token: {req_headers["x-incognia-request-token"][:80]}...')
        if 'cookie' in req_headers:
            print(f'  Cookie: {req_headers["cookie"][:200]}...')
        if 'postData' in e['request'] and e['request']['postData']:
            print(f'  Body: {e["request"]["postData"].get("text", "")[:500]}')
        print()

# Find j3r4zw/consume requests
for e in entries:
    url = e['request']['url']
    if 'j3r4zw' in url and 'consume' in url:
        print(f'INCOGNIA CONSUME: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        if 'x-incognia-request-token' in req_headers:
            print(f'  x-incognia-request-token: {req_headers["x-incognia-request-token"][:80]}...')
        if 'postData' in e['request'] and e['request']['postData']:
            print(f'  Body: {e["request"]["postData"].get("text", "")[:500]}')
        print()

# Find connectioncheck requests
for e in entries:
    url = e['request']['url']
    if 'connectioncheck' in url or 'netconn' in url or 'wsconn' in url:
        print(f'INCOGNIA WS: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        req_headers = {h['name']: h['value'] for h in e['request']['headers']}
        print(f'  Req Headers: {list(req_headers.keys())}')
        print()

# Find Datadome requests
for e in entries:
    url = e['request']['url']
    if 'datadome' in url.lower() or 'dd.vinted' in url:
        print(f'DATADOME: {e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        print()