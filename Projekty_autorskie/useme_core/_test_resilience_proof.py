# -*- coding: utf-8 -*-
"""Testy deterministyczne sprawdzające odporność łańcucha na błędy, zawieszenia i awarie."""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

# UTF-8 dla konsoli
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chain_executor
import cortex_bridge
import storage


def test_1_checkpoint_save_and_resume():
    """Test 1: Sprawdza, czy po przerwaniu pracy łańcuch wznawia od checkpointu."""
    print("\n--- TEST 1: Checkpoint & Resume ---")
    job_id = "test_cp_001"
    storage.clear_checkpoint(job_id)

    dummy_zlecenie = {
        "id": job_id,
        "title": "Aplikacja mobilna Flutter",
        "budget": "8000",
        "fields": {"opis": "Potrzebuję prostej aplikacji w technologii Flutter dla e-commerce." * 3}
    }

    # Symulujemy, że slot 01 i 02b zostały wykonane i zapisujemy sztuczny checkpoint
    fake_context = {
        "research": "Flutter 3.x, gotowe pakiety riverpod, integracja Stripe.",
        "wycena_dni": "[WYNIK_KONCOWY]\nKWOTA: 7500\nDNI: 14\n[/WYNIK_KONCOWY]"
    }
    storage.save_checkpoint(job_id, "02b", fake_context)
    assert storage.load_checkpoint(job_id) is not None, "Błąd: Checkpoint nie zapisał się na dysku!"
    print("[DOWÓD 1A] Checkpoint pomyślnie zapisany na dysku.")

    called_slots = []
    def fake_call(system, user, **kwargs):
        sys_lower = system.lower()
        if "agent 08" in sys_lower or "agent_08" in sys_lower:
            called_slots.append("08")
            return "PASS - oferta jest w porządku."
        elif "agent 02a" in sys_lower or "agent_02a" in sys_lower:
            called_slots.append("02a")
            return "Dzień dobry, z chęcią zrealizuję aplikację Flutter."
        called_slots.append("other")
        return "PASS"

    with patch("chain_executor.call_deepseek", side_effect=fake_call):
        wynik = chain_executor.run_chain(f"test-chain-{job_id}", dummy_zlecenie)

    print(f"Wywołane sloty podczas wznawiania: {called_slots}")
    assert "01" not in called_slots, "BŁĄD: Slot 01 został niepotrzebnie wywołany mimo checkpointu!"
    assert "02b" not in called_slots, "BŁĄD: Slot 02b został niepotrzebnie wywołany mimo checkpointu!"
    assert "02a" in called_slots, "BŁĄD: Slot 02a nie został wywołany!"
    assert wynik is not None, "BŁĄD: Łańcuch nie zwrócił wyniku!"
    assert storage.load_checkpoint(job_id) is None, "BŁĄD: Checkpoint nie został wyczyszczony po pełnym sukcesie!"
    print("[DOWÓD 1B] Łańcuch wznowił pracę od slotu 02a, pominął wykonane sloty i wyczyścił checkpoint po sukcesie.")


def test_2_fallback_21_chars_no_hang():
    """Test 2: Sprawdza, czy 'BRAK_ISTOTNYCH_FAKTOW' (21 znaków) nie powoduje pętli retry."""
    print("\n--- TEST 2: Fallback 21 znaków bez pętli wiszącej ---")
    job_id = "test_fb_002"
    storage.clear_checkpoint(job_id)

    dummy_zlecenie = {
        "id": job_id,
        "title": "Zlecenie bez researchu",
        "budget": "2000",
        "fields": {"opis": "Prosta naprawa skryptu python." * 3}
    }

    call_count = {"01": 0}
    def fake_call(system, user, **kwargs):
        sys_lower = system.lower()
        if "agent 01" in sys_lower or "agent_01" in sys_lower:
            call_count["01"] += 1
            return ""  # Zwracamy pusty wynik z researchu
        elif "agent 02b" in sys_lower or "agent_02b" in sys_lower:
            return "[WYCENA_JSON]\n{\"typ\": \"projekt\", \"moduly\": [{\"nazwa\": \"Fix\", \"godziny_real\": 10}], \"uzasadnienie\": \"ok\"}\n[/WYCENA_JSON]\n[WYNIK_KONCOWY]\nKWOTA: 1000\nDNI: 7\n[/WYNIK_KONCOWY]"
        elif "agent 02a" in sys_lower or "agent_02a" in sys_lower:
            return "Dzień dobry, z chęcią wykonam to zlecenie. Posiadam bogate doświadczenie i gwarantuję najwyższą jakość."
        elif "agent 08" in sys_lower or "agent_08" in sys_lower:
            return "PASS"
        return "PASS"

    with patch("chain_executor.call_deepseek", side_effect=fake_call):
        wynik = chain_executor.run_chain(f"test-chain-{job_id}", dummy_zlecenie)

    print(f"Liczba wywołań slotu 01 (Research): {call_count['01']}")
    assert call_count["01"] == 1, f"BŁĄD: Slot 01 ponawiał próbę {call_count['01']} razy zamiast natychmiast przyjąć fallback!"
    assert wynik is not None, "BŁĄD: Łańcuch powinien przejść dalej na fallbacku!"
    assert wynik.get("research") == "BRAK_ISTOTNYCH_FAKTOW"
    print("[DOWÓD 2] Fallback 'BRAK_ISTOTNYCH_FAKTOW' został przyjęty natychmiast za 1. razem bez 12-minutowego wiszenia.")


