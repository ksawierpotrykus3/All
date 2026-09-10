# coding: utf-8
"""Kopiuje cookie `datadome` z profil_firefox (FF152) do profil_firefox_135.

[DEPRECATED 2026-09-01] profil_firefox (FF152) został usunięty — ten skrypt
zostaje tylko jako referencja historyczna. Nie używać.
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "profil_firefox" / "cookies.sqlite"
DST = BASE / "profil_firefox_135" / "cookies.sqlite"


def cols(db, table):
    return [c[1] for c in db.execute(f"PRAGMA table_info({table})").fetchall()]


def main() -> None:
    if not SRC.exists() or not DST.exists():
        print("Brak zrodlowego lub docelowego cookies.sqlite")
        return

    src = sqlite3.connect(str(SRC))
    src_cols = cols(src, "moz_cookies")
    rows = src.execute("SELECT * FROM moz_cookies WHERE name='datadome'").fetchall()
    src.close()

    if not rows:
        print("Brak datadome w zrodle")
        return

    dst = sqlite3.connect(str(DST))
    dst_cols = cols(dst, "moz_cookies")
    # Uzyj tylko kolumn obecnych w obu bazach.
    common = [c for c in src_cols if c in dst_cols]
    print(f"Wspolne kolumny: {common}")

    for row in rows:
        rec = dict(zip(src_cols, row))
        print(f"Znaleziono datadome: host={rec['host']} expiry={rec['expiry']}")

        values = [rec[c] for c in common]
        dst.execute("DELETE FROM moz_cookies WHERE name='datadome'")
        dst.execute(
            f"INSERT INTO moz_cookies ({', '.join(common)}) "
            f"VALUES ({', '.join('?' * len(common))})",
            values,
        )
        dst.commit()
        print("Skopiowano datadome do profil_firefox_135")

    # Weryfikacja
    chk = dst.execute("SELECT name, host, expiry FROM moz_cookies WHERE name='datadome'").fetchall()
    print("Po kopii:", chk)
    dst.close()


if __name__ == "__main__":
    main()