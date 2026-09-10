# Fix 3: Administrator / UIPI

## Problem
Gra działająca jako Administrator + bot jako standard user → Windows UIPI po cichu blokuje SendInput. W kodzie tylko `logger.warning`, brak twardej blokady i brak elewacji w instalatorze.

## Miejsce w kodzie
- `mvp/bot/runner.py:189-201` — tylko warning przy UIPI mismatch
- `mvp/build/installer.iss` — brak PrivilegesRequired=admin

## Rozwiązanie
1. Dodać `PrivilegesRequired=admin` w instalatorze (żeby bot zawsze działał z uprawnieniami admina)
2. Przy wykryciu UIPI mismatch pokazać jasny komunikat w GUI zamiast logowania

## Kroki
- [ ] Edytować installer.iss — dodać PrivilegesRequired
- [ ] Poprawić detekcję UIPI, pokazać w GUI