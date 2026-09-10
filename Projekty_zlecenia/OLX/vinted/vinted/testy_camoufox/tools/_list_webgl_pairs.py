# coding: utf-8
"""Wypisuje dostępne pary vendor/renderer WebGL dla Windows z bazy Camoufox."""
import sqlite3
from pathlib import Path
import camoufox.webgl.sample as s

# odnajdź bazę webgl w pakiecie camoufox
pkg = Path(s.__file__).parent
dbs = list(pkg.glob("*.db")) + list(pkg.glob("*.sqlite")) + list(pkg.glob("*.sqlite3"))
print("Bazy:", [str(d) for d in dbs])

for db in dbs:
    try:
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        # sprawdź tabelę i kolumny
        cols = [r[1] for r in cur.execute("PRAGMA table_info(webgl_fingerprints)").fetchall()]
        print("Kolumny:", cols)
        rows = cur.execute(
            "SELECT DISTINCT vendor, renderer FROM webgl_fingerprints WHERE win > 0 ORDER BY vendor LIMIT 60"
        ).fetchall()
        print(f"Liczba par (win>0): {len(rows)}")
        for v, r in rows[:40]:
            print(f"  {v!r} / {r!r}")
        conn.close()
        break
    except Exception as e:
        print("Błąd dla", db, ":", e)