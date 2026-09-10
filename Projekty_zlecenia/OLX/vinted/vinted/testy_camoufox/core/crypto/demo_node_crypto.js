/**
 * demo_node_crypto.js — operacje kryptograficzne WebCrypto API (Node.js stdlib).
 *
 * Używa globalThis.crypto.subtle (dostępne w Node.js 16+ bez flag).
 * Zero zależności zewnętrznych — czysty standard WebCrypto.
 *
 * Operacje:
 * - hkdf: HKDF-SHA256 derive key (RFC 5869) — Incognia session key derivation
 * - aes_gcm_encrypt/decrypt: AES-256-GCM (RFC 5116) — Incognia payload encryption
 * - jwe_encrypt/decrypt: JWE compact (RFC 7516) z RSA-OAEP + A128CBC-HS256 — cchd_config format
 *
 * Wejście: JSON na stdin { operation, payload }
 * Wyjście: JSON na stdout { derivedKey / ciphertext / tag / plaintext / jwe }
 */

// ===== NARZĘDZIA =====

function b64ToBuf(b64) {
    return Buffer.from(b64, 'base64');
}

function bufToB64(buf) {
    return Buffer.from(buf).toString('base64');
}

function bufToB64Url(buf) {
    return Buffer.from(buf).toString('base64url');
}

function b64UrlToBuf(b64url) {
    return Buffer.from(b64url, 'base64url');
}

// Import klucza RSA z PEM (PKCS#8 private / SPKI public)
async function importRsaKey(pem, isPrivate, usage) {
    const pemHeader = isPrivate ? '-----BEGIN PRIVATE KEY-----' : '-----BEGIN PUBLIC KEY-----';
    const pemFooter = isPrivate ? '-----END PRIVATE KEY-----' : '-----END PUBLIC KEY-----';
    const b64 = pem.replace(pemHeader, '').replace(pemFooter, '').replace(/\s/g, '');
    const der = Buffer.from(b64, 'base64');

    const format = isPrivate ? 'pkcs8' : 'spki'; // Private = PKCS#8, Public = SPKI (SubjectPublicKeyInfo)
    const keyUsages = isPrivate ? ['decrypt', 'unwrapKey'] : ['encrypt', 'wrapKey'];

    return await crypto.subtle.importKey(
        format,
        der,
        {
            name: 'RSA-OAEP',
            hash: 'SHA-256',
        },
        false,
        keyUsages
    );
}

// ===== HKDF (RFC 5869) =====

async function hkdfDerive({ hash, salt, ikm, info, length }) {
    // WebCrypto HKDF: import key -> deriveBits
    const baseKey = await crypto.subtle.importKey(
        'raw',
        b64ToBuf(ikm),
        { name: 'HKDF' },
        false,
        ['deriveBits']
    );

    const derivedBits = await crypto.subtle.deriveBits(
        {
            name: 'HKDF',
            hash: hash, // 'SHA-256'
            salt: b64ToBuf(salt),
            info: b64ToBuf(info),
        },
        baseKey,
        length * 8 // bits
    );

    return { derivedKey: bufToB64(new Uint8Array(derivedBits)) };
}

// ===== AES-GCM (RFC 5116) =====

async function aesGcmEncrypt({ key, nonce, aad, plaintext }) {
    const cryptoKey = await crypto.subtle.importKey(
        'raw',
        b64ToBuf(key),
        { name: 'AES-GCM' },
        false,
        ['encrypt']
    );

    // WebCrypto AES-GCM zwraca ciphertext + tag złączone (tag na końcu, 16 bajtów)
    const encrypted = await crypto.subtle.encrypt(
        {
            name: 'AES-GCM',
            iv: b64ToBuf(nonce),
            additionalData: b64ToBuf(aad),
            tagLength: 128, // 128-bit tag = 16 bytes
        },
        cryptoKey,
        b64ToBuf(plaintext)
    );

    const encryptedBuf = new Uint8Array(encrypted);
    const tagLength = 16;
    const ciphertext = encryptedBuf.slice(0, -tagLength);
    const tag = encryptedBuf.slice(-tagLength);

    return {
        ciphertext: bufToB64(ciphertext),
        tag: bufToB64(tag),
    };
}

