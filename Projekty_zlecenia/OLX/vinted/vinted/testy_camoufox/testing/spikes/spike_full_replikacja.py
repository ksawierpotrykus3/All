# coding: utf-8
"""Spike A3: Pełna replikacja requestu Camoufox - dokładnie skopiowane nagłówki + JWE Incognia.

Wniosek z A1: samo posiadanie cookie datadome NIE wystarczy - 403 captcha.
Z A2 mamy dokładny request z prawdziwej sesji Camoufox (pełny JWE Incognia).
Pytanie: czy curl_cffi z tymi nagłówkami przejdzie?

Testowane warianty:
  R1: curl_cffi + wszystkie nagłówki + cookie (surowy string)
  R2: R1 + sekwencja: najpierw curl_cffi GET item → potem POST build
  R3: R1 + dodanie Sec-Fetch-* + User-Agent Firefox 152
  R4: curl_cffi z headers dict (nie tylko dict, ale dokładna kolejność z Camoufox)
  R5: Bez Incognia nagłówka (sprawdzić czy sam cookie wystarczy)
  R6: Pełny HEAD + OPTIONS na checkout/build (sprawdzić CORS)
"""
import json
import sqlite3
import time
from pathlib import Path
from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
ITEM_ID_REAL = 21872241924  # ten który Camoufox faktycznie zarezerwował
OUTPUT_TMP = Path(r"C:\Temp\wynik_spike_full_replikacja.json")


def wczytaj_cookies(profil: str) -> dict:
    cookies = {}
    db = Path(profil) / "cookies.sqlite"
    if not db.exists():
        return cookies
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%vinted.pl%'")
        for n, v in cur.fetchall():
            cookies[n] = v
    finally:
        conn.close()
    return cookies


def probe(name, url, method="POST", impersonate="chrome131", cookies=None, headers=None,
          data=None, timeout=20):
    t0 = time.monotonic()
    try:
        if method == "GET":
            r = creq.get(url, headers=headers, cookies=cookies or {},
                         impersonate=impersonate, timeout=timeout)
        else:
            r = creq.post(url, headers=headers, cookies=cookies or {},
                          impersonate=impersonate, timeout=timeout, json=data)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {
            "name": name, "status": r.status_code, "elapsed_ms": elapsed,
            "body_preview": r.text[:400] if r.text else "",
        }
    except Exception as e:
        return {"name": name, "status": None, "error": repr(e)}


