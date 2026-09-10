# coding: utf-8
"""Hookuje crypto.subtle.encrypt/importKey w kontekście Vinted, by przechwycić
plaintext sygnałów Incognii ZANIM zostanie zaszyfrowany do JWE."""
import time, json, sys, traceback
from pathlib import Path

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"
OUT = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_crypto_hook_out.json")

captured = {
    "encrypt_calls": [],   # list[{algo, plaintext_b64, plaintext_hex, plaintext_len, key_b64}]
    "import_key_calls": [], # list[{format, algo, key_b64, usages, extractable}]
    "error": None,
}

INIT_SCRIPT = """
(function () {
  if (window.__cryptoHookInstalled) return;
  window.__cryptoHookInstalled = true;
  window.__captured = { encrypt_calls: [], import_key_calls: [], rsa_jwk: null };

  const toB64 = (buf) => {
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  };
  const toHex = (buf) => {
    const bytes = new Uint8Array(buf);
    let s = '';
    for (let i = 0; i < bytes.length; i++) s += bytes[i].toString(16).padStart(2, '0');
    return s;
  };
  const bufToArray = (x) => {
    if (x instanceof ArrayBuffer) return new Uint8Array(x.slice(0));
    if (ArrayBuffer.isView(x)) return new Uint8Array(x.buffer, x.byteOffset, x.byteLength);
    return null;
  };

  const origEncrypt = crypto.subtle.encrypt.bind(crypto.subtle);
  crypto.subtle.encrypt = async function (algorithm, key, data) {
    const arr = bufToArray(data);
    const rec = {
      algo: JSON.stringify(algorithm),
      plaintext_len: arr ? arr.length : -1,
      plaintext_b64: arr ? toB64(arr) : null,
      plaintext_hex: arr ? toHex(arr) : null,
      key_type: key && key.type,
      key_alg: key && key.algorithm && key.algorithm.name,
    };
    try {
      if (key && key.extractable) {
        const raw = await crypto.subtle.exportKey('raw', key);
        rec.key_b64 = toB64(raw);
      }
    } catch (e) {}
    if (window.__captured) window.__captured.encrypt_calls.push(rec);
    return origEncrypt(algorithm, key, data);
  };

  const origImportKey = crypto.subtle.importKey.bind(crypto.subtle);
  crypto.subtle.importKey = async function (format, keyData, algorithm, extractable, usages) {
    const arr = bufToArray(keyData);
    const rec = {
      format: format,
      algo: JSON.stringify(algorithm),
      key_b64: arr ? toB64(arr) : null,
      key_len: arr ? arr.length : -1,
      usages: Array.from(usages | []),
      extractable: extractable,
    };
    if (window.__captured) window.__captured.import_key_calls.push(rec);
    return origImportKey(format, keyData, algorithm, extractable, usages);
  };

  // Eksport kluczy RSA publicznych (do identyfikacji kid)
  const origExportKey = crypto.subtle.exportKey.bind(crypto.subtle);
  crypto.subtle.exportKey = async function (format, key) {
    const out = await origExportKey(format, key);
    if (window.__captured && format === 'jwk' && key && key.algorithm && key.algorithm.name === 'RSA-OAEP') {
      window.__captured.rsa_jwk = out;
    }
    return out;
  };
})();
"""

def log(msg):
    print(msg, flush=True)

log("t0 import")
from camoufox import Camoufox

try:
    with Camoufox(persistent_context=True, headless=True,
                  user_data_dir=PROFILE, os="windows") as ctx:
        page = ctx.new_page()
        # wstrzyknij hook PRZED nawigacją
        page.add_init_script(INIT_SCRIPT)

        log("goto item")
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)

        # klik Kup teraz
        buy = None
        for sel in ['button[data-testid="item-buy-button"]',
                    'button:has-text("Kup teraz")',
                    'button:has-text("Kup i zapłać")']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    buy = el
                    break
            except Exception:
                continue

        if buy:
            log("click buy")
            buy.click(timeout=10000)
            time.sleep(6)
        else:
            log("no buy button, waiting for any sdk call")
            time.sleep(6)

        data = page.evaluate("() => window.__captured || { encrypt_calls: [], import_key_calls: [], rsa_jwk: null }")
        captured["encrypt_calls"] = data.get("encrypt_calls", [])
        captured["import_key_calls"] = data.get("import_key_calls", [])
        captured["rsa_jwk"] = data.get("rsa_jwk")
        log("encrypt_calls=%d import_key_calls=%d" % (len(captured["encrypt_calls"]), len(captured["import_key_calls"])))
except Exception as e:
    captured["error"] = repr(e)
    log("FAIL: " + repr(e))
    log(traceback.format_exc())

OUT.write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
log("SAVED -> " + str(OUT))