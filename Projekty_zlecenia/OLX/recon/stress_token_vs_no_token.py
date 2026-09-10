# coding: utf-8
"""
OSTRY test: czy token partnerski chroni publiczne API /api/v1/offers/{id}/.

Dwa scenariusze rownolegle w interleaved petli:
  A) BEZ tokenu - nagie zapytanie (jak obecny detektor)
  B) Z tokenem partnerskim (Bearer client_credentials)

Mierzymy:
  - statusy w czasie (kiedy pojawi sie 403/429/challenge)
  - jak dlugo wytrzymuje kazdy scenariusz
  - czy token realnie podnosi limit

Uwaga: test moze wywolac czasowy ban IP na publicznym API.
Uruchamiamy na jasna prosbe uzytkownika.
"""
import json
import time
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

CLIENT_ID = "202745"
CLIENT_SECRET = "HucUsS3hhReAr5j5V4BN5I85rlOM0y2y5cFGoKjJbXuPO5YI"


def get_token():
    r = creq.post(
        "https://www.olx.pl/api/open/oauth/token",
        data=json.dumps({
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "v2 read write",
        }),
        headers={"Content-Type": "application/json"},
        impersonate=IMP, timeout=20,
    )
    return r.json().get("access_token") if r.status_code == 200 else None


def hit(oid, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = creq.get(API + str(oid) + "/", impersonate=IMP, headers=headers, timeout=10)
        return r.status_code
    except Exception as e:  # noqa: BLE001
        return -1


def main():
    token = get_token()
    print(f"token uzyskany: {'TAK' if token else 'NIE'}")
    start = 1093568539  # aktualna okolica krawedzi

    # Interleaved: 1 zapytanie bez tokenu, 1 z tokenem, na przemian
    results_a = {}  # bez tokenu: tick -> status
    results_b = {}  # z tokenem: tick -> status

    N = 200  # po 100 na scenariusz (bezpieczne, ale pozwoli zobaczyc limit)
    for i in range(N):
        oid = start + i
        # A: bez tokenu
        sa = hit(oid, token=None)
        results_a[i] = sa
        # B: z tokenem
        sb = hit(oid, token=token)
        results_b[i] = sb

        if i % 25 == 0:
            print(f"  krok {i}: A(bez)={sa} B(z tokenem)={sb}")

        # wczesne wykrycie blokady
        if sa in (403, 429) and sb in (403, 429):
            print(f"  OBA zablokowane przy kroku {i}")
            break
        time.sleep(0.1)

    # podsumowanie
    def summarize(name, res):
        total = len(res)
        blocked = sum(1 for s in res.values() if s in (403, 429))
        errors = sum(1 for s in res.values() if s == -1)
        ok = sum(1 for s in res.values() if s == 200)
        print(f"\n{name}: ok={ok}/{total}, 403/429={blocked}, bledy={errors}")
        if blocked:
            first_block = next((i for i, s in sorted(res.items()) if s in (403, 429)), None)
            print(f"  pierwsza blokada przy kroku {first_block}")
        return total, blocked, errors, ok

    ta, ba, ea, oka = summarize("BEZ tokenu", results_a)
    tb, bb, eb, okb = summarize("Z tokenem partnerskim", results_b)

    print("\n=== WNIOSEK ===")
    if ba == 0 and bb == 0:
        print("Zaden scenariusz nie zostal zablokowany w tym zakresie (za krotki test lub brak limitu).")
    elif ba > bb:
        print("Token partnerski CHRONI: mniej blokad niz bez tokenu.")
    elif bb > ba:
        print("Token partnerski NIE chroni: blokady pojawiaja sie tak samo lub czesciej.")
    else:
        print("Token partnerski nie daje roznicy (oba zablokowane rowno).")


if __name__ == "__main__":
    main()