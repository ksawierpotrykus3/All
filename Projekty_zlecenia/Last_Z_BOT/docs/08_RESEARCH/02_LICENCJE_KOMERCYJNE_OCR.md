> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Audyt licencyjny silników Fast OCR do użytku komercyjnego

Data audytu: 2026-09-03
Status: **100% LEGALNE I BEZPŁATNE DO UŻYTKU KOMERCYJNEGO (Commercial-Safe)**

---

## 1. Zestawienie komponentów nowego potoku Fast OCR

| Komponent | Rola w projekcie | Licencja | Dozwolony użytek komercyjny? | Wymóg copyleft (otwieranie kodu bota)? |
| :--- | :--- | :--- | :--- | :--- |
| **`Windows.Media.Ocr`** | Natywne WinRT API systemu Windows 10/11 (Czat, Alerty) | Standardowe API Windows (EULA Windows Developer) | **TAK (Bez opłat i tantiem)** | **NIE** |
| **`winocr`** | Python wrapper WinRT dla `Windows.Media.Ocr` | **MIT License** | **TAK** | **NIE** |
| **`rapidocr-onnxruntime`** | Silnik OCR C++ (Timer, rozpoznawanie tekstu) | **Apache License 2.0** | **TAK** | **NIE** |
| **Wagi modeli PP-OCR (Baidu)** | Modele wag sieci neuronowej (CRNN / DBNet) | **Apache License 2.0** | **TAK (Royalty-free)** | **NIE** |
| **`onnxruntime` (Microsoft)** | Silnik inferencji sieci neuronowych ONNX | **MIT License** | **TAK** | **NIE** |
| **`opencv-python`** | Przetwarzanie obrazu, skalowanie, maski HSV | **Apache License 2.0** | **TAK** | **NIE** |

---

## 2. Szczegółowa analiza prawna każdego komponentu

### A. Natywne Windows.Media.Ocr i wrapper `winocr`
- **Podstawa prawna**: `Windows.Media.Ocr` to wbudowane API systemowe Microsoft Windows 10 i Windows 11.
- **Opłaty**: Brak opłat za wywołania, brak opłat per-dokument, brak limitów komercyjnych (w przeciwieństwie do chmurowego Azure AI Vision).
- **Wrapper `winocr`**: Kod biblioteki opublikowany przez autora na GitHubie na licencji **MIT License**. Licencja MIT zezwala na komercyjne użycie, redystrybucję i łączenie z zamkniętym oprogramowaniem komercyjnym.

### B. RapidOCR (`rapidocr-onnxruntime`)
- **Podstawa prawna**: Projekt RapidAI/RapidOCR udostępniony jest na licencji **Apache License 2.0**.
- **Warunki komercyjne**: Licencja Apache 2.0 jest licencją wybitnie permisywną (permissive), zezwalającą na komercyjne wykorzystanie, sprzedaż oprogramowania oraz kompilację do formatów binarnych (.exe przez Nuitka/PyInstaller) bez ujawniania kodu własnego aplikacji bota.
- **Obowiązki**: Dołączenie notki licencyjnej Apache 2.0 w dokumentacji/dystrybucji aplikacji (np. plik `THIRD_PARTY_LICENSES.txt`).

### C. Wagi modeli PP-OCR (Baidu PaddleOCR)
- **Podstawa prawna**: Modele z serii PP-OCR (v3 / v4) wytrenowane przez zespół Baidu PaddlePaddle są oficjalnie objęte licencją **Apache License 2.0**.
- **Legalność komercyjna**: Baidu wprost deklaruje licencję Apache 2.0 dla toolkitu oraz wag pre-trained, co oznacza prawo do ich komercyjnego wykorzystywania bez tantiem (royalty-free commercial use).

### D. Microsoft ONNX Runtime
- **Podstawa prawna**: Biblioteka Microsoft ONNX Runtime podlega licencji **MIT License**.
- **Legalność komercyjna**: Pełna swoboda komercyjna.

---

## 3. Porównanie ze starym rozwiązaniem (EasyOCR)

Wcześniejsze rozwiązanie bazowało na PyTorch (`torch`) i modelach EasyOCR (CRAFT + CRNN):
- Model detektora **CRAFT** w EasyOCR pochodził z repozytorium Clova AI Research, gdzie w części publikacji akademickich stosowano licencje CC-BY-NC (Non-Commercial Only)!
- **Przejście na Fast OCR (WinOCR + RapidOCR / PaddleOCR Apache 2.0) całkowicie wyeliminowało ryzyko naruszenia licencji akademickiej CRAFT.**

---

## 4. Wnioski i zalecenia końcowe
Nowy potok Fast OCR jest w 100% legalny, bezpieczny komercyjnie i wolny od restrykcji copyleft (GPL). Jedynym zalecanym wymogiem formalnym jest umieszczenie standardowego pliku `LICENSE` / notek licencyjnych MIT i Apache 2.0 w katalogu instalatora bota.
