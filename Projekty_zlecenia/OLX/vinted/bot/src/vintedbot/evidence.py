"""Dowody pomiarowe: raport timingów (ms) i screenshot przez Camoufox z telemetrią Waterfall v2.

Screenshot renderuje checkout (rezerwacja, bez payment) albo bramkę płatności
(z payment) przez Camoufox, z wypalonym paskiem telemetrycznym pełnego cyklu (od detekcji do płatności).

Wydajność: screenshot (start Camoufox ~8-15s) NIE może blokować gorącej ścieżki
zakupu. Dlatego `zapisz_dowody_async` wykonuje go w wątku tła (daemon), a wątek
zakupowy wraca natychmiast po zapisie raportu timingów (szybki JSON).
"""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import profile_lock

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
SCREENSHOT_DIR = OUTPUT_DIR / "screens"  # screeny osobno od JSON-ow
_SCREENSHOT_LOCK = threading.Lock()


def wall_ts() -> str:
    """Timestamp ścienny UTC z milisekundami (spójny z poprzednimi analizami)."""
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


def _output_dir(output_dir: Path | None) -> Path:
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    return out


def _screenshot_dir(output_dir: Path | None) -> Path:
    out = (output_dir or SCREENSHOT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    return out


def zapisz_raport_timingow(wynik: dict, prefix: str, output_dir: Path | None = None) -> Path | None:
    """Zapisuje czasy kroków (ms) + statusy do JSON z timestampem ms i telemetrią v2."""
    out = _output_dir(output_dir)
    payload = {
        "trace_id": wynik.get("trace_id") or f"tr_{prefix}_{int(time.time() * 1000)}",
        "ts_wall": wall_ts(),
        "ts_started_ms": int(time.time() * 1000),
        "prefix": prefix,
        "summary_timings": wynik.get("summary_timings") or {},
        "spans": wynik.get("spans") or wynik.get("step_marks") or {},
        "result": wynik,
    }
    path = out / f"{prefix}_{int(time.time() * 1000)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def zrob_screenshot(
    *,
    checkout_id: str | None = None,
    redirect_url: str | None = None,
    prefix: str,
    profile: str | None = None,
    output_dir: Path | None = None,
    step_marks: dict | None = None,
    timings: dict | None = None,
    payment_info: dict | None = None,
) -> Path | None:
    """Screenshot przez Camoufox: bramka (redirect_url) albo checkout (checkout_id).

    Wypala timestamp ms + szczegółowe marki kroków i status płatności na czarnym pasku (dowód wizualny).
    Błędy zwracają None.
    """
    out = _screenshot_dir(output_dir)

    if redirect_url:
        url = redirect_url
        kind = "bramka_platnosci"
    elif checkout_id:
        url = f"https://www.vinted.pl/checkout?purchase_id={checkout_id}"
        kind = "checkout"
    else:
        return None

    shot_path = out / f"{prefix}_{kind}_{int(time.time() * 1000)}.png"

    try:
        from camoufox import Camoufox

        kwargs = dict(headless=True, os="windows", fingerprint_preset=True, humanize=True,
                      webgl_config=WEBGL_CONFIG)
        if profile:
            kwargs.update(persistent_context=True, user_data_dir=profile)
        _lk = profile_lock(profile) if profile else _SCREENSHOT_LOCK
        with _lk:
            with Camoufox(**kwargs) as ctx:
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
                page.screenshot(path=str(shot_path), full_page=False)
    except Exception as exc:
        print(f"[evidence] błąd zrob_screenshot: {exc!r}", flush=True)
        return None

    _wypal_timestamp(shot_path, kind, url, step_marks=step_marks, timings=timings, payment_info=payment_info)
    return shot_path


