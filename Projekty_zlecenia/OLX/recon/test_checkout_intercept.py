import json
from playwright.sync_api import sync_playwright
from pathlib import Path

brain_dir = Path(r"C:\Users\Ksawier\.gemini\antigravity\brain\dda6a6ab-b8d9-4fbb-bd33-521ac9843d92")

cookies_playwright = [
    {"name": "user_business_status", "value": "private", "domain": ".olx.pl", "path": "/"},
    {"name": "deviceGUID", "value": "7a86fee8-3caa-4c02-a02a-2b40c5cfc11b", "domain": ".olx.pl", "path": "/"},
    {"name": "user_id", "value": "2553769477", "domain": ".olx.pl", "path": "/"},
    {"name": "user_uuid", "value": "06727a02-0312-4a9e-b6f6-e6b1fd331594", "domain": ".olx.pl", "path": "/"},
    {"name": "PHPSESSID", "value": "9ua5pioo06eqb7ss9i9ps0j9kr", "domain": ".olx.pl", "path": "/"},
    {"name": "access_token", "value": "eyJraWQiOiJSTWxVTFJrZXkvMVdTNDl5NXBJd0tMV2lqQVlSN3lRZU1nTSt2S0R6ZUFjPSIsImFsZyI6IlJTMjU2In0.eyJhdF9oYXNoIjoiR2dGbU5DY244S29Ic3dIZmpGLVl1QSIsInN1YiI6IjA2NzI3YTAyLTAzMTItNGE5ZS1iNmY2LWU2YjFmZDMzMTU5NCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJpc3MiOiJodHRwczovL2NvZ25pdG8taWRwLmV1LXdlc3QtMS5hbWF6b25hd3MuY29tL2V1LXdlc3QtMV9kVWpGdXZUZjQiLCJjb2duaXRvOnVzZXJuYW1lIjoiNGZhMGQ4ZDktZTc5ZC00ZTQ1LWI4MzYtN2M5ZDQ2ZGVjYjJhIiwibm9uY2UiOiJNVXh6dl95aW5pOGY0RENvVU5QaGtDMWVkNGV3ZEZXYTNYcEVzalE1VFlXWDdULVZSRkRIVWJqdEttd0hCaGtJWTh5QVdJUnhnb09BWjlwd1N1VEFUdWdLRXNxbXNnUWV3b29tR3g2ZnZtd3UwdkZLejhfMGI1Q1lSU0s3bVpJVlRSWWZJdjRnd0dxV2t6ZVBYVndMSVgtVGtJdmJBa1I4WklTQVhIWEY5Uk0iLCJvcmlnaW5fanRpIjoiMzEwMGViMjItN2U0NS00NDM0LWI0MmYtMjYwMGM0OWQ4M2IxIiwiYXVkIjoiNmo3ZWxrMDFwMzJvNjQ4bzFpbzhsdmhoYWIiLCJpZGVudGl0aWVzIjpbeyJ1c2VySWQiOiIxMDIzMTQ2OTU0NzkwNjU3MjA0MDQiLCJwcm92aWRlclR5cGUiOiJHb29nbGUiLCJpc3N1ZXIiOm51bGwsInByaW1hcnkiOiJmYWxzZSIsImRhdGVDcmVhdGVkIjoiMTc4ODI3MDEwMjg5NiJ9XSwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE3ODgyNzAxMDcsImN1c3RvbTppZHBfbGFzdF9lbWFpbCI6ImtzYXdpZXJwb3RyeWt1czNAZ21haWwuY29tIiwiZXhwIjoxNzg4MjcxMDA3LCJpYXQiOjE3ODgyNzAxMDcsImp0aSI6ImQ5MTA4ZTQzLTY4MjMtNGU5Ni1iZDZiLTUxOTY1NGQ0MmY1YyIsImVtYWlsIjoia3Nhd2llcnBvdHJ5a3VzM0BnbWFpbC5jb20ifQ.uA8uZlQrh1BWvjVokFmJ5uy3o797VQYadH_Z06rPmpWT8E5GknkJDH1eAlumNDH4fyCfB1QmdpZXEqUscvImwpagzLOA7treiDariFcRT-fMBG7idXGxPX8AO3W3g7hIb6c91jPGqcarJeJKp8g5TIu_GmohdwNHFEqKVLRVdgxxW4GOsdb70q4NaXW-k-ZUSlaXeNIs0cxUsvOUOcjerOZ9kq2s4bVFDGdmi-4HvVyYH0MTPeVNv7jQxOs36xdxv3eil70XGogRH6X05zAaExjbhbt4rt04senXpIYcLLnYVONtSy5T8CuI0ZdnbFzPAhOht8JYMa4scOi5eugztg", "domain": ".olx.pl", "path": "/"},
    {"name": "datadome", "value": "6ejM3HVLHERbn0KmEl_IwLQQXrtkbvKuG_XhH2VFxyD4gX3GHT~rwRH6CM6qZtYkue9F8ABPvZ_wOD4p6NeAOmZ7OaEPpqMYm4tvwF0Phg25YYb0UqY2~212v~Vu8srw", "domain": ".olx.pl", "path": "/"},
    {"name": "cf_clearance", "value": "0ZqJQpAvcjthUmJ4dEPtTPxd.w2uXfF1UZR4RL2KZL4-1765544202-1.2.1.1-2CKDPteIPVR0YZCO.XmaShMtvynLVOYU13OPHqYh60G1VBljRxUZ6qL7Mw2PQqEHo6yFxHNi5GIc6BC5liUH1dphkmcflJklgJfjNU2_Gz53O9lZ._4.ePV9vF6bY5ESJCIq3ppbklPtKae4y0hud9Muv1Z11Z_mpe57s3CM_PAX3sOpKZTvbedzartr7ClMvkTSzBZIIEISJrHjjDBqalYioj93rJZWSZHI14LVGNY", "domain": ".olx.pl", "path": "/"}
]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_cookies(cookies_playwright)
    page = ctx.new_page()

    api_calls = []
    def on_req(req):
        if "api" in req.url or "checkout" in req.url or "delivery" in req.url or "payment" in req.url:
            api_calls.append({
                "method": req.method,
                "url": req.url,
                "post_data": req.post_data
            })
    page.on("request", on_req)

    print("[*] Otwieram checkout przesyłki...")
    page.goto("https://www.olx.pl/delivery/checkout/1089722585/", wait_until="domcontentloaded", timeout=25000)
    page.wait_for_timeout(3000)

    print("Title checkoutu:", page.title())
    print("URL po przekierowaniu:", page.url)
    
    shot_path = brain_dir / "checkout_page.png"
    page.screenshot(path=str(shot_path))
    print("[+] Zapisano zrzut strony checkoutu:", shot_path)

    b.close()

print("\n--- PRZECHWYCONE API PODCZAS OTWIERANIA CHECKOUTU ---")
for a in api_calls[:15]:
    print(f"[{a['method']}] {a['url']}")
    if a['post_data']:
        print(f"   Data: {a['post_data'][:200]}")
