# coding: utf-8
import glob, os, re, sys

base = r'C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\chunks'
seen = set()
out = []

for f in glob.glob(os.path.join(base, '*.js')):
    s = open(f, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'["`][^"`]*(?:items|user|closet)[^"`]*["`]', s):
        t = m.group(0)
        if t not in seen and len(t) < 150:
            seen.add(t)
            out.append(t)

for line in out[:80]:
    print(line)