def zapisz_dowody(wynik, *, prefix, timings=True, screenshot=True,
                  payment=False, profil=None, output_dir=None) -> dict:
    """Zapis raportu timingów (ms) i/lub screena checkoutu/bramki dla wyniku zakupu."""
    if hasattr(wynik, "model_dump"):
        dane = wynik.model_dump()
        redirect = getattr(wynik, "redirect_url", None)
        checkout_id = getattr(wynik, "checkout_id", None)
    else:
        dane = wynik if isinstance(wynik, dict) else {"value": wynik}
        redirect = dane.get("redirect_url")
        checkout_id = dane.get("checkout_id")

    paths: dict = {}
    if timings:
        p = zapisz_raport_timingow(dane, prefix=prefix, output_dir=output_dir)
        if p:
            paths["timing_report"] = str(p)
    if screenshot:
        p = None
        spans_to_pass = dane.get("spans") or dane.get("step_marks")
        if payment and redirect:
            p = zrob_screenshot(redirect_url=redirect, prefix=prefix, profile=profil,
                                output_dir=output_dir, step_marks=spans_to_pass,
                                timings=dane.get("timings"), payment_info=dane)
        elif checkout_id:
            p = zrob_screenshot(checkout_id=checkout_id, prefix=prefix, profile=profil,
                                output_dir=output_dir, step_marks=spans_to_pass,
                                timings=dane.get("timings"), payment_info=dane)
        if p:
            paths["screenshot"] = str(p)
    return paths


def zapisz_dowody_async(wynik, *, prefix, timings=True, screenshot=True,
                        payment=False, profil=None, output_dir=None):
    """Jak `zapisz_dowody`, ale screenshot wykonuje się w wątku tła (daemon)."""
    if hasattr(wynik, "model_dump"):
        dane = wynik.model_dump()
        redirect = getattr(wynik, "redirect_url", None)
        checkout_id = getattr(wynik, "checkout_id", None)
    else:
        dane = wynik if isinstance(wynik, dict) else {"value": wynik}
        redirect = dane.get("redirect_url")
        checkout_id = dane.get("checkout_id")

    paths: dict = {}
    if timings:
        p = zapisz_raport_timingow(dane, prefix=prefix, output_dir=output_dir)
        if p:
            paths["timing_report"] = str(p)

    if screenshot and ((payment and redirect) or checkout_id):
        spans_to_pass = dane.get("spans") or dane.get("step_marks")
        def _shot():
            if payment and redirect:
                zrob_screenshot(redirect_url=redirect, prefix=prefix, profile=profil,
                                output_dir=output_dir, step_marks=spans_to_pass,
                                timings=dane.get("timings"), payment_info=dane)
            elif checkout_id:
                zrob_screenshot(checkout_id=checkout_id, prefix=prefix, profile=profil,
                                output_dir=output_dir, step_marks=spans_to_pass,
                                timings=dane.get("timings"), payment_info=dane)

        threading.Thread(target=_shot, daemon=True, name=f"shot-{prefix}").start()
    return paths


