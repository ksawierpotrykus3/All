#!/usr/bin/env python3
"""
Skrypt do czyszczenia wrażliwych danych z plików projektu.
Usuwa hardcoded tokeny i zastępuje je placeholderami.
"""

import os
import re
import json
from pathlib import Path

# Wrażliwe tokeny do usunięcia
SENSITIVE_TOKENS = {
    "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e": "CSRF_TOKEN_PLACEHOLDER",
    "98c6af5a-87da-45f2-9be5-24cf9345b003": "ANON_ID_PLACEHOLDER"
}

# Wzorce do wyszukiwania
PATTERNS = [
    r'access_token_web["\']?\s*:\s*["\'][^"\']+["\']',
    r'refresh_token_web["\']?\s*:\s*["\'][^"\']+["\']',
    r'_vinted_fr_session["\']?\s*:\s*["\'][^"\']+["\']',
    r'CSRF\s*=\s*["\'][^"\']+["\']',
    r'ANON\s*=\s*["\'][^"\']+["\']',
    r'"x-csrf-token["\']?\s*:\s*["\'][^"\']+["\']',
    r'"x-anon-id["\']?\s*:\s*["\'][^"\']+["\']'
]

def _redact(match):
    """Podmienia tylko wartość, zachowując klucz, separator i znak cytatu.

    Wartość to ostatni fragment w cudzysłowie; początek znajdujemy od prawej,
    dzięki czemu działa zarówno dla JSON ('key': "v"), jak i Pythona (KEY = "v").
    """
    text = match.group(0)
    closing = text[-1]
    opening = text.rfind(closing, 0, len(text) - 1)
    if opening == -1:
        return text
    return text[:opening] + closing + "REDACTED" + closing


def clean_file(filepath):
    """Czyści pojedynczy plik z wrażliwych danych."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Zamiana hardcoded tokenów
        for token, placeholder in SENSITIVE_TOKENS.items():
            content = content.replace(token, placeholder)

        # Usuwanie pełnych wartości cookies/tokenów — wspólny separator ':' i '='.
        for pattern in PATTERNS:
            content = re.sub(pattern, _redact, content)

        if content != original:
            backup = filepath.with_suffix(filepath.suffix + '.bak')
            backup.write_text(original, encoding='utf-8')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"Błąd przy czyszczeniu {filepath}: {e}")
        return False

def main():
    project_root = Path(__file__).parent.parent
    cleaned_count = 0
    
    # Przeszukaj wszystkie pliki
    for ext in ['.py', '.json', '.txt', '.md', '.js']:
        for filepath in project_root.rglob(f'*{ext}'):
            if filepath.is_file() and not any(part.startswith('.') for part in filepath.parts):
                if clean_file(filepath):
                    print(f"✓ Wyczyczono: {filepath.relative_to(project_root)}")
                    cleaned_count += 1
    
    print(f"\n✅ Wyczyczono {cleaned_count} plików z wrażliwych danych.")
    print("⚠️  UWAGA: To nie zastępuje resetowania tokenów na serwerze Vinted!")
    print("   Musisz ręcznie zresetować hasło i tokeny na koncie Vinted.")

if __name__ == "__main__":
    main()
