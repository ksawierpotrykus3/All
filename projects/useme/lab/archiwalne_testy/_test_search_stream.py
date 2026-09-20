import requests, json, sys

url = 'http://localhost:4571/v1/chat/completions'
payload = {
    'model': 'deepseek-v4-pro-search',
    'messages': [
        {'role': 'system', 'content': 'You are a researcher with web search enabled.'},
        {'role': 'user', 'content': 'Ile kosztuje plan CloudTalk Essential w 2026?'}
    ],
    'stream': True
}

print('Sending request to 4571...')
try:
    resp = requests.post(url, json=payload, timeout=60, stream=True)
    print('Status code:', resp.status_code)
    raw_lines = []
    content_chunks = []
    reasoning_chunks = []
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        raw_lines.append(line)
        if line.startswith('data:'):
            data_str = line[5:].strip()
            if data_str == '[DONE]':
                print('Received [DONE]')
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk.get('choices', [{}])[0].get('delta', {})
                if 'content' in delta and delta['content']:
                    content_chunks.append(delta['content'])
                if 'reasoning_content' in delta and delta['reasoning_content']:
                    reasoning_chunks.append(delta['reasoning_content'])
            except Exception as e:
                print('JSON parse error on line:', line, e)
    
    full_content = "".join(content_chunks)
    full_reasoning = "".join(reasoning_chunks)
    print(f'Total raw lines: {len(raw_lines)}')
    print(f'Total content chunks: {len(content_chunks)}, total len: {len(full_content)}')
    print(f'Total reasoning chunks: {len(reasoning_chunks)}, total len: {len(full_reasoning)}')
    print('CONTENT SAMPLE:', repr(full_content[:300]))
    print('REASONING SAMPLE:', repr(full_reasoning[:300]))
    if not full_content:
        print('All raw lines:')
        for l in raw_lines[:20]:
            print('  ', repr(l[:150]))
except Exception as e:
    print('Exception:', e)
