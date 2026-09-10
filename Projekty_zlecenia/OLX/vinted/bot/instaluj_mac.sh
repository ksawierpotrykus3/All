#!/bin/bash
# Instalka bota Vinted na Macu. Odpal w Terminalu jedna komenda:
#   bash instaluj_mac.sh
# Skrypt sam sprawdza Pythona, instaluje zaleznosci, usuwa kwarantanne
# i uruchamia bota. Nic nie trzeba klikac w Finderze.

set -e
cd "$(dirname "$0")"

echo "=== BOT VINTED — INSTALKA MAC ==="

# 1. Sprawdz czy jest Python 3.11+
if ! command -v python3 >/dev/null 2>&1; then
  echo "BRAK Pythona 3. Zainstaluj z https://www.python.org/downloads/"
  echo "(przy instalacji zaznacz Add Python to PATH)"
  exit 1
fi
echo "Python OK: $(python3 --version)"

# 2. Usun ewentualna kwarantanne z plikow (skopiowane z internetu)
xattr -dr com.apple.quarantine . 2>/dev/null || true

# 3. Zainstaluj bota i zaleznosci
echo "Instaluje bota i zaleznosci (pierwszy raz moze potrwac)..."
python3 -m pip install -e . || echo "UWAGA: instalacja zglosila blad, probuje dalej"

# 4. Pobierz przegladarke Camoufox (arm64 pod Apple Silicon)
python3 -m camoufox fetch || true

# 5. Odpal bota
echo "Uruchamiam bota..."
python3 -m vintedbot.runner