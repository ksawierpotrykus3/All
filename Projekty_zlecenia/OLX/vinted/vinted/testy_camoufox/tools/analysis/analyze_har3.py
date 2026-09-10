import json

with open(r'f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

# Check first checkout/build entry in detail
for e in entries:
    url = e['request']['url']
    if 'checkout/build' in url:
        print(f"URL: {url}")
        print(f"Request keys: {e['request'].keys()}")
        print(f"Response keys: {e['response'].keys()}")
        if 'content' in e['request']:
            print(f"Request content keys: {e['request']['content'].keys()}")
        if 'content' in e['response']:
            print(f"Response content keys: {e['response']['content'].keys()}")
        break

# Check Incognia config
print("\n--- Incognia config ---")
for e in entries:
    url = e['request']['url']
    if 'j3r4zw/v1/config' in url:
        print(f"URL: {url}")
        print(f"Response keys: {e['response'].keys()}")
        if 'content' in e['response']:
            print(f"Response content keys: {e['response']['content'].keys()}")
            if 'text' in e['response']['content']:
                print(f"Text length: {len(e['response']['content']['text'])}")
            if 'mimeType' in e['response']['content']:
                print(f"MimeType: {e['response']['content']['mimeType']}")
        break

# Check consume
print("\n--- Incognia consume ---")
for e in entries:
    url = e['request']['url']
    if 'j3r4zw/v1/consume' in url and e['request']['method'] == 'POST':
        print(f"URL: {url}")
        print(f"Request content keys: {e['request'].get('content', {}).keys()}")
        if 'content' in e['request'] and 'text' in e['request']['content']:
            print(f"Request text length: {len(e['request']['content']['text'])}")
        if 'content' in e['response']:
            print(f"Response content keys: {e['response']['content'].keys()}")
        break

# Check cchd_config
print("\n--- cchd_config ---")
for e in entries:
    url = e['request']['url']
    if 'cchd_config' in url:
        print(f"URL: {url}")
        if 'content' in e['response']:
            print(f"Response content keys: {e['response']['content'].keys()}")
            if 'text' in e['response']['content']:
                print(f"Text length: {len(e['response']['content']['text'])}")
            if 'mimeType' in e['response']['content']:
                print(f"MimeType: {e['response']['content']['mimeType']}")
        break