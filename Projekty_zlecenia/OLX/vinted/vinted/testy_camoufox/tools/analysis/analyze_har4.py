import json

with open(r'f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

# Find checkout/build with postData
for e in entries:
    url = e['request']['url']
    if 'checkout/build' in url:
        print(f"=== CHECKOUT/BUILD REQUEST ===")
        print(f"URL: {url}")
        print(f"Method: {e['request']['method']}")
        print(f"Headers:")
        for h in e['request']['headers']:
            print(f"  {h['name']}: {h['value']}")
        print(f"\nCookies:")
        for c in e['request']['cookies']:
            print(f"  {c['name']}: {c['value'][:50]}...")
        if 'postData' in e['request']:
            print(f"\nPostData:")
            print(f"  mimeType: {e['request']['postData'].get('mimeType')}")
            print(f"  text: {e['request']['postData'].get('text')}")
        break

# Find payment request with x-incognia-request-token
print("\n=== PAYMENT REQUEST (with x-incognia-request-token) ===")
for e in entries:
    url = e['request']['url']
    if 'checkout/payment' in url:
        print(f"URL: {url}")
        print(f"Method: {e['request']['method']}")
        print(f"Headers:")
        for h in e['request']['headers']:
            print(f"  {h['name']}: {h['value']}")
        print(f"\nCookies:")
        for c in e['request']['cookies']:
            print(f"  {c['name']}: {c['value'][:50]}...")
        if 'postData' in e['request']:
            print(f"\nPostData:")
            print(f"  mimeType: {e['request']['postData'].get('mimeType')}")
            print(f"  text: {e['request']['postData'].get('text')}")
        break

# Find all cookies set in responses
print("\n=== COOKIES SET BY SERVER (key ones) ===")
cookie_names = set()
for e in entries:
    if 'cookies' in e['response']:
        for c in e['response']['cookies']:
            cookie_names.add(c['name'])
            if c['name'] in ['_vinted_fr_session', 'datadome', 'ddjskey', 'sessionid', 'csrf_token']:
                print(f"  {c['name']}: {c['value'][:80]}... (domain: {c.get('domain')}, path: {c.get('path')})")

print(f"\nAll cookie names seen: {sorted(cookie_names)}")