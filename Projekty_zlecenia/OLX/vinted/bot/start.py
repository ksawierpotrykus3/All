"""Uniwersalny launcher bota (Windows + Mac).

Klient klika ten plik (albo wpisuje `python start.py`) i nic więcej nie musi
robić. Launcher sam:
  1. sprawdzi czy Python jest dostępny
  2. zainstaluje zależności (pip install -e .)
  3. zainstaluje przeglądarkę Camoufox dla danego systemu
  4. odpali runner konsolowy

Działa identycznie na Windowsie i na Macu — bez plików .bat/.sh.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _python() -> str:
    return sys.executable


def krok(msg: str) -> None:
    print(f"\n[instalka] {msg}")


def zainstaluj_pakiet() -> None:
    """pip install -e . — instaluje vintedbot i zależności."""
    krok("Instaluję bota i zależności (pierwszy raz może potrwać)...")
    r = subprocess.run(
        [_python(), "-m", "pip", "install", "-e", str(ROOT)],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        print("[instalka] UWAGA: instalacja pakietu zgłosiła błąd, ale próbuję dalej.")


def zainstaluj_camoufox() -> None:
    """camoufox fetch — pobiera przeglądarkę pod dany system."""
    try:
        from camoufox.pkgman import installed_verstr
        installed_verstr()
        return  # już jest
    except Exception:
        pass
    krok("Pobieram przeglądarkę Camoufox (Firefox 152)...")
    subprocess.run([_python(), "-m", "camoufox", "fetch"], cwd=str(ROOT), check=False)


def main() -> None:
    print("=== BOT VINTED — INSTALKA ===")
    print(f"Wykryto system: {sys.platform}")

    zainstaluj_pakiet()
    zainstaluj_camoufox()

    krok("Uruchamiam bota...")
    # Import po instalacji — runner jest w pakiecie vintedbot.
    from vintedbot.runner import Runner

    Runner().run()


if __name__ == "__main__":
    main()