async function aesGcmDecrypt({ key, nonce, aad, ciphertext, tag }) {
    const cryptoKey = await crypto.subtle.importKey(
        'raw',
        b64ToBuf(key),
        { name: 'AES-GCM' },
        false,
        ['decrypt']
    );

    // WebCrypto oczekuje ciphertext || tag
    const combined = Buffer.concat([b64ToBuf(ciphertext), b64ToBuf(tag)]);

    const decrypted = await crypto.subtle.decrypt(
        {
            name: 'AES-GCM',
            iv: b64ToBuf(nonce),
            additionalData: b64ToBuf(aad),
            tagLength: 128,
        },
        cryptoKey,
        combined
    );

    return { plaintext: bufToB64(new Uint8Array(decrypted)) };
}

// ===== JWE (RFC 7516) — RSA-OAEP + A128CBC-HS256 =====

// A128CBC-HS256 = AES-128-CBC + HMAC-SHA-256 (split key: first 16B enc, last 16B mac)
async function jweEncrypt({ publicKeyPem, plaintext, alg, enc }) {
    // 1. Generuj losowy CEK (Content Encryption Key) — 32 bajty dla A128CBC-HS256 (16 enc + 16 mac)
    const cek = crypto.getRandomValues(new Uint8Array(32));

    // 2. Zaszyfruj CEK kluczem publicznym RSA-OAEP (SHA-256)
    const publicKey = await importRsaKey(publicKeyPem, false, ['encrypt']);
    const encryptedKey = await crypto.subtle.encrypt(
        { name: 'RSA-OAEP' },
        publicKey,
        cek
    );

    // 3. Podziel CEK na klucz szyfrowania (16B) i klucz MAC (16B)
    const encKey = cek.slice(0, 16);
    const macKey = cek.slice(16, 32);

    // 4. JWE Protected Header
    const protectedHeader = {
        alg: alg, // "RSA-OAEP"
        enc: enc, // "A128CBC-HS256"
    };
    const protectedB64 = bufToB64Url(Buffer.from(JSON.stringify(protectedHeader)));

    // 5. Generuj losowy IV (16 bajtów dla AES-CBC)
    const iv = crypto.getRandomValues(new Uint8Array(16));

    // 6. Szyfruj plaintext AES-128-CBC z PKCS#7 padding
    const encCryptoKey = await crypto.subtle.importKey(
        'raw',
        encKey,
        { name: 'AES-CBC' },
        false,
        ['encrypt']
    );

    // PKCS#7 padding
    const padLen = 16 - (plaintext.length % 16);
    const padded = Buffer.concat([
        Buffer.from(plaintext),
        Buffer.alloc(padLen, padLen),
    ]);

    const ciphertext = await crypto.subtle.encrypt(
        { name: 'AES-CBC', iv: iv },
        encCryptoKey,
        padded
    );

    // 7. Oblicz HMAC-SHA256 (AAD || IV || ciphertext || length)
    // AAD = protected header (base64url)
    const aad = Buffer.from(protectedB64, 'ascii');
    const aadLenBits = Buffer.alloc(8);
    aadLenBits.writeBigUInt64BE(BigInt(aad.length * 8));
    const macData = Buffer.concat([aad, iv, Buffer.from(ciphertext), aadLenBits]);

    const macKeyCrypto = await crypto.subtle.importKey(
        'raw',
        macKey,
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
    );
    const tagFull = await crypto.subtle.sign('HMAC', macKeyCrypto, macData);
    const tag = new Uint8Array(tagFull).slice(0, 16); // first 128 bits (16 bytes)

    // 8. Złóż JWE Compact Serialization: protected.encrypted_key.iv.ciphertext.tag
    const encryptedKeyB64 = bufToB64Url(Buffer.from(encryptedKey));
    const ivB64 = bufToB64Url(Buffer.from(iv));
    const ciphertextB64 = bufToB64Url(Buffer.from(ciphertext));
    const tagB64 = bufToB64Url(Buffer.from(tag));

    const jwe = `${protectedB64}.${encryptedKeyB64}.${ivB64}.${ciphertextB64}.${tagB64}`;

    return { jwe };
}

