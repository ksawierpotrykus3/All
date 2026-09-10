from mvp.backend.license_signing import generate_keypair, sign_payload, verify_payload


def test_sign_and_verify_roundtrip():
    priv, pub = generate_keypair()
    payload = {"valid": True, "license_key": "LZ-X", "hwid": "h"}
    sig = sign_payload(payload, priv)
    assert verify_payload(payload, sig, pub) is True


def test_verify_rejects_tampered_payload():
    priv, pub = generate_keypair()
    sig = sign_payload({"valid": True}, priv)
    assert verify_payload({"valid": False}, sig, pub) is False
