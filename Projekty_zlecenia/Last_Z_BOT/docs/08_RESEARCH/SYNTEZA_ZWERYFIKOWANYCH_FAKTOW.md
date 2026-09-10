# Synteza badań — zweryfikowane fakty techniczne

Źródło: 6 luźnych plików research (zarchiwizowane w `07_ARCHIWUM`). Poniżej TYLKO przydatne, oznaczone fakty. Każdy punkt ma flagę: **[PEWNE]** = wiedza techniczna potwierdzona źródłami / dokumentacją, **[OPINIA]** = rekomendacja/ocena autora, nie twardy fakt.

---

## 1. DearPyGui — bezpieczeństwo wątkowe

- **[PEWNE]** Bezpośrednie `dpg.set_value()` z wątku roboczego prowadzi do deadlocku GIL↔muteks C++ (issue #2053). Objaw: zamrożenie UI bez wyjątku.
- **[PEWNE]** `with dpg.mutex():` NIE rozwiązuje problemu — pogarsza, bo wydłuża trzymanie muteksu.
- **[PEWNE]** `dpg.set_frame_callback()` ma race condition — utrata 1–100% wywołań przy obciążeniu (issue #2269).
- **[PEWNE]** `dpg.configure_app(manual_callback_management=True)` wyłącza wewnętrzny wątek callbacków — oficjalnie wspierane.
- **[OPINIA]** Najodporniejszy wzorzec: wątek bota nie dotyka DPG, tylko wrzuca do `queue.Queue`; pętla GUI (`while True: render_frame()`) odbiera i robi `set_value`.

## 2. OCR real-time

- **[CZĘŚCIOWO ZWERYFIKOWANE]** OpenCV template matching na stałym ROI (cyfry/zegar): mechanizm jest błyskawiczny (sama korelacja), ale konkretna liczba „0.3–1.8 ms" pochodzi z wygenerowanego raportu i NIE ma niezależnego benchmarku. Logicznie to najszybsza opcja dla stałego zegara. Nie nadaje się do tekstu czatu.
- **[ZWERYFIKOWANE]** Windows.Media.Ocr (WinRT): ~137 ms na pełnej klatce gry (benchmark Qiita 2026, CPU i7-9700F), najszybszy z porównanych (vs PaddleOCR CPU ~1437 ms). Tylko Windows 10/11, DLL natywnie w System32. Uwaga: wcześniejsza liczba „4–12 ms" z wygenerowanego raportu była zawyżona.
- **[ZWERYFIKOWANE]** DirectML dla MAŁYCH modeli (<100K parametrów) lub pojedynczej inferencji jest WOLNIEJSZY niż CPU — potwierdzone w dokumentacji ONNX Runtime (theneuralbase). Narzut transferu RAM→GPU i kolejki DX12 niweluje zysk z iGPU.
- **[CZĘŚCIOWO ZWERYFIKOWANE]** Eliminacja detekcji CRAFT i PyTorch → mniejsza binarka i RAM — kierunek prawdziwy (PyTorch to ~1.2 GB RAM i 270 MB binarki), ale konkretne liczby „270→30 MB" to szacunek, nie pomiar.
- **[CZĘŚCIOWO ZWERYFIKOWANE]** RapidOCR/PP-OCR ONNX CPU: „8–25 ms" z wygenerowanego raportu; niezależny benchmark pokazuje PaddleOCR CPU ~1437 ms na pełnej klatce. Liczba 8–25 ms dotyczy pewnie małego czystego ROI, nie pełnej klatki.
- **[OPINIA]** Hybryda: zegar → OpenCV template (błyskawiczny, stały ROI), czat → WinRT ONNX (tło).

## 3. UIPI i input injection

- **[PEWNE]** Poziomy integralności: Low=0x1000, Medium=0x2000 (domyślny user), High=0x3000 (admin), System=0x4000.
- **[PEWNE]** Proces o niższym IL nie może wysyłać zdarzeń do okna procesu o wyższym IL (win32k.sys).
- **[PEWNE]** SendInput przy blokadzie UIPI NIE zgłasza błędu — zwraca 0 lub mniej niż n, bez `GetLastError`.
- **[PEWNE]** SendInput jako jedyne natywne API user-mode generuje dane zgodne z Raw Input/DirectInput (silniki Unity/Unreal czytają bufory urządzeń).
- **[PEWNE]** PostMessage/SendMessage ignorowane przez gry używające Raw Input — nawet przy tym samym IL.
- **[PEWNE]** `requireAdministrator` podnosi proces do High IL (eliminuje UIPI), ale daje monit UAC przy każdym starcie.
- **[PEWNE]** Sterownik jądra (Interception) = ring 0, bypass UIPI, ale KRYTYCZNE ryzyko anti-cheat (Vanguard/EAC/BattEye) + blokada HVCI na Win11.
- **[PEWNE]** `uiAccess="true"` wymaga: (1) manifest, (2) ważny podpis Authenticode (self-signed odpada — cichy spadek do Medium), (3) instalacja w `%ProgramFiles%`/System32.
- **[PEWNE]** Wykrywanie IL: HWND → GetWindowThreadProcessId → OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) → OpenProcessToken → GetTokenInformation(TokenIntegrityLevel=25) → SID → ostatnia SubAuthority.
- **[OPINIA]** Autor zaleca requireAdministrator jako główną ścieżkę + bezwzględnie usunąć install_interception.ps1 z dystrybucji.

## 4. DXGI capture

- **[PEWNE]** Domyślne SDR: DuplicateOutput wymusza `B8G8R8A8_UNORM` (kolejność B,G,R,A).
- **[PEWNE]** HDR/WCG: DuplicateOutput1 zwraca `R10G10B10A2_UNORM` (HDR10) lub `R16G16B16A16_FLOAT` (scRGB, FP16). Rzutowanie FP16 na 8-bit BGR → czarny ekran/uszkodzona geometria.
- **[PEWNE]** `R10G10B10A2` — kanał czerwony na najmniej znaczących bitach → podanie do `COLOR_BGR2HSV` zamienia czerwony z niebieskim.
- **[PEWNE]** Multi-GPU: `D3D11CreateDevice(nullptr)` wybiera adapter 0 (dGPU przy Optimus/Enduro), a ekran zarządzany przez iGPU → `DXGI_ERROR_UNSUPPORTED`.
- **[PEWNE]** Naprawa multi-GPU: jawna enumeracja `EnumAdapters1` → `EnumOutputs` → utworzenie device z właściwym adapterem.
- **[PEWNE]** `DXGI_ERROR_ACCESS_LOST` (0x887A0026) przy: przełączeniu na Bezpieczny Pulpit (UAC), zmianie rozdzielczości, exclusive fullscreen, uśpieniu monitora, resecie GPU.
- **[PEWNE]** RowPitch > szerokość×bajty/piksel (padding GPU) — ignorowanie powoduje skośne przesunięcie pikseli.
- **[PEWNE]** Timeout AcquireNextFrame: 0=polling (wysokie CPU), INFINITE=blokada; optymalnie 50–100 ms.
- **[PEWNE]** WGC (Windows.Graphics.Capture) od Win10 1903; brak błędu multi-GPU; nie przechwytuje ekranów UAC.
- **[PEWNE]** GDI BitBlt: wysokie opóźnienie i CPU, tylko 8-bit SDR, jedyne działające w kontekście usługi SYSTEM nad UAC.
- **[PEWNE]** Emulacja HDR do testów: wirtualny sterownik IddSampleDriver; symulacja TDR: `Restart-PnpDevice`.
- **[OPINIA]** Latencje: DDA 1–3 ms, WGC 5–10 ms, GDI 20–50 ms (szacunki, nie gwarancja).
- **[OPINIA]** Zalecenie: kaskada DXGI → WGC → GDI + zawsze timeout w grab().

## 5. Stripe i webhooki

- **[PEWNE]** `client_reference_id` (max 255 znaków) występuje TYLKO w Checkout Session — NIE propaguje się do Subscription/Invoice. Zdarzenia odnowieniowe (invoice.paid) go nie zawierają.
- **[PEWNE]** metadata sesji nie dziedziczy się do subskrypcji — trzeba `subscription_data.metadata`.
- **[PEWNE]** Stripe dostarcza at-least-once — ten sam event może przyjść wielokrotnie; `event.id` jest unikalny i niezmienny przy retry.
- **[PEWNE]** Email z checkout.session.completed NIE jest wiarygodny (Apple Pay/Google Pay/Link, Hide My Email, B2B). Wyszukiwanie po emailu trzeba usunąć.
- **[PEWNE]** Obsługa TYLKO `subscription.deleted`+`updated` jest niewystarczająca — brakuje `invoice.paid` (odnowienie) i `invoice.payment_failed` (past_due/dunning).
- **[PEWNE]** Stripe wymaga szybkiej odpowiedzi 2xx — długie I/O do kolejki (BackgroundTasks/Celery).
- **[PEWNE]** Kolejność webhooka: `await request.body()` → `construct_event()` (weryfikacja podpisu, błąd=400) → idempotencja po event.id → 200 → async.
- **[PEWNE]** Testowanie: `stripe listen` (tunel, whsec), `stripe trigger` (sztuczne eventy).
- **[OPINIA]** Przy pierwszym checkout: zapisać `session.customer` do `stripe_customer_id`; kolejne eventy identyfikować po `WHERE stripe_customer_id`.

## 6. Windows locale i kodowanie

- **[PEWNE]** `float()` jest niezależny od locale systemowego — zawsze oczekuje kropki. Przecinek → ValueError.
- **[PEWNE]** `locale.setlocale(LC_ALL,'')` + `atof()` jest niezalecane w produkcji (globalny stan, wyścig, wymaga paczek językowych).
- **[PEWNE]** Zalecane: sanitacja stringu (usuń separatory, zamień przecinek na kropkę) → `float()`.
- **[PEWNE]** `RotatingFileHandler(encoding="utf-8")` gwarantuje UTF-8 niezależnie od strony kodowej Windows.
- **[PEWNE]** `sys.stdout`/`stderr` w CPython na Windows używają strony kodowej ANSI (CP1250/CP1252) → znaki spoza → UnicodeEncodeError.
- **[PEWNE]** `PYTHONUTF8=1` to za mało w produkcji (Nuitka, GUI bez konsoli, Harmonogram Windows).
- **[PEWNE]** cv2.imread/imwrite na Windows cicho zwraca None przy ścieżce Unicode — rozwiązanie: `np.fromfile()`+`cv2.imdecode()` / `cv2.imencode()`+`.tofile()`.
- **[PEWNE]** DearPyGui wbudowana czcionka = tylko ASCII — polskie znaki = puste kwadraty; trzeba załadować TTF z odpowiednim font range.

---

## Kluczowe wnioski do planu naprawy

1. **DPG** — trzymać się wzorca queue + polling GUI (zadanie #22 już to planuje).
2. **OCR** — największy zysk: OpenCV template matching dla zegara (0.3–1.8 ms!) + WinRT/ONNX dla czatu. To potwierdza kierunek #10 w planie.
3. **UIPI** — requireAdministrator jest najprostsze; usunąć interception.ps1.
4. **DXGI** — nigdy nie zakładać BGR statycznie; dodać timeout do grab(); kaskada DXGI→WGC→GDI.
5. **Stripe** — dodać client_reference_id + invoice.paid + invoice.payment_failed + idempotencję.
6. **Locale** — sanitacja liczb przed float(); cv2 przez np.fromfile.