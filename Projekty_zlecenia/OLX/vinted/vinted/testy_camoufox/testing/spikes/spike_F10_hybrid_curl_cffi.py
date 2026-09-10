#!/usr/bin/env python3
"""
F10 Hybrid Test: curl_cffi + extracted browser state
Tests if we can do checkout/build with cookies from Playwright
"""
import json
import time
import sys
import subprocess
from curl_cffi import requests

# Cookies extracted from Playwright after item page load + "Kup teraz" click
COOKIES = {
    "anon_id": "8e7f48f7-2ca3-44d0-8b7e-186ae2afc568",
    "anonymous-iso-locale": "pl-PL",
    "non_dot_com_www_domain_cookie_buster": "1",
    "consent_version": "eu",
    "viewport_size": "929",
    "_fbp": "fb.1.1788047196793.959524101959013678",
    "domain_selected": "true",
    "OptanonAlertBoxClosed": "2026-08-29T23:50:56.545Z",
    "eupubconsent-v2": "CQptDDAQptDDAAcABBPLCuFgAAAAAEPgAAwIAAAYNABMNDogDLIgECBQEAIEACgrCACgQBAAAkBRAQAmDAhyBgAusIkAIAUAAQQAgABBgACAAASABCIAIACAQAgQCBQABgAQBAQAMDAAGAChEAgABAdAxSAggECwASIwoDBAhAAQCAlsqEEgCBBHCFIscAggREwUAACIABQAAIB4WAgJKCViQQBcQXQAIAAAAUYIICKQkwBRQGQLQVgScBkaYAgeYJEkOgiAJghIyDIhJUEg8UxRAAAAAAAAAAAAAAAAAAAQAAAA.YAAACHwAAAAA.IMGtR_G__bXlv-Tb36bpkeYxf99hr7sQxBgbIsm4FzLvW7JwC32EbJEyatiIKmRIAu3DBIQNtHAjURUChKIAVLzDsaEyUoTtKJ-BkiDMRYyJQCEhum4pjWQCZYur_50d0mR-N6dr-2dzyy5hnn3a9fuS1UJicKYetHfn8ZBOS-_IU9_x-_4v4_MbpEm0eSVv9tEtt4zc64tP6dpuxt-Tyffyfv_f72fS7X__c__33_8qXX_r764AAAAAAAAQAAAAAAAAAIAA",
    "OTAdditionalConsentString": "2~~dv.20.43.55.57.61.70.83.89.93.108.117.122.124.135.143.144.147.149.159.161.184.192.196.211.228.230.236.239.255.259.266.272.286.291.311.313.314.320.322.323.327.340.358.367.370.371.385.407.415.424.429.430.436.445.469.486.491.494.495.522.523.550.560.568.574.576.587.591.621.723.737.797.798.803.820.827.839.864.899.904.922.938.955.959.979.981.985.986.1003.1027.1031.1033.1046.1047.1048.1051.1053.1067.1092.1095.1097.1099.1107.1109.1126.1135.1143.1149.1152.1162.1166.1186.1188.1192.1205.1215.1220.1226.1227.1230.1252.1268.1270.1276.1284.1290.1301.1307.1312.1329.1342.1345.1356.1365.1403.1415.1416.1419.1421.1423.1440.1449.1455.1495.1512.1514.1516.1525.1540.1548.1555.1558.1567.1570.1577.1579.1583.1584.1598.1603.1616.1638.1651.1653.1659.1660.1667.1677.1678.1682.1697.1699.1712.1716.1720.1721.1725.1732.1735.1745.1750.1753.1782.1786.1800.1808.1810.1825.1827.1832.1838.1840.1843.1845.1859.1870.1878.1880.1882.1889.1898.1911.1917.1928.1929.1942.1944.1958.1962.1963.1964.1967.1968.1699.1712.1716.1720.1721.1725.1732.1735.1745.1750.1753.1782.1786.1800.1808.1810.1825.1827.1832.1838.1840.1843.1845.1859.1870.1878.1880.1882.1889.1898.1911.1917.1928.1929.1942.1944.1958.1962.1963.1964.1967.1968.1969.1978.1985.1987.2003.2016.2027.2035.2038.2039.2044.2047.2052.2056.2064.2068.2069.2072.2074.2084.2088.2090.2103.2107.2109.2115.2124.2130.2133.2135.2137.2140.2141.2147.2156.2166.2177.2186.2205.2213.2216.2219.2220.2222.2223.2224.2225.2227.2234.2251.2253.2262.2271.2275.2278.2279.2282.2295.2299.2309.2312.2316.2322.2325.2328.2331.2335.2336.2354.2358.2359.2370.2373.2376.2377.2400.2403.2405.2406.2411.2414.2415.2416.2418.2425.2427.2440.2447.2453.2461.2465.2468.2472.2477.2484.2486.2488.2498.2506.2510.2517.2526.2527.2531.2534.2535.2542.2552.2559.2564.2567.2568.2569.2571.2572.2575.2577.2579.2583.2584.2589.2595.2596.2604.2605.2609.2610.2612.2614.2621.2624.2627.2628.2629.2633.2636.2642.2643.2645.2646.2650.2651.2652.2656.2657.2658.2660.2661.2669.2670.2677.2681.2684.2687.2689.2690.2695.2698.2713.2714.2729.2739.2767.2768.2770.2772.2778.2784.2787.2791.2792.2798.2801.2805.2812.2813.2814.2816.2817.2821.2822.2824.2826.2827.2830.2831.2832.2833.2838.2839.2844.2846.2849.2850.2852.2854.2860.2862.2863.2865.2867.2869.2872.2874.2875.2878.2880.2881.2882.2884.2886.2887.2888.2889.2891.2893.2894.2895.2897.2898.2900.2901.2908.2909.2916.2917.2918.2920.2922.2923.2927.2929.2930.2931.2940.2941.2947.2949.2950.2956.2958.2961.2963.2964.2965.2966.2968.2972.2973.2974.2975.2979.2980.2981.2983.2985.2986.2987.2994.2995.2997.2999.3000.3001.3002.3003.3005.3008.3009.3010.3012.3016.3017.3018.3019.3023.3028.3031.3034.3038.3043.3051.3052.3053.3055.3058.3059.3063.3066.3073.3074.3075.3076.3077.3089.3090.3093.3094.3095.3097.3099.3100.3106.3107.3109.3112.3117.3119.3120.3126.3127.3128.3130.3133.3135.3136.3137.3145.3149.3151.3153.3165.3167.3169.3172.3173.3177.3182.3184.3185.3186.3187.3188.3189.3190.3194.3196.3200.3201.3209.3210.3213.3214.3215.3217.3218.3222.3223.3225.3226.3227.3228.3230.3231.3233.3234.3235.3236.3237.3238.3240.3244.3250.3251.3253.3254.3257.3260.3266.3270.3272.3286.3288.3289.3290.3292.3293.3296.3299.3300.3306.3307.3309.3314.3315.3316.3318.3323.3324.3328.3330.3331.3531.3631.3731.3831.4131.4531.4631.4731.4831.5231.6731.6931.7131.7235.7831.7931.8931.10231.10631.10831.11031.11531.11631.13431.13632.14034.14133.14237.15731.16831.16931.21233.21731.23031.25131.25931.26031.26631.27731.27831.28031.28332.28731.29631.30331.30532.30732.32531.33931.34231.34631.34731.36831.39131.39531.40632.41131.41531.43631.43731.43831.45931.47232.47531.48131.49231.49332.49431.50831.52831.54231.56831.56931.57131.57231.57531.57931.58131.58631.59831.59832.60731",
    "__eoi": "ID=0e043c600529ea19:T=1788047980:RT=1788047980:S=AA-AfjYDSBCn69Mov8soODgmw4LF",
    "monetixads-user-session": "250100646453736151000537365131080192024",
    "sharedid": "0b9e8ff0-2f71-4026-984d-33be1eb636e4",
    "sharedid_cst": "skLIFQ%3D%3D",
    "OptanonConsent": "isGpcEnabled=0&datestamp=Sun+Aug+30+2026+02%3A03%3A22+GMT%2B0200+(czas+%C5%9Brodkowoeuropejski+letni)&version=202602.1.0&browserGpcFlag=0&isIABGlobal=false&consentId=8e7f48f7-2ca3-44d0-8b7e-186ae2afc568&identifierType=Cookie+Unique+Id&isAnonUser=1&hosts=&interactionCount=2&prevHadToken=0&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A0%2CC0003%3A0%2CC0004%3A0%2CC0005%3A0%2CV2STACK42%3A0%2CC0035%3A0%2CC0038%3A0&genVendors=V5%3A0%2CV2%3A0%2CV1%3A0%2C&crTime=1788047456875&AwaitingReconsent=false&intType=2&geolocation=PL%3B22",
    "datadome": "Fzuwe0forq417rjfe0RX_c7jz2GGcxdTXNRcBx42r~jebxO6srCknIRDz50CzXVvTAW7cTLsi5kADCH9pF5QO6az_ENzOc5X3uiiI3kYZ2l8dJ5OEMuJhRTxFuaz0Cgx",
}

