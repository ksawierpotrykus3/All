#!/usr/bin/env python3
"""
Narzędzie do zarządzania konfliktami w dokumentacji Vinted Bot.
Pomaga identyfikować, analizować i rozwiązywać sprzeczności między dokumentami.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
import argparse

class DocumentationConflictManager:
    def __init__(self, project_root: str = "F:\\PROJEKTY\\vinted"):
        self.project_root = Path(project_root)
        self.conflicts_file = self.project_root / "vinted" / "raporty" / "00_POWTORZENIA_I_SPRZECZNOSCI.md"
        self.synthesis_dir = self.project_root / "vinted" / "testy_camoufox" / "docs" / "synthesis"
        
    def find_markdown_files(self) -> List[Path]:
        """Znajdź wszystkie pliki markdown w projekcie."""
        md_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Pomijamy node_modules i inne niepotrzebne katalogi
            if 'node_modules' in dirs:
                dirs.remove('node_modules')
            if '.git' in dirs:
                dirs.remove('.git')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
                
            for file in files:
                if file.endswith('.md'):
                    md_files.append(Path(root) / file)
        return md_files
    
    def extract_headings(self, filepath: Path) -> Dict[str, List[str]]:
        """Wyodrębnij nagłówki i treść z pliku markdown."""
        headings = {}
        current_heading = None
        content = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                # Sprawdzamy nagłówki (#, ##, ###)
                heading_match = re.match(r'^(#{1,4})\s+(.+)$', line.strip())
                if heading_match:
                    if current_heading and content:
                        headings[current_heading] = content.copy()
                    level = len(heading_match.group(1))
                    title = heading_match.group(2)
                    current_heading = f"{'#' * level} {title}"
                    content = []
                elif current_heading and line.strip():
                    content.append(line.strip())
            
            if current_heading and content:
                headings[current_heading] = content
        
        except Exception as e:
            print(f"Błąd czytania {filepath}: {e}")
            
        return headings
    
    def find_duplicate_headings(self, files: List[Path]) -> Dict[str, List[Path]]:
        """Znajdź duplikaty nagłówków między plikami."""
        all_headings = {}
        
        for filepath in files:
            headings = self.extract_headings(filepath)
            for heading, content in headings.items():
                if heading not in all_headings:
                    all_headings[heading] = []
                all_headings[heading].append(filepath)
        
        # Filtruj tylko duplikaty (2+ pliki z tym samym nagłówkiem)
        duplicates = {h: paths for h, paths in all_headings.items() if len(paths) > 1}
        return duplicates
    
    def find_conflicting_statements(self, files: List[Path]) -> List[Dict]:
        """Znajdź sprzeczne stwierdzenia między dokumentami."""
        conflicts = []
        
        # Słowa kluczowe wskazujące na stwierdzenia faktów
        fact_keywords = [
            "udowodnione", "potwierdzone", "zweryfikowane", "zmierzone",
            "fałsz", "nieprawda", "zmyślone", "nieudowodnione",
            "100%", "działa", "nie działa", "możliwe", "niemożliwe"
        ]
        
        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                
                # Znajdź linie z faktami
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if any(keyword in line for keyword in fact_keywords):
                        # Sprawdź czy inne pliki mają sprzeczne informacje
                        conflicts.append({
                            'file': filepath,
                            'line': i + 1,
                            'statement': line[:200],  # Pierwsze 200 znaków
                            'context': '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                        })
                        
            except Exception as e:
                print(f"Błąd analizy {filepath}: {e}")
        
        return conflicts
    
    def generate_conflict_report(self) -> str:
        """Wygeneruj raport konfliktów."""
        md_files = self.find_markdown_files()
        
        report = []
        report.append("# Raport Konfliktów Dokumentacyjnych")
        report.append(f"Wygenerowano: {Path(__file__).name}")
        report.append(f"Znaleziono plików MD: {len(md_files)}")
        report.append("")
        
        # 1. Duplikaty nagłówków
        duplicates = self.find_duplicate_headings(md_files)
        if duplicates:
            report.append("## 1. DUPLIKATY NAGŁÓWKÓW")
            report.append("")
            for heading, files in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
                if len(files) > 1:  # Tylko prawdziwe duplikaty
                    report.append(f"### {heading}")
                    report.append(f"**Występuje w {len(files)} plikach:**")
                    for file in files:
                        rel_path = file.relative_to(self.project_root)
                        report.append(f"- `{rel_path}`")
                    report.append("")
        
        # 2. Potencjalne konflikty faktów
        conflicts = self.find_conflicting_statements(md_files)
        if conflicts:
            report.append("## 2. POTENCJALNE KONFLIKTY FAKTÓW")
            report.append("")
            for i, conflict in enumerate(conflicts[:10], 1):  # Pierwsze 10
                rel_path = conflict['file'].relative_to(self.project_root)
                report.append(f"### Konflikt #{i}")
                report.append(f"**Plik:** `{rel_path}` (linia {conflict['line']})")
                report.append(f"**Stwierdzenie:** `{conflict['statement']}`")
                report.append("**Kontekst:**")
                report.append("```")
                report.append(conflict['context'])
                report.append("```")
                report.append("")
        
        # 3. Zalecenia
        report.append("## 3. ZALECENIA")
        report.append("")
        report.append("### Do zrobienia:")
        report.append("1. **Zidentyfikuj prawdziwe konflikty** z powyższej listy")
        report.append("2. **Sprawdź dowody** w captured_requests.json i logach testów")
        report.append("3. **Aktualizuj syntezy** w `testy_camoufox/docs/synthesis/`")
        report.append("4. **Oznacz rozstrzygnięte** w `00_POWTORZENIA_I_SPRZECZNOSCI.md`")
        report.append("")
        report.append("### Hierarchia wiarygodności:")
        report.append("1. **captured_requests.json** - najwyższa (rzeczywiste requesty)")
        report.append("2. **Logi testów** (*.log, *.json) - wysoką")
        report.append("3. **Analiza kodu** (JS reverse) - średnia")  
        report.append("4. **Hipotezy AI/Research** - najniższa")
        
        return '\n'.join(report)
    
    def update_synthesis_docs(self):
        """Zaktualizuj dokumenty syntezy na podstawie aktualnych konfliktów."""
        print("Aktualizacja dokumentów syntezy...")
        
        # Sprawdź czy mamy aktualny raport konfliktów
        if not self.conflicts_file.exists():
            print(f"Brak pliku konfliktów: {self.conflicts_file}")
            return
        
        # Tutaj można dodać logikę automatycznej aktualizacji
        # na podstawie 00_POWTORZENIA_I_SPRZECZNOSCI.md
        print("Uruchom skrypt ręcznie z opcją --report aby zobaczyć konflikty")
        print("Następnie zaktualizuj ręcznie syntezy w docs/synthesis/")

def main():
    parser = argparse.ArgumentParser(description='Zarządzaj konfliktami w dokumentacji Vinted Bot')
    parser.add_argument('--report', action='store_true', help='Wygeneruj raport konfliktów')
    parser.add_argument('--update', action='store_true', help='Zaktualizuj syntezy')
    parser.add_argument('--output', type=str, help='Plik wyjściowy dla raportu')
    
    args = parser.parse_args()
    
    manager = DocumentationConflictManager()
    
    if args.report:
        report = manager.generate_conflict_report()
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"Raport zapisano do: {args.output}")
        else:
            print(report)
    
    elif args.update:
        manager.update_synthesis_docs()
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()