async function jweDecrypt({ privateKeyPem, jwe }) {
    const parts = jwe.split('.');
    if (parts.length !== 5) {
        throw new Error('Invalid JWE: expected 5 parts');
    }

    const [protectedB64, encryptedKeyB64, ivB64, ciphertextB64, tagB64] = parts;

    // 1. Zdekoduj protected header
    const protectedHeader = JSON.parse(Buffer.from(protectedB64, 'base64url').toString());
    const { alg, enc } = protectedHeader;

    if (alg !== 'RSA-OAEP' || enc !== 'A128CBC-HS256') {
        throw new Error(`Unsupported JWE alg/enc: ${alg}/${enc}`);
    }

    // 2. Odszyfruj CEK kluczem prywatnym
    const privateKey = await importRsaKey(privateKeyPem, true, ['decrypt']);
    const encryptedKey = b64UrlToBuf(encryptedKeyB64);
    const cek = await crypto.subtle.decrypt(
        { name: 'RSA-OAEP' },
        privateKey,
        encryptedKey
    );
    const cekBytes = new Uint8Array(cek);
    console.error('[JWE decrypt] CEK decrypted len:', cekBytes.length);
    console.error('[JWE decrypt] CEK (hex):', Buffer.from(cekBytes).toString('hex'));
    console.error('[JWE decrypt] encKey (hex):', Buffer.from(cekBytes.slice(0, 16)).toString('hex'));
    console.error('[JWE decrypt] macKey (hex):', Buffer.from(cekBytes.slice(16, 32)).toString('hex'));
    if (cekBytes.length !== 32) {
        throw new Error(`Invalid CEK length: ${cekBytes.length}`);
    }

    const encKey = cekBytes.slice(0, 16);
    const macKey = cekBytes.slice(16, 32);

    // 3. Weryfikuj HMAC tag
    const iv = b64UrlToBuf(ivB64);
    const ciphertext = b64UrlToBuf(ciphertextB64);
    const tag = b64UrlToBuf(tagB64);

    const aad = Buffer.from(protectedB64, 'ascii');
    const aadLenBits = Buffer.alloc(8);
    aadLenBits.writeBigUInt64BE(BigInt(aad.length * 8));
    const macData = Buffer.concat([aad, iv, ciphertext, aadLenBits]);

    // HMAC-SHA256 daje 32 bajty, JWE A128CBC-HS256 używa pierwszych 16 bajtów (128 bitów)
    // crypto.subtle.verify porównuje CAŁY podpis (32B), więc nie zadziała z 16B tagiem.
    // Rozwiązanie: sign + ręczne porównanie pierwszych 16 bajtów (zgodne z RFC 7516).
    const macKeyCrypto = await crypto.subtle.importKey(
        'raw',
        macKey,
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
    );
    const tagFull = await crypto.subtle.sign('HMAC', macKeyCrypto, macData);
    const computedTag = new Uint8Array(tagFull).slice(0, 16);
    const valid = Buffer.from(computedTag).equals(Buffer.from(tag));

    if (!valid) {
        throw new Error('JWE MAC verification failed');
    }

    // 4. Odszyfruj AES-128-CBC
    const decCryptoKey = await crypto.subtle.importKey(
        'raw',
        encKey,
        { name: 'AES-CBC' },
        false,
        ['decrypt']
    );

    const decryptedPadded = await crypto.subtle.decrypt(
        { name: 'AES-CBC', iv: iv },
        decCryptoKey,
        ciphertext
    );

    // 5. Usuń PKCS#7 padding
    const decryptedBuf = Buffer.from(decryptedPadded);
    const padLen = decryptedBuf[decryptedBuf.length - 1];
    if (padLen > 16 || padLen === 0) {
        throw new Error('Invalid PKCS#7 padding');
    }
    const plaintext = decryptedBuf.slice(0, -padLen);

    return { plaintext: bufToB64(plaintext) };
}

// ===== MAIN =====

async function main() {
    const input = JSON.parse(await new Promise((resolve) => {
        let data = '';
        process.stdin.on('data', chunk => data += chunk);
        process.stdin.on('end', () => resolve(data));
    }));

    const { operation, payload } = input;

    try {
        let result;
        switch (operation) {
            case 'hkdf':
                result = await hkdfDerive(payload);
                break;
            case 'aes_gcm_encrypt':
                result = await aesGcmEncrypt(payload);
                break;
            case 'aes_gcm_decrypt':
                result = await aesGcmDecrypt(payload);
                break;
            case 'jwe_encrypt':
                result = await jweEncrypt(payload);
                break;
            case 'jwe_decrypt':
                result = await jweDecrypt(payload);
                break;
            default:
                throw new Error(`Unknown operation: ${operation}`);
        }
        process.stdout.write(JSON.stringify(result));
    } catch (err) {
        process.stderr.write(err.message);
        process.exit(1);
    }
}

main();