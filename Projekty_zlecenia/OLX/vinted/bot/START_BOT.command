#!/bin/bash
# Uruchom bota na Macu (kliknij dwukrotnie ten plik w Finderze).
# Pierwsze uruchomienie pobierze zależności i przeglądarkę Camoufox (arm64).
cd "$(dirname "$0")" || exit 1
python3 start.py