# Base headers from HAR analysis
BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://www.vinted.pl",
    "referer": "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e",  # From HAR - appears constant
}

ITEM_ID = "9807925466"

STRATEGIES = [
    {"name": "firefox_151", "impersonate": "firefox151", "desc": "Firefox 151 JA3"},
    {"name": "firefox_152", "impersonate": "firefox152", "desc": "Firefox 152 JA3"},
    {"name": "chrome_151", "impersonate": "chrome151", "desc": "Chrome 151 JA3"},
    {"name": "chrome_152", "impersonate": "chrome152", "desc": "Chrome 152 JA3"},
    {"name": "firefox_akamai", "impersonate": "firefox152_akamai", "desc": "Firefox 152 Akamai"},
    {"name": "chrome_akamai", "impersonate": "chrome152_akamai", "desc": "Chrome 152 Akamai"},
    {"name": "safari_15_5", "impersonate": "safari15_5", "desc": "Safari 15.5"},
    {"name": "safari_17_0", "impersonate": "safari17_0", "desc": "Safari 17.0"},
]

EXTRA_HEADERS_VARIANTS = [
    {"name": "minimal", "extra": {}},
    {"name": "with_csrf", "extra": {"x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"}},
    {"name": "full_har", "extra": {
        "x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e",
        "x-requested-with": "XMLHttpRequest",
    }},
]

