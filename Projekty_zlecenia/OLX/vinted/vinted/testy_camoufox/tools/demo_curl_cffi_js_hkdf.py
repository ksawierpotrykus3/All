"""
Demo edukacyjne: curl_cffi (transport TLS/HTTP2) + Node.js subprocess (kryptografia HKDF/JWE).

Architektura podziału ról:
- curl_cffi: warstwa transportowa — TLS fingerprint (JA3/JA4/Akamai), HTTP/2, nagłówki, ciało requestu
- Node.js: warstwa kryptograficzna — WebCrypto API (HKDF, AES-GCM, RSA-OAEP, JWE)

Używane biblioteki:
- curl_cffi 0.15.0 (impersonate + custom ja3/akamai/extra_fp)
- cryptography 44.0.3 (RSA, AES, HKDF w Python jako referencja)
- Node.js v24 (WebCrypto API: SubtleCrypto) — zero dodatkowych zależności

Cel: pokazanie jak rozdzielić "co robi przeglądarka w TLS" od "co robi SDK w JS".
"""

import json
import subprocess
import sys
import base64
import os
from pathlib import Path
from typing import Dict, Any, Optional

# curl_cffi z custom fingerprintem Firefox 152
try:
    from curl_cffi import requests
except ImportError:
    print("curl_cffi nie zainstalowane: pip install curl_cffi")
    sys.exit(1)

# Stałe z pomiarów spike_ja3_firefox152.py i spike_curl_cffi_firefox152.py
FF152_JA3 = "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,4588-29-23-24-25-256-257,0"
FF152_JA4 = "t13d1617h2_86a278354501_3cbfd9057e0d"
FF152_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"

FF152_EXTRA_FP = {
    "tls_delegated_credential": "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:ecdsa_secp521r1_sha512:ecdsa_sha1",
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",
}

FF152_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"

# Endpoint testowy do weryfikacji fingerprintu
PEET_URL = "https://tls.peet.ws/api/all"

# Ścieżka do skryptu Node.js (obok tego pliku)
NODE_SCRIPT = Path(__file__).with_name("demo_node_crypto.js")