def _wypal_timestamp(shot_path: Path, kind: str, url: str, step_marks: dict | None = None,
                     timings: dict | None = None, payment_info: dict | None = None) -> None:
    """Wypala czytelny pasek Waterfall Telemetry v2 z podziałem na fazy zakupu."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        with Image.open(shot_path) as _orig:
            img = _orig.convert("RGB")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            font_bold = ImageFont.truetype("arialbd.ttf", 17)
        except Exception:
            font = ImageFont.load_default()
            font_bold = font

        lines = [f"DOWÓD VINTED BOT | {kind.upper()} | {wall_ts()} | {url}"]

        # Informacje o płatności
        if payment_info:
            pay_parts = []
            st_pay = payment_info.get("status_payment")
            if st_pay is not None:
                pay_parts.append(f"HTTP: {st_pay}")
            p_stat = payment_info.get("payment_status")
            if p_stat:
                pay_parts.append(f"Status: {p_stat}")
            act = payment_info.get("action_type")
            if act:
                pay_parts.append(f"Action: {act}")
            err = payment_info.get("error_code")
            if err:
                pay_parts.append(f"Kod Błędu: {err}")
            corr = payment_info.get("correlation_id")
            if corr:
                pay_parts.append(f"CorrID: {corr}")
            if pay_parts:
                lines.append("--- WYNIK PŁATNOŚCI: " + " | ".join(pay_parts) + " ---")

        # Fazy Waterfall (Spans)
        if step_marks:
            lines.append("--- FAZY WATERFALL (TELEMETRIA PEŁNEGO CYKLU) ---")
            phase_labels = {
                "1_detection_poll": "[1] DETEKCJA",
                "1_detection": "[1] DETEKCJA",
                "transaction": "[2] TRANSAKCJA",
                "2_transaction": "[2] TRANSAKCJA",
                "build+pickup_point": "[3] KOSZYK+PKP",
                "3_build_and_pickup": "[3] KOSZYK+PKP",
                "put_pickup_details": "[4] PUT ADRES",
                "4_put_pickup_details": "[4] PUT ADRES",
                "payment": "[5] PŁATNOŚĆ",
                "5_payment": "[5] PŁATNOŚĆ",
            }
            for name, m in step_marks.items():
                label = phase_labels.get(name, f"[-] {name.upper()}")
                dur = m.get("dur_ms", 0)
                st_iso = m.get("start_iso", "")
                en_iso = m.get("end_iso", "")
                span_type = m.get("type", "NET")
                lines.append(f" {label:<15}: {dur:>5} ms  [{span_type}]  ({st_iso} -> {en_iso})")

        # Podsumowanie czasowe
        summary = (payment_info or {}).get("summary_timings") or {}
        if summary:
            tot = summary.get("total_full_cycle_ms", 0)
            det = summary.get("detection_ms", 0)
            chk = summary.get("checkout_to_payment_ms", 0)
            net_pct = summary.get("net_ratio_pct", 0)
            lines.append(f"--- CZAS PEŁNY: {tot} ms (Detekcja: {det}ms + Zakup: {chk}ms) | Sieć Vinted: {net_pct}% | CPU Bota: {round(100-net_pct, 1)}% ---")
        elif timings:
            total = sum(v for k, v in timings.items() if isinstance(v, (int, float)) and k != "SUMA")
            lines.append(f"--- CZAS ZAKUPU: {total} ms ({total/1000:.2f}s) ---")

        # Zawijaj linie do szerokości obrazu
        max_w = img.width - 24
        wrapped: list[str] = []
        for line in lines:
            cur = line
            while cur:
                if draw.textlength(cur, font=font) <= max_w:
                    wrapped.append(cur)
                    break
                cut = len(cur)
                while cut > 0 and draw.textlength(cur[:cut], font=font) > max_w:
                    cut -= 1
                sep = max(cur.rfind(" | ", 0, cut), cur.rfind(" ", 0, cut))
                if sep <= 0:
                    sep = cut
                wrapped.append(cur[:sep])
                cur = cur[sep:].lstrip(" |")

        line_h = font.size + 4 if hasattr(font, "size") else 20
        bar_h = 16 + len(wrapped) * line_h
        bar_h = min(bar_h, img.height - 8)
        draw.rectangle([0, img.height - bar_h, img.width, img.height], fill=(0, 0, 0))
        for i, ln in enumerate(wrapped):
            y = img.height - bar_h + 8 + i * line_h
            if y + line_h > img.height:
                break
            # Nagłówki w kolorze białym/zielonym, dane w żółtym
            f_color = (100, 255, 100) if ln.startswith("---") or ln.startswith("DOWÓD") else (255, 255, 50)
            draw.text((12, y), ln, fill=f_color, font=font)
        img.save(shot_path)
    except Exception as exc:
        print(f"[evidence] błąd _wypal_timestamp: {exc!r}", flush=True)