def generate_incognia_payload():
    """Generate Incognia payload using Node.js incognia_engine.js"""
    try:
        result = subprocess.run(
            ['node', '-e', '''
const { buildConsumePayload } = require("./incognia_engine.js");
const payload = buildConsumePayload({ sdkInstanceId: "test-" + Date.now(), type: "pls" });
console.log(JSON.stringify(payload));
'''],
            cwd=r'f:\PROJEKTY\vinted\vinted\testy_camoufox',
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
        else:
            print(f"  Node.js error: {result.stderr}")
            return None
    except Exception as e:
        print(f"  Incognia generation failed: {e}")
        return None


def test_strategy(strategy, extra_headers_variant):
    """Test a single strategy combination."""
    print(f"\n{'='*60}")
    print(f"Strategy: {strategy['name']} ({strategy['desc']}) + {extra_headers_variant['name']}")
    print(f"{'='*60}")

    headers = BASE_HEADERS.copy()
    headers.update(extra_headers_variant['extra'])

    # Generate Incognia payload
    incognia_payload = generate_incognia_payload()
    if incognia_payload:
        headers["x-incognia-request-token"] = incognia_payload["s"]
        print(f"  Incognia token: {incognia_payload['s'][:50]}...")

    # Checkout body from HAR
    body = {
        "item_id": int(ITEM_ID),
        "quantity": 1,
        "checkout_type": "buy_now",
        "currency": "PLN",
        "protection_fee": True,
        "payment_method": "wallet",
        "browser_info": {
            "user_agent": BASE_HEADERS["user-agent"],
            "screen_width": 1920,
            "screen_height": 1080,
            "timezone_offset": -120,
            "language": "pl",
        }
    }

    session = requests.Session()
    session.cookies.update(COOKIES)
    session.headers.update(headers)

    try:
        # First, try to get the checkout page to establish session
        print(f"  GET /checkout?item_id={ITEM_ID}...")
        resp = session.get(
            f"https://www.vinted.pl/checkout?item_id={ITEM_ID}",
            impersonate=strategy["impersonate"],
            timeout=30,
        )
        print(f"  GET status: {resp.status_code}")

        # Now POST to checkout/build
        print(f"  POST /checkout/build...")
        resp = session.post(
            "https://www.vinted.pl/checkout/build",
            json=body,
            impersonate=strategy["impersonate"],
            timeout=30,
        )
        print(f"  POST status: {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")

        if resp.status_code == 200:
            print(f"  ✅ SUCCESS!")
            return resp.json()
        elif resp.status_code == 403:
            print(f"  ❌ 403 Forbidden (captcha/block)")
        elif resp.status_code == 401:
            print(f"  ❌ 401 Unauthorized (need login)")
        elif resp.status_code == 422:
            print(f"  ❌ 422 Unprocessable (validation error)")
        else:
            print(f"  ❓ Status {resp.status_code}")

        return None

    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None


def main():
    print("F10 Hybrid Test: curl_cffi + Browser State")
    print("=" * 60)
    print(f"Item: {ITEM_ID}")
    print(f"Cookies: {len(COOKIES)} cookies (including datadome)")
    print(f"Strategies: {len(STRATEGIES)}")
    print(f"Header variants: {len(EXTRA_HEADERS_VARIANTS)}")

    # Test all combinations
    for strategy in STRATEGIES:
        for variant in EXTRA_HEADERS_VARIANTS:
            result = test_strategy(strategy, variant)
            if result:
                print(f"\n🎉 FOUND WORKING COMBINATION!")
                print(f"Strategy: {strategy['name']}")
                print(f"Headers: {variant['name']}")
                print(f"Result: {json.dumps(result, indent=2)}")
                return result

    print("\n❌ No working combination found")
    return None


if __name__ == "__main__":
    main()