def build_curl_cffi_session() -> requests.Session:
    """Buduje sesję curl_cffi z fingerprintem Firefox 152."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": FF152_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    })
    return session


def test_tls_fingerprint(session: requests.Session) -> Dict[str, Any]:
    """
    Sprawdza czy curl_cffi prezentuje fingerprint Firefox 152.
    Zwraca dane z tls.peet.ws (JA3, JA4, Akamai, ciphers, extensions).
    """
    print(f"[curl_cffi] GET {PEET_URL}")
    print(f"[curl_cffi] JA3 target: {FF152_JA3}")
    print(f"[curl_cffi] Akamai target: {FF152_AKAMAI}")

    resp = session.get(
        PEET_URL,
        impersonate="firefox133",  # bazowy profil, nadpisujemy niżej
        ja3=FF152_JA3,
        akamai=FF152_AKAMAI,
        extra_fp=FF152_EXTRA_FP,
        timeout=15,
    )
    print(f"[curl_cffi] HTTP {resp.status_code}")
    data = resp.json()
    tls = data.get("tls", {})
    print(f"[curl_cffi] JA3 hash: {tls.get('ja3_hash', 'N/A')}")
    print(f"[curl_cffi] JA4: {tls.get('ja4', 'N/A')}")
    print(f"[curl_cffi] Akamai: {tls.get('akamai_fingerprint', 'N/A')}")
    return data


def run_node_crypto(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uruchamia Node.js subprocess z operacją kryptograficzną.
    Node.js używa wbudowanego WebCrypto API (globalThis.crypto.subtle).
    """
    input_data = json.dumps({"operation": operation, "payload": payload})
    result = subprocess.run(
        ["node", str(NODE_SCRIPT)],
        input=input_data,
        capture_output=True,
        text=True,
        timeout=10,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node.js error: {result.stderr}")
    return json.loads(result.stdout)


def demo_hkdf_derive() -> None:
    """
    Demonstracja HKDF (RFC 5869) — derive key z sdkInstanceId.
    Incognia używa HKDF-SHA256 z salt=iid + ikm=instanceId → klucz AES-GCM.
    """
    print("\n=== DEMO: HKDF derive key (Incognia pattern) ===")

    # Symulowane dane z SDK Incognia (z deobfuskacji sekcji 14)
    sdk_instance_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # przykładowy UUID v4
    salt = b"iid"  # stała z kodu SDK (string "iid")
    ikm = sdk_instance_id.encode("utf-8")
    info = b"incognia-sdk-v1"  # context info
    length = 32  # 256-bit key for AES-256-GCM

    print(f"[Python] sdkInstanceId: {sdk_instance_id}")
    print(f"[Python] salt: {salt.hex()}")
    print(f"[Python] info: {info}")
    print(f"[Python] length: {length} bytes")

    # Wywołanie Node.js (WebCrypto SubtleCrypto)
    result = run_node_crypto("hkdf", {
        "hash": "SHA-256",
        "salt": base64.b64encode(salt).decode(),
        "ikm": base64.b64encode(ikm).decode(),
        "info": base64.b64encode(info).decode(),
        "length": length,
    })

    derived_key_b64 = result["derivedKey"]
    derived_key = base64.b64decode(derived_key_b64)
    print(f"[Node.js] Derived key (hex): {derived_key.hex()}")
    print(f"[Node.js] Derived key (b64): {derived_key_b64}")

    # Weryfikacja w Python (cryptography) — independence check
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    )
    py_key = hkdf.derive(ikm)
    print(f"[Python] Derived key (hex): {py_key.hex()}")
    print(f"[Python] Match Node.js: {py_key == derived_key}")


def demo_aes_gcm_encrypt_decrypt() -> None:
    """
    Demonstracja AES-256-GCM — szyfrowanie payloadu Incognia.
    Klucz z HKDF, losowy nonce (12B), AAD (additional authenticated data).
    """
    print("\n=== DEMO: AES-256-GCM encrypt/decrypt (Incognia payload) ===")

    # Klucz z poprzedniego kroku (HKDF)
    # Używamy znanego klucza testowego dla powtarzalności
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    nonce = bytes.fromhex("000102030405060708090a0b")  # 96-bit nonce
    aad = b"incognia-sdk-v1"  # additional authenticated data
    plaintext = b'{"event":"session_start","ts":1725000000,"sid":"abc123"}'

    print(f"[Python] key: {key.hex()}")
    print(f"[Python] nonce: {nonce.hex()}")
    print(f"[Python] aad: {aad}")
    print(f"[Python] plaintext: {plaintext}")

    # Node.js encrypt
    result = run_node_crypto("aes_gcm_encrypt", {
        "key": base64.b64encode(key).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "aad": base64.b64encode(aad).decode(),
        "plaintext": base64.b64encode(plaintext).decode(),
    })

    ciphertext_b64 = result["ciphertext"]
    tag_b64 = result["tag"]
    ciphertext = base64.b64decode(ciphertext_b64)
    tag = base64.b64decode(tag_b64)
    print(f"[Node.js] ciphertext (b64): {ciphertext_b64}")
    print(f"[Node.js] tag (b64): {tag_b64}")

    # Node.js decrypt
    result = run_node_crypto("aes_gcm_decrypt", {
        "key": base64.b64encode(key).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "aad": base64.b64encode(aad).decode(),
        "ciphertext": ciphertext_b64,
        "tag": tag_b64,
    })

    decrypted = base64.b64decode(result["plaintext"])
    print(f"[Node.js] decrypted: {decrypted}")
    print(f"[Node.js] Match: {decrypted == plaintext}")

    # Python verify
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    py_decrypted = aesgcm.decrypt(nonce, ciphertext + tag, aad)
    print(f"[Python] decrypted: {py_decrypted}")
    print(f"[Python] Match Node.js: {py_decrypted == decrypted}")


