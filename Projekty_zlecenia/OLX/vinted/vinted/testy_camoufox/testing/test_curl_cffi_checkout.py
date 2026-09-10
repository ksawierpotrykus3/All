#!/usr/bin/env python3
"""
Test curl_cffi z fingerprintem Firefox 152 do endpointu checkout/build.
Używa nagłówków i payloadu z HAR (Opera GX / Chrome 150).
"""

import json
from curl_cffi import requests

# Firefox 152 fingerprint (zmierzony spike_ja3_firefox152.py, zweryfikowany spike_curl_cffi_firefox152.py)
FF152_JA3 = "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,4588-29-23-24-25-256-257,0"
FF152_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"
FF152_EXTRA_FP = {
    "tls_delegated_credential": "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:ecdsa_secp521r1_sha512:ecdsa_sha1",
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",
}

# Nagłówki z HAR (checkout/build request)
# User-Agent z HAR: Chrome 150 / Opera GX 134
HAR_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 OPR/134.0.0.0"

# Wartości z HAR (przykładowe - muszą być aktualne z sesji)
HAR_X_ANON_ID = "98c6af5a-87da-45f2-9be5-24cf9345b003"
HAR_X_CSRF_TOKEN = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"

# x-incognia-request-token z HAR (JWE - jednorazowy, wygasły)
HAR_INCOGNIA_TOKEN = "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkExMjhDQkMtSFMyNTYifQ.oiK8KBQ2KtW_dPBysaPHF5aKgMZFXL-52K6CZMMRsVrnuAxq7agrwy-ds7U2X7f0XFKrgr6xQOcIVwDnjnPD22-xIok-JHPhcOpTb0BsFhZflIFvsVAoTVdmNweogzqPNjkiUKux7WaeN9L4T01PXHlk5vC48eV7NU8LC8TS-6IrBbaciYRnKfENYciPYRhKPf3CEZgmGeTaXlAh2hjve3yf9K2NC5rCOXuAMNM5Vi07zvnmCPT7rQlsA5te8ime1iqbbpacdsOwHW32_XhvsPrhI1rhy6sV5wx2tg-1BAMzFyC40WaTvF9RdX4qBAezp0r8VR8QrsiSpFTRvy12Mg.VX2QtEVj20y2NUVvWWVF6A.-iaP0rwcPabYAEbukB9ceP-ZvtV8YENVpkHmloHqSL5H_Qid_qSI73AO9-_G10DzolvFX9a9C3FHJguCUKrB0MCvNa5FdtVa8iuxfzBT44dmW9vQife6D-46sKYVehyBdAZb2aDV0Hb4TjWYIvL_Ax3o-3nQFUerUGx7h_eBwoM90gEJsToN7VUoyb8uTDUmayWTExR9aOp_cfNhtRONGxDhE-XE-_uWzx85PMPyUto4GJNuuJ1KKP6VnicwSaccMwwRs84I6h4AHrsyZW2FQzlItGNMI4ZEQiH0DPBX2f97Fzoy_BfLzIeNH_DSd1d5vJKDEx0FLGF9fNi9Uv0tpBbOiene27ebM5EJNeaD00kD15Dtm_Iwjlptn-ilAOwrOBLnQ05_nhuVNoi0L-Sx4bNRh_PgKfrlW0Jrzw7wztJ0cuL885tYPfgfA1asS9nNX5OQN8gk8eDN9T7uo2c99NWfErW7fL98OqO54i3Zin3KkYyQsswLlBV7p-5cfVGOkmLbsibwdoEq0wPRZ3rX_wtkt2p0NNvxgaxeEoCxfvdZPVVt0azY-8xkIBhzzYOTR45kSv-yQ64sUYW6qhtMpOd5RHUh0qsu-pY1erznc66lu-ZkgR2jekXARevY4vlanyy-tKBwGGciq6IDiP-qE8TUJntpfiK4n2Du9yliLO6sNNxn2qIr7Nz2ro0FJI1rNhMB9sL94a8rrefLkJ-hLycGaCRI-GzCQBYs2WF-LIK_DDOoptbdbyfAF-vyrHBVezIdYn7qR2w4Ug-qgW6PkRRcja5M2QO-ib5shsmJhDyRw4_u2hj75I5pIktV6iYPaRpao4Aa1-tIr1Mk6dcDKji0vt57s7SgUtgJ__NJ60Z9zzBG-nMdyZHx3EeR0MBimnkb89aselrS7mV_vT0KS-vonxWaydqWCNVDDzYUV_PXSfiyUZdWGGM-8O-xtxC5j1ysIwZBhL6RqgoEFkoaZjRHTY70kqfwQK5bVbcvQU7lQ5FUpSYEszsIASri9UB5xr2LXuK7syb-2pxsPbc0FCnKgTYe2RMSgdXqnqmhHcl53s3AvDeJk8-2c212YPJjd6T9DI5KpGHHVAK06GnHArwrYV2aEGTtcHLSBQRM0A06B5Ou5dh2DbKur7m4tM1kv65TlVziko9DK_LaKpOGAf-HohddJQfY0usLh5dsJWzT_PjvrnYrBXBW474V7CA5z21DC0VkD1b5wKbZITPsbBMDlh7Qqo1ffUrwh_8mPWOC1dv3HwuiRvXNP2MvEYPrKifo6ec0Dv2XhT3gSZEVfk_jSWUSVOTSJcwxNFQIzCDG4YHd4NhjaiTtpLMYI6VVkpsJEaQU3n79rs5NRW_8FO1VxYMDCfLAHYxIxGXyhlXXVDtvcN9Eu99q8nIbIRU4Roc--J18Sn9kyPjOAs29JCosC53O3IHJ02EnqA0tBPTiW2rpTyd2O8oQSmdlPHwoG3paVm7Jv-UEgRNzNrCvF69V-dhis6l4OFxuZf3WPdyT1uNThR1TVye6fKVBi-3fvJN5R7FV17e4-OCvQPAakfRljkOXbMGcG_JhJOIXkAnsSJhB40Xb9skjAkuHn9bvKZJTvPjopQ9ZiDzmr1tOqhWskqGHOWN5vFQIzr1N-gDx0LvV8VFTfTJluFSQH-o0xf40AmpyfqDb8vF0JyT9YCCeASuaAQ1p0i-Lgy0uQov1267QjtDLsiEa4UojaoIpQf100iz-QC3abCYDz5Dao7BuBThS2Wp80_GO4UjtLoPiNISN0DjVv9wh-l3Z5R6msU--9xby971t7h-_itde4ceXtuZjOX41zCqoxL7o1VakZy-abbM12L1ERIY0T13QUFsEJFWKolIZIdU4-ECqblZwyBpWB1Cy70ulBqXWIR4LvyBrWALNrYFCQVHFZMAag5QJcVTK_8nf4cNlacxk4UCqwcjbC0kIjuaNnB0NPxs2APSPlcokKy1--qwG8YtytrBnHd3Wx2AU0LfgUDbRk76W_EsW0SJmRlgLXg5b5YsC5Oq19WARyl42PRQSHfaE1eIWqzKGnIOQAKmbVK0bQb_XGqEtSY1bH65K-OAKU4DGJyzZKRrR0_5hxVALdkstATRdVb8Q22AiZMCYMWzHb55TG6tCRzzkPYF5s28wJcebQHhxi6BFopSHAABT5fnBPa_aIuRVcOBIkACiV_eSn02tYaEKLHrQBd1PuKWfJfudH2QyquUDmx4CWKN9P0PaOvtXMn4rafss2tP2NcgAQ5GGlTZg8oQYBparRH-rdPF8oqxSU7h6YqBcX444ST2C7pZRuPX5nGdjjGcuN_HS7WxMPJGJzRMPVZXRSXb4ROwF2-hGGZBAzYERYVNyLUwmdOZybkj9wekiX8QEeZCR25gdOeoUIp_t6tbiwDqBf3PCIFK1DFkikLnUMvuNAxvewErykL4H9wjK6JaNRvArQqjqS-qcSIzDtGWgL8-QnlZhG2TMYaXEfv_aXuhSW_igxBvHczWzaDIcWzq1E4DC_xOx1zOXUyiQ7SF6Z_xlttwc8LxtPHFvldeIcOLeFKRcn8BsBoEH_GD2PITXAPOVSiwNuL6CfVDOu5zJEyK-ThlzibxMeJtxPYDnszZr1l3H8g_eKpO8NLOAiooHk0Il_PPOK3DyKVdDbZCQY7kqImfCrx5O0-C8QImXjzTP0-EX9ewZ0lWtYKiXEZCs_7brlk2mc7Wau13cmn0tFgIGgPwDnGMvcl-k1BFleRcMHmvj6dE-8mRvwPxGdjtEwTSk1ZtRh356DV8RjcrCZ0bch_50X-ssvbHJ5TLmeFxitw0YqbBcqBqd_JdF3vGy0K6Lo1_zA9C6Md9uobVCLrdpJW8Xl6glymQOWEf8U-J7zvHy5sBZxibEPRVOudtkiYWG4Q3uy9k4fp9dz6eotLjKQ9ozIPjjPFNqxl_ELKLqP2YmQW7-aRcvxs6iSuPAD3tvky36MVnw3_oTkzktMSneTQt0X_aI3UWCHWtoltNxIMwe6v8_wwLeS62X92XxsM4IPPxjMW_OgkyxVlmK0eJOyQIYw_OTWa3IhdYnXJ5CugX9jIlKpkOfrHAcWrpViOaWcnnZJ4e9_M2Oe0HddV3FuefITg8lIJaIS2gUxwWMJyUhkaeuvAk_3sJ5Oa3wU0zHQ51axdQX4q7ySwoQEbKDmgzzUKOaobOuh3qxndxHd2J0P4zAPxSTQZDqrx26aeJEm894bq5wjfk2Ztku6Z56RObNFkWKT0p7pB3B5vJAjIJRD_wyQibVDrJsIOvKiymZkckTJgXKGR7saj6R-4ZkmP9qq6KgqijQx7aPdyWOp3PcNSpRiE_kZ_sQli4e3-xfWAPiQb2V3Z4spSoK2b4ySZVvGcMpVauB4ewCkbYkXA__paOMbAnWlgN_v44Pu_Qdymdgee2duSovq2A0b944leE1WTViRRluE-zSQyJ69VL1ktxVERzer-2SNWJ9g-Q_hR8RqhVWnQf8XQcNwrvg3jM.8wg_021qSoHNr3b0eHqjhw"

