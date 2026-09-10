#!/usr/bin/env python3
"""
Benchmark: Weryfikacja wektorow optymalizacyjnych bota Vinted.
"""
import json, statistics, sys, time
from pathlib import Path
import orjson

REPO = Path(r'F:\PROJEKTY\vinted\bot')
sys.path.insert(0, str(REPO / 'src'))
from vintedbot.config import wczytaj_cookies, tls_kwargs, IMPERSONATE
import curl_cffi.requests as creq

COOKIES_PATH = Path(r'F:\PROJEKTY\vinted\vinted\dane\cookies_fresh.txt')
if not COOKIES_PATH.exists():
    COOKIES_PATH = REPO / 'output' / 'cookies_152_export.txt'
COOKIES = wczytaj_cookies(COOKIES_PATH)
print(f'[COOKIES] {COOKIES_PATH}  ({len(COOKIES)} cookies)')

TLS = tls_kwargs()
CATALOG_URL = 'https://www.vinted.pl/api/v2/catalog/items'
BASE_PARAMS = {'catalog_ids[]': '1206', 'currency': 'PLN', 'order': 'newest_first'}
N = 6

def session():
    s = creq.Session(impersonate=IMPERSONATE)
    s.cookies.update(COOKIES)
    s.headers.update({'Accept-Language': 'pl-PL,pl;q=0.9'})
    return s

# ── TEST 1: RTT vs per_page ───────────────────────────────────────────────
print('\n' + '='*64)
print(f'TEST 1: RTT katalogu vs per_page (N={N} per wariant)')
rtt1 = {}; sz1 = {}
for pp in [5, 10, 20, 96]:
    rtt1[pp] = []; sz1[pp] = []
    s = session()
    for i in range(N):
        t0 = time.perf_counter()
        r = s.get(CATALOG_URL, params={**BASE_PARAMS, 'per_page': pp}, **TLS, timeout=15)
        ms = (time.perf_counter()-t0)*1000
        rtt1[pp].append(ms); sz1[pp].append(len(r.content))
        print(f'  pp={pp:3d} #{i+1}: {ms:7.1f} ms  {len(r.content)//1024} KB  HTTP {r.status_code}')
        time.sleep(1.3)
    s.close()
    med = statistics.median(rtt1[pp])
    print(f'  => pp={pp}: median={med:.0f} ms  mean={statistics.mean(rtt1[pp]):.0f} ms  stdev={statistics.stdev(rtt1[pp]):.0f} ms')
    time.sleep(2.0)

# ── TEST 2: orjson vs stdlib json ─────────────────────────────────────────
print('\n'+'='*64)
print('TEST 2: orjson vs stdlib json (N=10000 iteracji)')
s = session()
raw = s.get(CATALOG_URL, params={**BASE_PARAMS, 'per_page': 96}, **TLS, timeout=15).content
s.close()
raw_str = raw.decode('utf-8')
print(f'  payload: {len(raw)//1024} KB')

NP = 10_000
t0 = time.perf_counter(); [json.loads(raw_str) for _ in range(NP)]; stdlib_us = (time.perf_counter()-t0)/NP*1e6
t0 = time.perf_counter(); [orjson.loads(raw) for _ in range(NP)]; orjson_us = (time.perf_counter()-t0)/NP*1e6
spd = stdlib_us/orjson_us
print(f'  stdlib json : {stdlib_us:.2f} us/call')
print(f'  orjson      : {orjson_us:.2f} us/call')
print(f'  speedup     : {spd:.2f}x  oszczednosc: {stdlib_us-orjson_us:.2f} us/call')
time.sleep(1.5)

# ── TEST 3: Cold vs Warm RTT ──────────────────────────────────────────────
print('\n'+'='*64)
print(f'TEST 3: Cold (nowa sesja TLS) vs Warm (reuz. polaczenie) (N={N})')
cold = []; warm = []
PARAMS_W = {**BASE_PARAMS, 'per_page': 10}
for i in range(N):
    s = session()
    t0 = time.perf_counter(); r = s.get(CATALOG_URL, params=PARAMS_W, **TLS, timeout=15)
    cold.append((time.perf_counter()-t0)*1000); s.close()
    print(f'  COLD #{i+1}: {cold[-1]:.1f} ms  HTTP {r.status_code}')
    time.sleep(1.5)
s = session()
for i in range(N):
    t0 = time.perf_counter(); r = s.get(CATALOG_URL, params=PARAMS_W, **TLS, timeout=15)
    warm.append((time.perf_counter()-t0)*1000)
    print(f'  WARM #{i+1}: {warm[-1]:.1f} ms  HTTP {r.status_code}')
    time.sleep(1.5)
s.close()
cmed = statistics.median(cold); wmed = statistics.median(warm)
print(f'  => COLD median={cmed:.0f} ms   WARM median={wmed:.0f} ms   zysk={cmed-wmed:.0f} ms ({(cmed-wmed)/cmed*100:.1f}%)')

# ── ZAPIS ─────────────────────────────────────────────────────────────────
ts = int(time.time())
wyniki = {
    'timestamp': ts,
    'test1_per_page': {str(pp): {'runs': rtt1[pp], 'median': statistics.median(rtt1[pp]), 'mean': statistics.mean(rtt1[pp]), 'stdev': statistics.stdev(rtt1[pp]), 'size_kb_avg': statistics.mean(sz1[pp])//1024} for pp in rtt1},
    'test2_json': {'payload_kb': len(raw)//1024, 'n': NP, 'stdlib_us': round(stdlib_us,2), 'orjson_us': round(orjson_us,2), 'speedup_x': round(spd,2), 'savings_us': round(stdlib_us-orjson_us,2)},
    'test3_cold_warm': {'cold': cold, 'warm': warm, 'cold_median': cmed, 'warm_median': wmed, 'gain_ms': round(cmed-wmed,1), 'gain_pct': round((cmed-wmed)/cmed*100,1)},
}
out = REPO / 'output' / f'benchmark_optymalizacje_{ts}.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(wyniki, indent=2, ensure_ascii=False))
print(f'\n[ZAPISANO] {out}')
