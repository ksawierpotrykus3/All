# coding: utf-8
"""Szybki test: czy x-incognia-request-token to brakujący nagłówek dla checkout/build.

Używa zapisanego cookie jar (cookies_profil.json) + tokenu JWE z HAR (z udanego builda).
Porównuje: z tokenem Incognia / bez tokena / z fałszywym tokenem.
"""
import json
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# JWE token z HAR (udany build 08-29)
JWE_HAR = "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkExMjhDQkMtSFMyNTYifQ.oiK8KBQ2KtW_dPBysaPHF5aKgMZFXL-52K6CZMMRsVrnuAxq7agrwy-ds7U2X7f0XFKrgr6xQOcIVwDnjnPD22-xIok-JHPhcOpTb0BsFhZflIFvsVAoTVdmNweogzqPNjkiUKux7WaeN9L4T01PXHlk5vC48eV7NU8LC8TS-6IrBbaciYRnKfENYciPYRhKPf3CEZgmGeTaXlAh2hjve3yf9K2NC5rCOXuAMNM5Vi07zvnmCPT7r"


def build_session():
    s = cr.Session()
    cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:  # noqa: BLE001
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/items/9823932531",
        "priority": "u=3",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    })
    return s


def post_build(s, extra_headers, label):
    body = {"purchase_items": [{"id": 9823932531, "type": "item"}]}
    headers = {"x-csrf-token": CSRF, "x-anon-id": ANON}
    headers.update(extra_headers)
    r = s.post(BUILD_URL, json=body, headers=headers,
               impersonate=BrowserType.chrome146, timeout=30, allow_redirects=False)
    print(f"[{label}] status={r.status_code} body={r.text[:180]}")
    return r


def main():
    s = build_session()
    post_build(s, {}, "bez incognia")
    post_build(s, {"x-incognia-request-token": JWE_HAR}, "JWE z HAR")
    post_build(s, {"x-incognia-request-token": "bogus.token.abc"}, "JWE bogus")
    post_build(s, {"x-incognia-request-token": JWE_HAR, "x-incognia-sdk-version": "2.0.0"}, "JWE + sdk-version")


if __name__ == "__main__":
    main()