def main():
    cookies = wczytaj_cookies(PROFIL)
    # Prawdziwe nagłówki z Camoufox (z A1)
    JWE = "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkExMjhDQkMtSFMyNTYifQ.VlrXOi1TbdNvmzTQoCwDt4wfVgftfBmLCkPq7MRNAG-qrxr9ANpOmCZ90T0NIG1DYFJM3EjqZKzrmyb9I-BviH1OJ21bjADta8iPmyoTUYMkAIfEdLe0kcp9E1jLbSyu8Dk8yNysg4P-V7y6EsxVlok1OQ1A5e_LUS0Ek8hgcR197DIQv5Pb5Eyxz0cTYv8wLjfLX39nPTUI64omA9b8_dgVf7I9sUdfsi4BD1Rb9V3Tb_qhbrSa81LTdp6oyrN9v5xEcEj1FlCQAvVxOGXaN-cYK5uGSJFw1APihUqTUeA-6i-v04iOFG4zsfK3RKgzymm2TPC1QsN0Ix0dQSgpJw.unc5lSRd6nie-kVkw6lexg.7ku46qO-Kp8GiuGy8haGKR6tDlstQ3Susnr_NScAET-cNGMBwikahA21SNAiFY71VGSdWNuWyvNMcHj1IQJhTAUDz6jAw2eecoNg6baYBWE-udh-19lfaJB9HkMPr5VXav4dIyQz77GNf76fIoqQDWAx1w53rTG28Kn9TNbakdJksvx6D99O5BTxOKFL0Xo4Jp1s4BG9i9Jce0Ms5kzWy14HbaWzl1FsirvrUtBTOiJDoCk4mTczazwxuptsBriULCpbokiMYbPZwMAgsSUZiyAuM7NLplbFlzEa63wAFXOf6TVQ22ZBgulUq_djGxvtZbQqJN7Uj3Hl31r4rTZ0D9sR6Ti1vU2Tiyh7t-Az_xT15lQ3Qa5uf-6dJAe_xwWdZnonQDuYcmttw_P983Elmfd4Um1tF8KJo2nCy2yepCKMhVHTPeKKIy4x0-0LN38CEYEDtPX2sD-iMAwd_S0LpcSVKIaeSXbh1snTnrLuzxlVLVEOMhdIIlcxXpssyv1z6EIMclGL8z-5UWztWfY-a7orJB4dZ8V25H-LMTZquhXrOmn8xkGbaRndcG0IsWejhGxUpBRxDy0QSfIntUJIZhZkvrfpbKLSXO2DI9A1ERwiraZwEK1D90lhGxpFjccLxjCTJYj4Iw2d86xXUcjDvA1YydM-SOPDhhTfWn0Qnt95PJd5jkCT0QOYw2Lh_QQq0X5cZ7pdW9jVtcrPHR57GjFNLShLDdl598guPtLX7VyZ2CyXeSV4H3BgtEJVNWqQKTKsh8H7dtvEd6FHZPjNAxdL10UVYuwvFmPk0-QKW4OftTqgDISH4VS-g9c944J4_vAUmflPATlIKs8zHclHtRx55oIHkEq82Ihq3i7gkHIwYQsrw_MKhAwUika-Q0TJMkv9ScV29lo9sAU2XNEXITNxKmNYM5qfMLpq-1PpimCBuvuvlOg9yLUkmA8F1ym2ir-XDblaMsI73M8B8uSTX44YwGJqOK4qjEuEgg26G_IqXDoLJl0zUroyY9NLm3Y49rEYWrHTM00-t9O65Bh20H-UUZvEL-GXqFZwAdE90nTbyzxgb6EGWEHx4kkYwkgHMTDySmC-z53MqzjTKOK3niYJyUdXtqnS3L6xYUjc0y5tle6r44ImKUg0ntlE-yov-2O8ea6weiPXEchLvwPT9TQAZ7hHuq0e26CgC1P6AsJ1_ybu5n0myQ06myADaUTbM5yjYnKG9nAAvqrTjwTZuOuT9ofEkT9tGGxK_Mr2mxuEsVFG-6l-yVk-gOsbDW_0CGSJ4F-Ji0RzrdIuiGk-qzlpkWd9HMutB0sH8TxywcjGjti-LHF7zk8Ku21P3D5tMzw3Q_4RFhBug5Bp7x5a7nS4rHU7qIM8shaSq7mCVJOhVKY40q5Z7ze6ugO_EyCJursbRzPb-I0o5m_bscEUrAR_dToIbaQvkaEU1Oms2TQjyqS5y5QXnx5tco7qMArEfohC64hIA75qeuKEucstptIaLCWajyQZk7rIb5F4aDjxspSGJwMCIwY2AwcGkqRcWawZCwpeKjjpU-7OFLcXxbErLqGkmiqGEx6gY3zvx-Z-kAd2Y4mKNPggH5nShiwsjC9LJYs7nUXM0Fwq0tzN43Qfytf1xsCJ0BbK76hCqEzze__bLjistmdYur4e02zZFfi3pqJ9deEybqd9yxmK85KReirHPNlQeUS20Si67oJt0hXKinnEajWWCEYIv0Fyvm8h2Ig3q6UgoAuuiuFcn_dalEykl7mObwSISdSeLCi4DdAzZTyTsLsqjspL6stXpyydRQnuiveeeTBRlP-ZeUPr5K4LlfnhV39oWtQvBi0awaiUq_6ju_jACFyAmwlIP9uJJBcA0hR18LvxHu7haUr1dOpBoMV98tr5aWjVS7kTigHkV0BnZybk77jJNDgKgGDsGm3rQSUrcb8WM7IgkP8Xik9gX1gYa1pbM3r4rYC-cuz6z3v_z63CSqtKD1h6QN_RpCbI0cIvxTO330tcG3w2CkTFUtDv26ahWTWnjBxahiTzFzIsnA3hGiSpWunPI66mVpLkqNSUPgLhTcopOClHblHdl1Cp62ouJq2ivJI7tGogy-8dlj9aqXoLDoUldNIbuxEd7A6kBIJ2fyUqDw3rLvkSdb1-2HpXHJdEPhrDsPO7DzGwMeIuomIaB6c0UzbcICoFYFZOqAVkxkMW-DRpERU4B4BWeF3Hrej_Mc-zeTU_zz4vr63WcPpB5jOdaqyAt-v4350RT9IBS2_evmtvu4DaK8ZxlPXkpitMWzOwNiWBRRxu5jDSSZXZDomhqmFQPnbWV1frpriXJ6lsBnEAkedbu-WDKA8vP9AJFFfdvBvpMg9bLzaIcTNjPrcr3O8XZoRs-VA6-23EbdYtUzrFUhk1AWlNj4907W22YqlIAA_A0eejhAaZz-m5RneuVVvvFw7lTCaW0P9UagX3hH_R2bw18ioedpWyvMLVcWt0Ylm0zWoXMx__BgNn6FLqPtWZ7Vu-AVC5mdmq-kDd2QkfcqJlYmfm7fhBCsWGtRiFqCd3m0yThBnFQVwWHCEsi7ChcNdIZ6nBKi768UOKg8t3jm-HN3A04-I4KLxpBbQ.hyZ1W0igGUpF6R4NQPnXcQ"

    BASE_HEADERS = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "x-incognia-request-token": JWE,
        "x-anon-id": "98c6af5a-87da-45f2-9be5-24cf9345b003",
        "x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e",
        "origin": "https://www.vinted.pl",
        "referer": f"https://www.vinted.pl/items/{ITEM_ID}",
    }

    results = {"started": time.strftime("%H:%M:%S"), "tests": []}

    # === R1: pełna replikacja ===
    payload = {"purchase_items": [{"id": ITEM_ID_REAL, "type": "transaction"}]}
    r = probe("R1_full_replica", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              impersonate="chrome131", cookies=cookies, headers=BASE_HEADERS, data=payload)
    results["tests"].append(r)

    # === R2: najpierw GET item (symulacja zachowania przeglądarki) ===
    r_get = probe("R2_pre_get", f"https://www.vinted.pl/items/{ITEM_ID_REAL}",
                  method="GET", impersonate="chrome131", cookies=cookies,
                  headers={"user-agent": BASE_HEADERS["user-agent"]})
    time.sleep(0.5)
    r = probe("R2_after_get", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              impersonate="chrome131", cookies=cookies, headers=BASE_HEADERS, data=payload)
    results["tests"].append({"name": "R2_get_then_build", "get_result": r_get, "build_result": r})

    # === R3: dodanie sec-fetch i Firefox UA ===
    headers_r3 = {**BASE_HEADERS,
                  "sec-fetch-dest": "empty",
                  "sec-fetch-mode": "cors",
                  "sec-fetch-site": "same-origin"}
    r = probe("R3_with_sec_fetch", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              impersonate="firefox133", cookies=cookies, headers=headers_r3, data=payload)
    results["tests"].append(r)

    # === R4: bez Incognia nagłówka (tylko cookies) ===
    headers_r4 = {k: v for k, v in BASE_HEADERS.items() if k != "x-incognia-request-token"}
    r = probe("R4_no_incognia", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              impersonate="chrome131", cookies=cookies, headers=headers_r4, data=payload)
    results["tests"].append(r)

    # === R5: z Incognia ale BEZ cookies (tylko nagłówki) ===
    r = probe("R5_no_cookies", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              impersonate="chrome131", cookies={}, headers=BASE_HEADERS, data=payload)
    results["tests"].append(r)

    # === R6: HEAD na checkout/build (sprawdzenie CORS) ===
    r = probe("R6_head", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="GET", impersonate="chrome131", cookies=cookies, headers=BASE_HEADERS)
    results["tests"].append(r)

    # === R7: PUT zamiast POST ===
    r = probe("R7_put", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              method="GET", impersonate="chrome131", cookies=cookies,
              headers={**BASE_HEADERS, "x-http-method-override": "POST"}, data=payload)
    results["tests"].append(r)

    # === R8: z referer do mojego item_id (9807925466 zamiast 21872241924) ===
    headers_r8 = {**BASE_HEADERS, "referer": f"https://www.vinted.pl/items/{ITEM_ID}"}
    r = probe("R8_my_item_id", "https://www.vinted.pl/api/v2/purchases/checkout/build",
              impersonate="chrome131", cookies=cookies, headers=headers_r8, data=payload)
    results["tests"].append(r)

    results["summary"] = {
        "total": len(results["tests"]),
        "passed_200": sum(1 for r in results["tests"] if r.get("status") == 200),
        "captcha_403": sum(1 for r in results["tests"] if r.get("status") == 403),
        "other": sum(1 for r in results["tests"] if r.get("status") not in (200, 403, None)),
    }
    results["finished"] = time.strftime("%H:%M:%S")
    OUTPUT_TMP.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results["summary"], ensure_ascii=False, indent=2), flush=True)
    for t in results["tests"]:
        print(f"  {t['name']}: {t.get('status') or t.get('error', 'N/A')[:50]}", flush=True)
    print(f"Zapisano {OUTPUT_TMP}", flush=True)


if __name__ == "__main__":
    main()