def demo_jwe_rsa_oaep_aes_cbc() -> None:
    """
    Demonstracja JWE (RFC 7516) z alg=RSA-OAEP, enc=A128CBC-HS256.
    To format odpowiedzi z endpointu cchd_config (spike_cchd_config_live.py).
    """
    print("\n=== DEMO: JWE RSA-OAEP + A128CBC-HS256 (cchd_config format) ===")

    # Generujemy parę kluczy RSA na potrzeby demo (w rzeczywistości klucz publiczny z cchd_config)
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    print(f"[Python] Generated RSA-2048 keypair")
    print(f"[Python] Public key (PEM head): {public_pem[:80]}...")

    plaintext = b'{"publicKey":"-----BEGIN PUBLIC KEY-----\\nMIIBIjAN...\\n-----END PUBLIC KEY-----"}'

    # Node.js: JWE encrypt (RSA-OAEP + A128CBC-HS256)
    result = run_node_crypto("jwe_encrypt", {
        "publicKeyPem": public_pem,
        "plaintext": base64.b64encode(plaintext).decode(),
        "alg": "RSA-OAEP",
        "enc": "A128CBC-HS256",
    })

    jwe_token = result["jwe"]
    print(f"[Node.js] JWE token (compact): {jwe_token[:80]}...")

    # Parsowanie JWE (5 części kropką)
    parts = jwe_token.split(".")
    print(f"[Node.js] JWE parts: protected={parts[0][:40]}..., encrypted_key={parts[1][:40]}..., iv={parts[2][:40]}..., ciphertext={parts[3][:40]}..., tag={parts[4][:40]}...")

    # Node.js: JWE decrypt
    result = run_node_crypto("jwe_decrypt", {
        "privateKeyPem": private_pem,
        "jwe": jwe_token,
    })

    decrypted = base64.b64decode(result["plaintext"])
    print(f"[Node.js] Decrypted: {decrypted}")
    print(f"[Node.js] Match: {decrypted == plaintext}")


