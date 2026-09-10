import json

with open(r'f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

print("=== CHECKOUT/BUILD REQUEST BODIES ===")
for e in entries:
    url = e['request']['url']
    if 'checkout/build' in url or '/purchases/' in url and 'checkout' in url:
        print(f'\n{e["request"]["method"]} {url}')
        print(f'  Status: {e["response"]["status"]}')
        if 'content' in e['request'] and 'text' in e['request']['content']:
            print(f'  Request body: {e["request"]["content"]["text"]}')
        if 'content' in e['response'] and 'text' in e['response']['content']:
            print(f'  Response body: {e["response"]["content"]["text"][:500]}...')

print("\n=== INCOGNIA CONFIG RESPONSE ===")
for e in entries:
    url = e['request']['url']
    if 'j3r4zw/v1/config' in url:
        if 'content' in e['response'] and 'text' in e['response']['content']:
            print(f'{e["request"]["method"]} {url}')
            print(f'  Response: {e["response"]["content"]["text"][:500]}...')

print("\n=== INCOGNIA CONSUME REQUEST BODIES (first 3) ===")
count = 0
for e in entries:
    url = e['request']['url']
    if 'j3r4zw/v1/consume' in url and e['request']['method'] == 'POST':
        if count < 3:
            print(f'\n{e["request"]["method"]} {url}')
            if 'content' in e['request'] and 'text' in e['request']['content']:
                print(f'  Request body: {e["request"]["content"]["text"][:500]}...')
            if 'content' in e['response'] and 'text' in e['response']['content']:
                print(f'  Response body: {e["response"]["content"]["text"][:500]}...')
            count += 1

print("\n=== CCHD_CONFIG RESPONSES ===")
for e in entries:
    url = e['request']['url']
    if 'cchd_config' in url:
        if 'content' in e['response'] and 'text' in e['response']['content']:
            print(f'{e["request"]["method"]} {url}')
            print(f'  Response: {e["response"]["content"]["text"][:200]}...')

print("\n=== DATADOME SDK (first 200 chars) ===")
for e in entries:
    url = e['request']['url']
    if 'datadome' in url and 'tags.js' in url:
        if 'content' in e['response'] and 'text' in e['response']['content']:
            print(f'{e["request"]["method"]} {url}')
            print(f'  Response: {e["response"]["content"]["text"][:200]}...')
            break