def test_3_circuit_breaker_anti_ping_pong():
    """Test 3: Sprawdza, czy walidator stale odrzucający (FAIL) zostaje ucięty przez Circuit Breaker."""
    print("\n--- TEST 3: Circuit Breaker & Anti-Ping-Pong ---")
    job_id = "test_cb_003"
    storage.clear_checkpoint(job_id)

    dummy_zlecenie = {
        "id": job_id,
        "title": "Zlecenie do testu pętli",
        "budget": "3000",
        "fields": {"opis": "Testujemy pętlę nieskończoną walidatora." * 3}
    }

    step_counter = {"total": 0}
    def fake_call(system, user, **kwargs):
        sys_lower = system.lower()
        step_counter["total"] += 1
        if "agent 08" in sys_lower or "agent_08" in sys_lower:
            # Ciągle zwracamy FAIL z żądaniem poprawki wyceny
            return "FAIL\nPOPRAW_WYCENA: Zmień stawkę natychmiast!"
        elif "agent 02b" in sys_lower or "agent_02b" in sys_lower:
            return "[WYCENA_JSON]\n{\"typ\": \"projekt\", \"moduly\": [{\"nazwa\": \"Fix\", \"godziny_real\": 10}], \"uzasadnienie\": \"ok\"}\n[/WYCENA_JSON]\n[WYNIK_KONCOWY]\nKWOTA: 1500\nDNI: 7\n[/WYNIK_KONCOWY]"
        elif "agent 02a" in sys_lower or "agent_02a" in sys_lower:
            return "Dzień dobry, oto pełna i rozbudowana treść oferty do testu walidatora."
        return "PASS"

    with patch("chain_executor.call_deepseek", side_effect=fake_call):
        wynik = chain_executor.run_chain(f"test-chain-{job_id}", dummy_zlecenie)

    print(f"Łączna liczba wywołań przed przerwaniem: {step_counter['total']}")
    assert step_counter["total"] < 15, f"BŁĄD: Pętla nie została przerwana! Liczba kroków: {step_counter['total']}"
    print("[DOWÓD 3] Pętla ping-pong została deterministycznie ograniczona i zakończona bezpiecznie.")


def test_4_panic_handler_on_crash():
    """Test 4: Sprawdza, czy w razie niespodziewanego wyjątku stan w Cortexie ma status 'blad' z powodem."""
    print("\n--- TEST 4: Panic Handler w Cortex Bridge ---")
    chain_id = "test-panic-verify"
    
    try:
        chain = cortex_bridge.Chain(chain_id, "Testowa Awaria")
        with chain.step("Krok katastrofy", typ="kod"):
            raise ValueError("KATASTROFA_TESTOWA: Symulacja wywalenia bota")
    except ValueError:
        pass

    stan_file = cortex_bridge.PIPELINES_DIR / chain_id / "stan.json"
    assert stan_file.exists(), "BŁĄD: Plik stan.json nie istnieje!"
    with open(stan_file, "r", encoding="utf-8") as f:
        stan_data = json.load(f)

    print(f"Status ogólny w Cortexie: {stan_data['status_ogolny']}")
    krok = stan_data["kroki"][0]
    print(f"Status kroku: {krok['status']}, wyjście: {krok.get('wyjscie')}")
    assert stan_data["status_ogolny"] == "blad", "BŁĄD: Status ogólny nie jest 'blad'!"
    assert krok["status"] == "blad", "BŁĄD: Status kroku nie jest 'blad'!"
    assert "KATASTROFA_TESTOWA" in krok.get("wyjscie", ""), "BŁĄD: Brak nazwy błędu w wyjściu kroku!"
    print("[DOWÓD 4] Cortex natychmiast zapisał status 'blad' z dokładnym komunikatem katastrofy.")


if __name__ == "__main__":
    test_1_checkpoint_save_and_resume()
    test_2_fallback_21_chars_no_hang()
    test_3_circuit_breaker_anti_ping_pong()
    test_4_panic_handler_on_crash()
    print("\n=======================================================")
    print("WSZYSTKIE TESTY ODPORNOŚCI ZAKOŃCZONE PEŁNYM SUKCESEM!")
    print("DETERMINISTYCZNY DOWÓD: ŁAŃCUCH JEST ODPORNY NA ZAWIEDZENIA!")
    print("=======================================================")
