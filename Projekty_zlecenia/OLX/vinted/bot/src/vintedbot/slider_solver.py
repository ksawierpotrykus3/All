"""Auto-solver DataDome slider challenge (captcha-delivery.com).

Wykrywa iframe captcha i przeciąga suwak (.slider) do celu (.sliderTarget)
ludzkim ruchem myszy (krzywa + jitter + zmienna prędkość).
"""
from __future__ import annotations

import random
import time
from pathlib import Path


def _znajdz_captcha_frame(page, proby: int = 40, czekaj_ms: int = 500):
    """Zwraca frame captcha-delivery lub None."""
    for _ in range(proby):
        for fr in page.frames:
            if "captcha-delivery.com" in (fr.url or ""):
                return fr
        page.wait_for_timeout(czekaj_ms)
    return None


def _pozycje_slidera(frame) -> dict | None:
    """Pozycje suwaka i celu. Cel = prawa krawędź toru (suwak dojedzie do końca)."""
    try:
        return frame.evaluate(
            """() => {
                const s = document.querySelector('.slider');
                const c = document.querySelector('.sliderContainer');
                if (!s || !c) return null;
                const rs = s.getBoundingClientRect();
                const rc = c.getBoundingClientRect();
                return {
                    slider: {x: rs.x + rs.width/2, y: rs.y + rs.height/2},
                    // Cel: suwak dojeżdża do prawej krawędzi toru.
                    cel_x: rc.x + rc.width - rs.width / 2,
                    cel_y: rs.y + rs.height/2,
                    szerokosc_suwaka: rs.width,
                    tor: {x: rc.x, w: rc.width},
                };
            }"""
        )
    except Exception:
        return None


def _ludzki_ruch(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    """Prosty ruch do celu: stałe Y (tor poziomy), minimalny jitter, lekkie spowolnienie."""
    dystans = x1 - x0
    kroki = max(15, int(dystans / 8))
    punkty = []
    for i in range(kroki + 1):
        t = i / kroki
        ease = 1 - (1 - t) ** 2  # ease-out
        x = x0 + dystans * ease
        y = y0 + random.uniform(-0.5, 0.5)  # minimalny jitter, bez kółek
        punkty.append((x, y))
    return punkty


def rozwiaz_slider(page, timeout_s: int = 45, debug_dir=None, proby: int = 3) -> bool:
    """Wykrywa i rozwiązuje slider DataDome. True = sukces (iframe zniknął)."""
    frame = _znajdz_captcha_frame(page)
    if not frame:
        return False

    # Element iframe na stronie nadrzędnej — do przeliczenia współrzędnych fallbacku
    # page.mouse. W headless `bounding_box()` bywa None (iframe ukryty/zerowy lub
    # zagnieżdżony) — to NIE może przerywać głównej ścieżki `drag_to`, która operuje
    # bezpośrednio na `frame.locator` i nie potrzebuje boxa.
    iframe_el = None
    for el in page.query_selector_all("iframe"):
        try:
            if "captcha-delivery.com" in (el.get_attribute("src") or ""):
                iframe_el = el
                break
        except Exception:
            continue
    box = None
    if iframe_el is None:
        print("[slider] nie znaleziono <iframe> na top-level (możliwy zagnieżdżony iframe)", flush=True)
    else:
        try:
            box = iframe_el.bounding_box()
        except Exception:
            box = None
        if not box:
            print("[slider] bounding_box iframe = None (headless/ukryty) — fallback mouse wyłączony", flush=True)

    for proba in range(proby):
        poz = _pozycje_slidera(frame)
        if not poz:
            return False

        # Celny drag przez locator (niezawodne eventy pointer w iframe). Działa
        # niezależnie od boxa — operuje na `frame.locator`, więc nie wymaga
        # przeliczania współrzędnych przez bounding_box (kluczowe w headless).
        target_x = max(int(poz["tor"]["w"] - poz["szerokosc_suwaka"] / 2), 260)
        if box is not None:
            sx = box["x"] + poz["slider"]["x"]
            sy = box["y"] + poz["slider"]["y"]
            tx = box["x"] + poz["cel_x"]
            ty = box["y"] + poz["cel_y"]
            print(f"[slider] proba={proba} slider=({sx:.0f},{sy:.0f}) cel=({tx:.0f},{ty:.0f}) box=({box['x']:.0f},{box['y']:.0f})", flush=True)
        else:
            sx = sy = tx = ty = None
            print(f"[slider] proba={proba} (box=None — główna ścieżka drag_to)", flush=True)

        if debug_dir:
            try:
                page.screenshot(path=str(Path(debug_dir) / f"slider_przed_{proba}.png"))
            except Exception:
                pass

        try:
            slider = frame.locator(".slider")
            tor = frame.locator(".sliderContainer")
            # Przeciągnij suwak na prawy koniec toru (używamy faktycznej szer. toru).
            slider.drag_to(tor, target_position={"x": target_x, "y": 20}, timeout=8000)
        except Exception as e:
            print(f"[slider] drag_to err: {e}", flush=True)
            # Fallback: surowe mouse — tylko gdy znamy współrzędne absolutne (box).
            if box is not None:
                page.mouse.move(sx, sy)
                time.sleep(random.uniform(0.2, 0.4))
                page.mouse.down()
                time.sleep(random.uniform(0.1, 0.2))
                page.mouse.move(tx, ty, steps=25)
                time.sleep(random.uniform(0.2, 0.4))
                page.mouse.up()

        # Sprawdź czy slider się przesunął.
        try:
            po = frame.evaluate(
                "() => { const s=document.querySelector('.slider'); if(!s) return null;"
                " const r=s.getBoundingClientRect(); return {x: r.x, transform: s.style.transform || null}; }"
            )
            print(f"[slider] po drag: {po}", flush=True)
        except Exception as e:
            print(f"[slider] odczyt po: {e}", flush=True)

        if debug_dir:
            try:
                page.screenshot(path=str(Path(debug_dir) / f"slider_po_{proba}.png"))
            except Exception:
                pass

        # Czekaj aż iframe zniknie (sukces) albo slider się zresetuje.
        t0 = time.monotonic()
        while time.monotonic() - t0 < 8:
            nadal = any("captcha-delivery.com" in (fr.url or "") for fr in page.frames)
            if not nadal:
                return True
            page.wait_for_timeout(500)
        # Kolejna próba (slider mógł się zresetować po nieudanym dragu).

    return False
