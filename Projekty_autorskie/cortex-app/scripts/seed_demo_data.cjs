const fs = require('fs');
const path = require('path');

const base = path.resolve(__dirname, '..', 'baza_wiedzy_kosmos');
const dirs = [
  '01_architektura',
  '02_automatyzacja',
  '03_badania_i_analizy',
  '04_skrypty_narzedziowe',
];

for (const d of dirs) {
  fs.mkdirSync(path.join(base, d), { recursive: true });
}

fs.writeFileSync(
  path.join(base, 'README.md'),
  '# BAZA WIEDZY KOSMOS\n\nDeterministyczne repozytorium wiedzy zorganizowane w hierarchiczne foldery.',
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '01_architektura', 'system_overview.md'),
  '# Architektura Cortex & Kosmos\n\nSystem składa się z silnika kanwy 2D, integracji z AI (DeepSeek) oraz deterministycznej bazy danych struktury projektów (Kosmos).',
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '01_architektura', 'baza_danych_schemat.json'),
  JSON.stringify(
    {
      wersja: '2.0.0',
      moduly: ['kosmos', 'supervisor', 'canvas', 'storage'],
      storage: 'StorageEngine (atomic writes)',
      status: 'stabilny',
    },
    null,
    2
  ),
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '02_automatyzacja', 'zlecenie_lead_hunter.py'),
  '# Lead Hunter Worker\nimport json\nimport sys\n\ndef run():\n    print("[LeadHunter] Skanowanie zlecen i leadow...")\n\nif __name__ == "__main__":\n    run()\n',
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '02_automatyzacja', 'pipeline_config.json'),
  JSON.stringify(
    {
      id: 'pipeline_lead_hunter_v1',
      nazwa: 'Automatyczne pozyskiwanie zlecen',
      kroki: ['pobranie_ofert', 'weryfikacja_stawek', 'bramka_bezpieczenstwa', 'wyslanie_odpowiedzi'],
    },
    null,
    2
  ),
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '03_badania_i_analizy', 'raport_rynkowy_2026.txt'),
  'Raport rynkowy Q3 2026:\n- Popyt na automatyzacje no-code/low-code: +45%\n- Srednia stawka za godzine programisty Python: 220 PLN\n- Glowne zrodla zlecen: Useme, LinkedIn, Grupy FB.',
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '03_badania_i_analizy', 'analiza_konkurencji.md'),
  '# Analiza Konkurencji\n\nKonkurencja oferuje narzedzia oparte o nieprzewidywalne wykresy silowe. Cortex Kosmos zapewnia 100% deterministyczna hierarchie i bezposrednie operacje na dysku.',
  'utf-8'
);

fs.writeFileSync(
  path.join(base, '04_skrypty_narzedziowe', 'backup_bazy.bat'),
  '@echo off\necho [BACKUP] Tworzenie kopii zapasowej bazy danych Kosmos...\ncopy data\\projekty\\kosmos_db.json data\\projekty\\kosmos_db.json.bak\necho [BACKUP] Zrobione.\n',
  'utf-8'
);

console.log('Pomyslnie utworzono pliki bazy wiedzy w:', base);