def demo_full_flow() -> None:
    """
    Pełny flow edukacyjny:
    1. curl_cffi robi request z fingerprintem FF152 (transport)
    2. Otrzymuje JWE z cchd_config (symulowane)
    3. Node.js deszyfruje JWE (kryptografia)
    4. Node.js robi HKDF z sdkInstanceId (klucz sesyjny)
    5. Node.js szyfruje payload AES-GCM (x-incognia-request-token)
    6. curl_cffi wysyła request z gotowym tokenem
    """
    print("\n=== DEMO: PEŁNY FLOW EDUKACYJNY ===")
    print("Krok 1: curl_cffi - transport (TLS fingerprint FF152)")
    session = build_curl_cffi_session()
    tls_data = test_tls_fingerprint(session)

    print("\nKrok 2: Symulacja odbioru JWE z cchd_config")
    # Używamy rzeczywistego JWE z spike_cchd_config_live.py
    real_jwe = "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkExMjhDQkMtSFMyNTYifQ.AViZI2vjVcRigrUwL4-RxSnRizMgpWY2dck3-LBJRLLbZOGOcQasBgeX4MKPT_OxtQI7TjMcteaMTHCNytZn_qTmNRKAr5hlCgT0CB5P1yup_HukKPHTguhcJ0kgEeCy9B8NcQwmjxIVCk8rd-r7QK-kHSYnXr7xtYLghRj4VuDjGCFX-sBjiNXBl5d8_pDGtev9azvBKm7mt3KjONWMg7qvstkdQXKTjkQY6en2wxz42_WMNfRastrkYApWODdscmDVXQsaTefiRHgm3n2DiXHdEAL2q4BZ7LTrIK1KZKnnq0RcSfyB8z8goFZTXTzrLxvbvevLM_kGZmk-PgrZbw.rplVPzgIU0x87Q5E2NwpNQ.92l7X0McdE5rafpsGFddMNf85n62Ru5eX610VBZXJQkUKCzrlnoq7PQFsE06Fq_5XFgve1KBwZtljSlPTThk6yOlORDD0NCPJkUn4vC5zUnK9vTdem5YoCo5a89lMYIxnkjlUekwskhU4SZFLG464ZN9_fus4X7DNIIT2jaaLlOtPVcJq01tdCNkmq1VA9ZzWDOauD01LXvBt0r4J5vJV_wnm1RWdyBXdTmb1OuQ9xLavLdAPQHpiPhiRNBpQk4UzAGFNW3-sGHQxE0KeDBl8PiQ0cb6slizoVxR58gxFMu7xa04Th9hB3b6L8ABvd-rqXTD88SRVHOcXWER1XRPPDt9dK1cpyCCWv0sNRvvXQF59alPXNk64VrHPgRpSleplncYivwpPOZP6gkpoV33lWv3TvBEKt1fcPbJONcdioySwUh5jln4HCvLmslti9BJYtcYnUjbJ8yKgihJ8qxF6xa4JkkJX3yViNsXymBzAq-OM9rB6MuHQazUw__qARoxhmb9pjKZ0b7oZ_wx4tSgrcUHUn-ZWzWcMOvLxeMU7AmgdL0OygdLhB54QWd0AcCkDPpqbH9gnbaIRy5Qx01pgw.I5M4SnXqV19CzF9S4sNPxQ"
    print(f"[Python] Real JWE from cchd_config (len={len(real_jwe)}): {real_jwe[:80]}...")

    print("\nKrok 3: Node.js - analiza struktury JWE (bez klucza prywatnego nie odszyfrujemy)")
    parts = real_jwe.split(".")
    print(f"[Python] Header (decoded): {json.loads(base64.urlsafe_b64decode(parts[0] + '==').decode())}")

    print("\nKrok 4: HKDF derive session key (symulacja SDK Incognia)")
    demo_hkdf_derive()

    print("\nKrok 5: AES-GCM encrypt payload (symulacja x-incognia-request-token)")
    demo_aes_gcm_encrypt_decrypt()

    print("\nKrok 6: JWE encrypt/decrypt (format cchd_config)")
    demo_jwe_rsa_oaep_aes_cbc()

    print("\n=== PODSUMOWANIE ARCHITEKTURY ===")
    print("""
curl_cffi (Python)                    Node.js (WebCrypto)
─────────────────                    ───────────────────
✓ TLS ClientHello (JA3/JA4)          ✓ HKDF-SHA256 (RFC 5869)
✓ HTTP/2 frames + settings           ✓ AES-256-GCM (RFC 5116)
✓ Akamai fingerprint                 ✓ RSA-OAEP (RFC 8017)
✓ Custom extensions (delegated       ✓ JWE compact serialization (RFC 7516)
  credential, record size limit,
  cert compression zstd)
✓ Nagłówki HTTP (UA, Sec-Fetch-*)    ✓ Klucze sesyjne, nonce, AAD
✓ Ciało request/response (JSON)      ✓ Zero zależności native (stdlib)

Podział odpowiedzialności:
- Transport / sieć / fingerprint TLS → curl_cffi
- Kryptografia aplikacyjna (SDK)     → Node.js WebCrypto
- Orkiestracja / logika biznesowa    → Python (klucz prywatny, stan sesji)
    """)


if __name__ == "__main__":
    # Sprawdź czy Node.js skrypt istnieje
    if not NODE_SCRIPT.exists():
        print(f"Brak skryptu Node.js: {NODE_SCRIPT}")
        print("Uruchom najpierw generowanie demo_node_crypto.js")
        sys.exit(1)

    try:
        demo_full_flow()
    except Exception as e:
        print(f"\n[BŁĄD] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)