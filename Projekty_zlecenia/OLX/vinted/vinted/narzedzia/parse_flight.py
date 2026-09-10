# coding: utf-8
"""Parsuj Next.js flight data (self.__next_f.push) z HTML strony kategorii.
Wyciaga prawdziwy licznik ofert i listy itemow."""
import re, json

html = open(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\katalog_1904.html", encoding="utf-8", errors="ignore").read()

# wyciagnij wszystkie payloady self.__next_f.push([1, "..."])
# format: self.__next_f.push([1,"STRING"])
chunks = []
for m in re.finditer(r'self\.__next_f\.push\(\[1,\s*"(.*?)"\]\)', html, re.S):
    chunks.append(m.group(1))

print("Liczba chunkow flight data:", len(chunks))

# zlacz i dekoduj escaped string
def unescape(s):
    # zamien \\" -> ", \\n -> newline itd (to jest JSON string)
    # pierwsze zrob replace typowych escape'y
    s = s.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
    return s

all_text = ""
for c in chunks:
    all_text += unescape(c) + "\n"

print("Zlaczony tekst len:", len(all_text))

# szukaj licznika - rozne wzorce
print("\n=== LICZNIK / PAGINATION ===")
for pat in [r'total_entries["\s:]*(\d+)', r'totalPages["\s:]*(\d+)', r'total_pages["\s:]*(\d+)',
            r'"totalEntries"\s*:\s*(\d+)', r'"count"\s*:\s*(\d+)', r'([\d\s]+)\s*wynik']:
    ms = re.findall(pat, all_text, re.I)
    if ms:
        print(f"  {pat!r} -> {ms[:5]}")

# szukaj item IDs (9-10 cyfr) z contextem
print("\n=== ITEM ID ===")
ids = set()
for m in re.finditer(r'(\d{9,10})', all_text):
    s = m.start()
    ctx = all_text[max(0,s-40):s+40].replace("\n"," ")
    if "timestamp" not in ctx.lower() and "time" not in ctx.lower():
        ids.add(m.group(1))
print("unikalne 9-10cyfrowe ID:", len(ids), "| przyklady:", list(ids)[:10])

# szukaj title ofert
print("\n=== TITLE ===")
titles = re.findall(r'"title"\s*:\s*"([^"]{3,80})"', all_text)
print("znaleziono title:", len(titles))
for t in titles[:15]:
    print("  ", t)

# zapisz surowy flight data do analizy
with open("flight_data.txt", "w", encoding="utf-8") as f:
    f.write(all_text)
print("\nZapisano flight_data.txt")