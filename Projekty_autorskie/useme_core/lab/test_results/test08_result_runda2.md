# TEST 08 – JSON API (Runda 2)

Data: 2026-08-06 15:32:00 (Europe/Warsaw)

## Cel testu
Sprawdzić, czy Useme zwraca JSON z nagłówkiem `Accept: application/json` zamiast HTML.

## Testowane URL-e
- **Kategoria (lista ofert)**: `https://useme.com/pl/jobs/category/programowanie-i-it,35/`
- **Detal oferty**: `https://useme.com/pl/jobs/stworzenie-narzedzia-do-drukowania-w-pdf-zestawow-z-platnika,142281/`

## Warianty nagłówków
1. `Accept: application/json`
2. `Accept: application/json, text/plain, */*`
3. `X-Requested-With: XMLHttpRequest`
4. `Accept: application/json` + `X-Requested-With: XMLHttpRequest` (razem)

## Wyniki szczegółowe

### Test 1: Kategoria (lista ofert) | Accept: application/json

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/category/programowanie-i-it,35/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-m0kUzs9OS3TRrChQPibXPn&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 2: Kategoria (lista ofert) | Accept: application/json, text/plain, */*

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/category/programowanie-i-it,35/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-SQamvtrrwbr13JWaTiaj63&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 3: Kategoria (lista ofert) | X-Requested-With: XMLHttpRequest

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/category/programowanie-i-it,35/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-6AYOuJ9aCUQjo3yUFoyoIw&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 4: Kategoria (lista ofert) | Accept: application/json + X-Requested-With: XMLHttpRequest

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/category/programowanie-i-it,35/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-Eo6zUsSGO1FQZCdgHAz1BK&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 5: Detal oferty | Accept: application/json

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/stworzenie-narzedzia-do-drukowania-w-pdf-zestawow-z-platnika,142281/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-tVo3YwNS08v8f8ifq2RU3x&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 6: Detal oferty | Accept: application/json, text/plain, */*

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/stworzenie-narzedzia-do-drukowania-w-pdf-zestawow-z-platnika,142281/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-xvAnRaAXgMm5XtiSjdmqUO&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 7: Detal oferty | X-Requested-With: XMLHttpRequest

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/stworzenie-narzedzia-do-drukowania-w-pdf-zestawow-z-platnika,142281/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-1G352l4RBINB6iLWqmAarI&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

### Test 8: Detal oferty | Accept: application/json + X-Requested-With: XMLHttpRequest

| Parametr | Wartość |
|----------|---------|
| URL | `https://useme.com/pl/jobs/stworzenie-narzedzia-do-drukowania-w-pdf-zestawow-z-platnika,142281/` |
| Status HTTP | `403` |
| Content-Type | `text/html; charset=UTF-8` |
| Czy JSON? | False |
| Czy HTML? | True |
| Zawiera article.job? | False |
| Zawiera treść oferty? | True |

**Body preview (500 znaków):**
```
<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="content-security-policy" content="default-src &#39;none&#39;; script-src &#39;nonce-tFbrRXq38sXoq0a2WNi2yq&#39; &#39;unsafe-eval&#39; https://challenges.cloudflare.com; script-s
```

## WNIOSEK

❌ **Useme NIE zwraca JSON** dla żadnego z testowanych wariantów nagłówków. Serwer zawsze odpowiada HTML.

**Rekomendacja**: Pozostać przy HTML+BeautifulSoup – JSON API nie jest dostępne.

---

*Test wykonany automatycznie przez skrypt test08_json.py*