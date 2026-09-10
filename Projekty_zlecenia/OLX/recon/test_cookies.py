import json
import base64
import time
from curl_cffi import requests as creq

raw_cookies = {
    'user_business_status': 'private',
    'deviceGUID': '7a86fee8-3caa-4c02-a02a-2b40c5cfc11b',
    'session_start_date': '1788271899229',
    'OptanonAlertBoxClosed': '2026-09-01T13:41:40.702Z',
    'datadome': '6ejM3HVLHERbn0KmEl_IwLQQXrtkbvKuG_XhH2VFxyD4gX3GHT~rwRH6CM6qZtYkue9F8ABPvZ_wOD4p6NeAOmZ7OaEPpqMYm4tvwF0Phg25YYb0UqY2~212v~Vu8srw',
    'auth_state': 'eyJzdWIiOiIwNjcyN2EwMi0wMzEyLTRhOWUtYjZmNi1lNmIxZmQzMzE1OTQifQ==',
    'access_token': 'eyJraWQiOiJSTWxVTFJrZXkvMVdTNDl5NXBJd0tMV2lqQVlSN3lRZU1nTSt2S0R6ZUFjPSIsImFsZyI6IlJTMjU2In0.eyJhdF9oYXNoIjoiR2dGbU5DY244S29Ic3dIZmpGLVl1QSIsInN1YiI6IjA2NzI3YTAyLTAzMTItNGE5ZS1iNmY2LWU2YjFmZDMzMTU5NCIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJpc3MiOiJodHRwczovL2NvZ25pdG8taWRwLmV1LXdlc3QtMS5hbWF6b25hd3MuY29tL2V1LXdlc3QtMV9kVWpGdXZUZjQiLCJjb2duaXRvOnVzZXJuYW1lIjoiNGZhMGQ4ZDktZTc5ZC00ZTQ1LWI4MzYtN2M5ZDQ2ZGVjYjJhIiwibm9uY2UiOiJNVXh6dl95aW5pOGY0RENvVU5QaGtDMWVkNGV3ZEZXYTNYcEVzalE1VFlXWDdULVZSRkRIVWJqdEttd0hCaGtJWTh5QVdJUnhnb09BWjlwd1N1VEFUdWdLRXNxbXNnUWV3b29tR3g2ZnZtd3UwdkZLejhfMGI1Q1lSU0s3bVpJVlRSWWZJdjRnd0dxV2t6ZVBYVndMSVgtVGtJdmJBa1I4WklTQVhIWEY5Uk0iLCJvcmlnaW5fanRpIjoiMzEwMGViMjItN2U0NS00NDM0LWI0MmYtMjYwMGM0OWQ4M2IxIiwiYXVkIjoiNmo3ZWxrMDFwMzJvNjQ4bzFpbzhsdmhoYWIiLCJpZGVudGl0aWVzIjpbeyJ1c2VySWQiOiIxMDIzMTQ2OTU0NzkwNjU3MjA0MDQiLCJwcm92aWRlclR5cGUiOiJHb29nbGUiLCJpc3N1ZXIiOm51bGwsInByaW1hcnkiOiJmYWxzZSIsImRhdGVDcmVhdGVkIjoiMTc4ODI3MDEwMjg5NiJ9XSwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE3ODgyNzAxMDcsImN1c3RvbTppZHBfbGFzdF9lbWFpbCI6ImtzYXdpZXJwb3RyeWt1czNAZ21haWwuY29tIiwiZXhwIjoxNzg4MjcxMDA3LCJpYXQiOjE3ODgyNzAxMDcsImp0aSI6ImQ5MTA4ZTQzLTY4MjMtNGU5Ni1iZDZiLTUxOTY1NGQ0MmY1YyIsImVtYWlsIjoia3Nhd2llcnBvdHJ5a3VzM0BnbWFpbC5jb20ifQ.uA8uZlQrh1BWvjVokFmJ5uy3o797VQYadH_Z06rPmpWT8E5GknkJDH1eAlumNDH4fyCfB1QmdpZXEqUscvImwpagzLOA7treiDariFcRT-fMBG7idXGxPX8AO3W3g7hIb6c91jPGqcarJeJKp8g5TIu_GmohdwNHFEqKVLRVdgxxW4GOsdb70q4NaXW-k-ZUSlaXeNIs0cxUsvOUOcjerOZ9kq2s4bVFDGdmi-4HvVyYH0MTPeVNv7jQxOs36xdxv3eil70XGogRH6X05zAaExjbhbt4rt04senXpIYcLLnYVONtSy5T8CuI0ZdnbFzPAhOht8JYMa4scOi5eugztg',
    'user_id': '2553769477',
    'user_uuid': '06727a02-0312-4a9e-b6f6-e6b1fd331594',
    'PHPSESSID': '9ua5pioo06eqb7ss9i9ps0j9kr',
}

token = raw_cookies['access_token']
# Check token exp
payload_b64 = token.split('.')[1]
payload_b64 += '=' * (-len(payload_b64) % 4)
payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
print('JWT Payload:')
print('  Email:', payload.get('email'))
print('  Sub (UUID):', payload.get('sub'))
print('  Exp timestamp:', payload.get('exp'))
print('  Iat timestamp:', payload.get('iat'))
print('  Current time:', int(time.time()))
print('  Valid remaining seconds:', payload.get('exp') - int(time.time()))

headers = {
    'authorization': f'Bearer {token}',
}

endpoints = [
    'https://www.olx.pl/api/v1/users/me/',
    'https://www.olx.pl/api/v1/users/2553769477/',
    'https://www.olx.pl/api/v1/users/2553769477/details/',
    'https://www.olx.pl/api/v1/users/me/billing/',
    'https://www.olx.pl/api/v1/delivery/buyers/profile/',
    'https://www.olx.pl/api/v1/delivery/orders/saved-addresses/'
]

for ep in endpoints:
    try:
        r = creq.get(ep, cookies=raw_cookies, headers=headers, impersonate='chrome124', timeout=5)
        print(f'{ep} -> Status: {r.status_code}, Body: {r.text[:200]}')
    except Exception as e:
        print(f'{ep} -> Error: {e}')