# Payload z HAR
PAYLOAD = {"purchase_items": [{"id": 21872241924, "type": "transaction"}]}

URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"


def build_session(use_ff152_fingerprint=True, use_har_ua=False):
    """Buduje sesję curl_cffi z odpowiednim fingerprintem i nagłówkami."""
    session = requests.Session()
    
    if use_har_ua:
        ua = HAR_UA
    else:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"
    
    session.headers.update({
        "User-Agent": ua,
        "Accept": "application/json,text/plain,*/*,image/webp",
        "Accept-Language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json",
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
        "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Anon-Id": HAR_X_ANON_ID,
        "X-Csrf-Token": HAR_X_CSRF_TOKEN,
        "X-Incognia-Request-Token": HAR_INCOGNIA_TOKEN,
        "Priority": "u=3",
        "Locale": "pl-PL",
    })
    
    return session


def test_checkout_build(session, label, use_custom_fingerprint=True, use_chrome_impersonate=False):
    """Testuje endpoint checkout/build."""
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")
    
    print(f"URL: {URL}")
    print(f"Headers sent:")
    for k, v in session.headers.items():
        if k.lower() in ['x-anon-id', 'x-csrf-token', 'x-incognia-request-token', 'user-agent']:
            display = v[:80] + "..." if len(v) > 80 else v
            print(f"  {k}: {display}")
    
    try:
        if hasattr(session, 'post') and use_custom_fingerprint:
            # curl_cffi Session with custom fingerprint
            resp = session.post(
                URL,
                json=PAYLOAD,
                impersonate="chrome131" if use_chrome_impersonate else "firefox133",
                ja3=FF152_JA3,
                akamai=FF152_AKAMAI,
                extra_fp=FF152_EXTRA_FP,
                timeout=30,
            )
        else:
            resp = session.post(URL, json=PAYLOAD, timeout=30)
        
        print(f"\nResponse: HTTP {resp.status_code}")
        print(f"Response headers: {dict(resp.headers)}")
        
        try:
            data = resp.json()
            print(f"Response JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            print(f"Response text: {resp.text[:500]}...")
        
        return resp
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("Testing curl_cffi checkout/build with various configurations...")
    
    # Test 1: Firefox 152 fingerprint + Firefox UA + HAR token
    print("\n\n>>> TEST 1: FF152 fingerprint + FF152 UA + HAR token")
    s1 = build_session(use_ff152_fingerprint=True, use_har_ua=False)
    test_checkout_build(s1, "FF152 fingerprint + FF152 UA", use_custom_fingerprint=True, use_chrome_impersonate=False)
    
    # Test 2: Firefox 152 fingerprint + Chrome/Opera UA (from HAR) + HAR token
    print("\n\n>>> TEST 2: FF152 fingerprint + HAR UA (Chrome/Opera) + HAR token")
    s2 = build_session(use_ff152_fingerprint=True, use_har_ua=True)
    test_checkout_build(s2, "FF152 fingerprint + HAR UA", use_custom_fingerprint=True, use_chrome_impersonate=False)
    
    # Test 3: Chrome 131 profile (curl_cffi built-in) + HAR UA + HAR token
    print("\n\n>>> TEST 3: chrome131 profile + HAR UA + HAR token")
    s3 = requests.Session()
    s3.headers.update({
        "User-Agent": HAR_UA,
        "Accept": "application/json,text/plain,*/*,image/webp",
        "Accept-Language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json",
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
        "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Anon-Id": HAR_X_ANON_ID,
        "X-Csrf-Token": HAR_X_CSRF_TOKEN,
        "X-Incognia-Request-Token": HAR_INCOGNIA_TOKEN,
        "Priority": "u=3",
        "Locale": "pl-PL",
    })
    test_checkout_build(s3, "chrome131 profile + HAR UA", use_custom_fingerprint=False)
    
    # Test 4: Bez x-incognia-request-token (sprawdź czy endpoint go wymaga)
    print("\n\n>>> TEST 4: FF152 fingerprint + BEZ x-incognia-request-token")
    s4 = build_session(use_ff152_fingerprint=True, use_har_ua=False)
    s4.headers.pop("X-Incognia-Request-Token", None)
    test_checkout_build(s4, "FF152 fingerprint, NO Incognia token", use_custom_fingerprint=True, use_chrome_impersonate=False)
    
    print("\n\n>>> DONE")