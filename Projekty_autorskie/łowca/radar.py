# radar.py - Moduł AUTO Śledzenia (Watcher / Radar) z maszyną stanów PENDING -> PROCESSING -> DONE / FAILED
import os
import re
import sys
import json
import time
import random
import threading
import subprocess
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# Obsługa kodowania UTF-8 dla konsoli Windows
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception: pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SLEDZONE_FILE = os.path.join(SCRIPT_DIR, "sledzone.txt")
BAZA_FILE = os.path.join(SCRIPT_DIR, "sledzenie_baza.json")
COOKIE_PATH = os.path.join(SCRIPT_DIR, "cookies.txt")

# Interwały sprawdzania (w sekundach)
INTERVAL_FAST = 600      # 10 minut (YouTube, Reddit)
INTERVAL_SLOW = 1800     # 30 minut (Facebook, Instagram)
MAX_BACKOFF = 3600       # Maksymalnie 60 minut przy błędach
MAX_KNOWN_IDS_PER_SRC = 200 # Limit FIFO dla bazy
MAX_RETRIES = 3          # Maksymalna liczba powtórzeń nieudanego zadania

def classify_source_type(url):
    u = url.strip().lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "YOUTUBE"
    if "reddit.com" in u or "redd.it" in u:
        return "REDDIT"
    if "instagram.com" in u or "instagr.am" in u:
        return "INSTAGRAM"
    if "facebook.com" in u or "fb.com" in u:
        return "FACEBOOK"
    return "UNKNOWN"

class RadarDatabase:
    """Wątkowo bezpieczna, atomowa baza danych z pełną maszyną stanów zadań (PENDING -> DONE/FAILED)."""
    def __init__(self, db_path=BAZA_FILE):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        if not os.path.exists(self.db_path):
            return {"sources": {}, "tasks": {}}
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                if "sources" not in d or "tasks" not in d:
                    # Migracja starej płaskiej struktury do wersji ze strukturą zadań
                    sources = {}
                    for k, v in d.items():
                        if isinstance(v, dict) and "typ" in v:
                            sources[k] = v
                    return {"sources": sources, "tasks": {}}
                return d
        except Exception:
            return {"sources": {}, "tasks": {}}

    def _save_atomic(self):
        tmp_path = self.db_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.db_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass
            print(f"[Radar DB] Błąd atomowego zapisu bazy: {e}")

    def get_known_ids(self, source_url):
        with self.lock:
            src = self.data["sources"].get(source_url, {})
            known = set(src.get("znane_id", []))
            # Dodajemy także ID zadań aktualnie w toku lub zarejestrowanych
            for t_url, t_data in self.data["tasks"].items():
                if t_data.get("source_url") == source_url:
                    if t_data.get("status") in ["PENDING", "PROCESSING", "DONE"]:
                        iid = t_data.get("item_id")
                        if iid: known.add(iid)
                        known.add(t_url)
            return known

    def should_check(self, source_url, platform):
        with self.lock:
            if source_url not in self.data["sources"]:
                return True
            src_data = self.data["sources"][source_url]
            next_check = src_data.get("next_check", 0)
            return time.time() >= next_check

    def register_pending_tasks(self, source_url, platform, new_items):
        """Rejestruje nowe wpisy w bazie ze statusem PENDING (nie dodaje ich jeszcze do znane_id dopóki nie zostaną DONE)."""
        registered = []
        with self.lock:
            if source_url not in self.data["sources"]:
                self.data["sources"][source_url] = {
                    "typ": platform,
                    "znane_id": [],
                    "ostatnie_sprawdzenie": "",
                    "status": "OK",
                    "error_count": 0,
                    "next_check": 0
                }
            
            src = self.data["sources"][source_url]
            src["typ"] = platform
            src["ostatnie_sprawdzenie"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            src["status"] = "OK"
            src["error_count"] = 0
            
            base_interval = INTERVAL_FAST if platform in ["YOUTUBE", "REDDIT"] else INTERVAL_SLOW
            jitter = random.randint(15, 120)
            src["next_check"] = time.time() + base_interval + jitter

            for it in new_items:
                target_url = it["url"]
                item_id = it.get("id", target_url)
                
                # Sprawdzamy czy zadanie już istnieje
                existing_task = self.data["tasks"].get(target_url)
                if not existing_task or existing_task.get("status") not in ["DONE", "PROCESSING"]:
                    task_obj = {
                        "task_id": f"{platform.lower()}_{item_id}",
                        "item_id": item_id,
                        "source_url": source_url,
                        "target_url": target_url,
                        "platform": platform,
                        "title": it.get("title", ""),
                        "discovered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "PENDING",
                        "retries": existing_task.get("retries", 0) if existing_task else 0,
                        "max_retries": MAX_RETRIES,
                        "last_error": None
                    }
                    self.data["tasks"][target_url] = task_obj
                    registered.append(task_obj)
                    
            self._save_atomic()
        return registered

    def mark_task_processing(self, target_url):
        """Ustawia status zadania na PROCESSING."""
        with self.lock:
            if target_url in self.data["tasks"]:
                self.data["tasks"][target_url]["status"] = "PROCESSING"
                self._save_atomic()

    def mark_task_done(self, target_url):
        """Oznacza zadanie jako DONE i atomowo dopisuje ID do znane_id źródła (z limitem FIFO 200)."""
        with self.lock:
            if target_url in self.data["tasks"]:
                task = self.data["tasks"][target_url]
                task["status"] = "DONE"
                task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                src_url = task.get("source_url")
                item_id = task.get("item_id", target_url)
                if src_url and src_url in self.data["sources"]:
                    existing_ids = self.data["sources"][src_url].get("znane_id", [])
                    if item_id not in existing_ids:
                        existing_ids.insert(0, item_id)
                    self.data["sources"][src_url]["znane_id"] = existing_ids[:MAX_KNOWN_IDS_PER_SRC]
                    
                self._save_atomic()

    def mark_task_failed(self, target_url, error_msg):
        """Obsługuje błąd przetwarzania zadania z mechanizmem retry (do max_retries)."""
        with self.lock:
            if target_url in self.data["tasks"]:
                task = self.data["tasks"][target_url]
                task["retries"] = task.get("retries", 0) + 1
                task["last_error"] = str(error_msg)[:200]
                
                if task["retries"] >= task.get("max_retries", MAX_RETRIES):
                    task["status"] = "FAILED"
                    print(f"[Radar DB] Zadanie {target_url} trwale nie powiodło się (przekroczono limit {MAX_RETRIES} prób).")
                else:
                    task["status"] = "PENDING"
                    print(f"[Radar DB] Zadanie {target_url} zwróciło błąd. Ponawiam próbę ({task['retries']}/{MAX_RETRIES}).")
                    
                self._save_atomic()

    def get_pending_tasks(self):
        """Zwraca wszystkie zadania ze statusem PENDING (np. po restarcie programu)."""
        with self.lock:
            pending = []
            for t_url, t_data in self.data["tasks"].items():
                if t_data.get("status") == "PENDING":
                    pending.append(t_data)
            return pending

    def mark_error(self, source_url, platform, error_msg):
        with self.lock:
            if source_url not in self.data["sources"]:
                self.data["sources"][source_url] = {
                    "typ": platform,
                    "znane_id": [],
                    "ostatnie_sprawdzenie": "",
                    "status": "ERROR",
                    "error_count": 0,
                    "next_check": 0
                }
            src = self.data["sources"][source_url]
            src["ostatnie_sprawdzenie"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            src["status"] = f"ERROR: {str(error_msg)[:100]}"
            src["error_count"] = src.get("error_count", 0) + 1
            
            backoff_sec = min(MAX_BACKOFF, (2 ** min(src["error_count"], 8)) * 60)
            src["next_check"] = time.time() + backoff_sec
            self._save_atomic()

# === SKANERY PER-PLATFORMA ===

def skanuj_youtube(channel_url, known_ids, limit=20):
    """Błyskawicznie skanuje kanał YouTube przez yt-dlp flat-playlist."""
    url = channel_url.rstrip('/')
    if not url.endswith('/videos'):
        url += '/videos'
        
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--playlist-end", str(limit),
        "--print", "%(id)s\t%(url)s\t%(title)s",
        url
    ]
    if os.path.exists(COOKIE_PATH):
        cmd.extend(["--cookies", COOKIE_PATH])

    res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
    if res.returncode != 0:
        raise Exception(f"yt-dlp error: {res.stderr.strip()[:150]}")

    new_items = []
    lines = res.stdout.strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 2:
            vid_id, vid_url = parts[0].strip(), parts[1].strip()
            title = parts[2].strip() if len(parts) > 2 else ""
            if not vid_url.startswith("http"):
                vid_url = f"https://www.youtube.com/watch?v={vid_id}"
                
            if vid_id in known_ids or vid_url in known_ids:
                break
            new_items.append({
                "id": vid_id,
                "url": vid_url,
                "title": title
            })
            
    new_items.reverse()
    return new_items

def skanuj_reddit(subreddit_url, known_ids, limit=25):
    """Skanuje subreddit hybrydowo (JSON/RSS -> Playwright fallback)."""
    sub_url = subreddit_url.rstrip('/')
    if not sub_url.endswith('/new'):
        sub_url += '/new'
        
    json_url = f"{sub_url}/.json?limit={limit}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}
    
    try:
        r = requests.get(json_url, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            children = data.get("data", {}).get("children", [])
            new_items = []
            for c in children:
                d = c.get("data", {})
                pid = d.get("id")
                permalink = d.get("permalink")
                title = d.get("title", "")
                if pid and permalink:
                    full_url = f"https://www.reddit.com{permalink}"
                    if pid in known_ids or full_url in known_ids:
                        break
                    new_items.append({"id": pid, "url": full_url, "title": title})
            if new_items or len(children) > 0:
                new_items.reverse()
                return new_items
    except Exception:
        pass

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=headers['User-Agent'], viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(sub_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        
        post_links = page.evaluate("""() => {
            const list = [];
            const seen = new Set();
            document.querySelectorAll('a[href*="/comments/"], a[data-testid="post-title"]').forEach(a => {
                let href = a.href.split('?')[0];
                if (!seen.has(href)) {
                    seen.add(href);
                    list.push(href);
                }
            });
            return list;
        }""")
        browser.close()

    new_items = []
    for purl in post_links:
        m = re.search(r'/comments/([a-z0-9]+)/', purl)
        pid = m.group(1) if m else purl
        if pid in known_ids or purl in known_ids:
            break
        new_items.append({"id": pid, "url": purl, "title": ""})

    new_items.reverse()
    return new_items

def skanuj_instagram(profile_url, known_ids, limit=15):
    """Skanuje profil Instagrama (wyciąga najnowsze linki z siatki i stanu JSON)."""
    from playwright.sync_api import sync_playwright
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=headers['User-Agent'], viewport={"width": 1280, "height": 1000})
        page = context.new_page()
        page.goto(profile_url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(3500)
        
        page.evaluate("""() => {
            document.querySelectorAll('button').forEach(b => {
                const t = b.innerText.toLowerCase();
                if (t.includes('allow') || t.includes('decline') || t.includes('zezwól') || t.includes('odrzuć')) b.click();
            });
            document.querySelectorAll('div[role="dialog"] svg, div[role="dialog"] button').forEach(el => {
                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                if (label.includes('close') || label.includes('zamknij')) el.closest('button')?.click();
            });
        }""")
        page.wait_for_timeout(1000)
        
        post_links = page.evaluate("""() => {
            const list = [];
            const seen = new Set();
            document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]').forEach(a => {
                let href = a.href.split('?')[0];
                if (!seen.has(href)) {
                    seen.add(href);
                    list.push(href);
                }
            });
            return list;
        }""")
        
        # Opcjonalny fallback na parsowanie stanu JSON
        if not post_links:
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            for sc in soup.find_all('script', type='application/json'):
                try:
                    js = json.loads(sc.string or '{}')
                    # Przeszukiwanie struktury xdt_api
                    def find_shortcodes(obj):
                        codes = []
                        if isinstance(obj, dict):
                            if 'shortcode' in obj:
                                codes.append(obj['shortcode'])
                            for v in obj.values():
                                codes.extend(find_shortcodes(v))
                        elif isinstance(obj, list):
                            for x in obj:
                                codes.extend(find_shortcodes(x))
                        return codes
                    for c in find_shortcodes(js):
                        p_url = f"https://www.instagram.com/p/{c}/"
                        if p_url not in post_links:
                            post_links.append(p_url)
                except Exception:
                    pass
                    
        browser.close()

    new_items = []
    for purl in post_links:
        m = re.search(r'/(?:p|reel)/([A-Za-z0-9_-]+)/', purl)
        pid = m.group(1) if m else purl
        if pid in known_ids or purl in known_ids:
            break
        new_items.append({"id": pid, "url": purl, "title": ""})

    new_items.reverse()
    return new_items

def skanuj_facebook(profile_url, known_ids, limit=15):
    """Skanuje profil Facebooka z ciasteczkami sesyjnymi."""
    from playwright.sync_api import sync_playwright
    
    def load_netscape_cookies(c_path):
        cookies = []
        if not os.path.exists(c_path): return cookies
        with open(c_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                parts = line.split('\t')
                if len(parts) >= 7 and 'facebook' in parts[0]:
                    domain, flag, path, secure, expiry, name, value = parts[:7]
                    try: exp_int = int(expiry) if expiry and expiry != '0' else None
                    except ValueError: exp_int = None
                    c_dict = {
                        'name': name, 'value': value,
                        'domain': domain.replace('#HttpOnly_', ''),
                        'path': path, 'secure': secure.upper() == 'TRUE'
                    }
                    if exp_int and exp_int > 0: c_dict['expires'] = exp_int
                    cookies.append(c_dict)
        return cookies

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1000}
        )
        fb_cookies = load_netscape_cookies(COOKIE_PATH)
        if fb_cookies:
            context.add_cookies(fb_cookies)
            
        page = context.new_page()
        page.goto(profile_url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(3500)
        
        try:
            page.locator('div[role="dialog"] button:has-text("Zezwól"), div[role="dialog"] button:has-text("Odrzuć"), button:has-text("Allow")').first.click()
            page.wait_for_timeout(1000)
        except Exception:
            pass
            
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(1800)
        
        posts = page.evaluate("""() => {
            const list = [];
            const seen = new Set();
            document.querySelectorAll('div[role="feed"] div[role="article"], div[data-pagelet*="FeedUnit"], div[data-pagelet="ProfileTimeline"] div[role="article"]').forEach(art => {
                const links = art.querySelectorAll('a[href*="/posts/"], a[href*="/videos/"], a[href*="/reel/"], a[href*="story_fbid="], a[href*="/photo/?fbid="]');
                for (let a of links) {
                    let href = a.href;
                    let clean = href.split('?')[0];
                    if (href.includes('story_fbid=') || href.includes('fbid=')) {
                        clean = href.split('&__cft__')[0].split('&__tn__')[0];
                    }
                    if (!seen.has(clean) && !clean.includes('comment_id')) {
                        seen.add(clean);
                        list.push(clean);
                        break;
                    }
                }
            });
            return list;
        }""")
        browser.close()

    new_items = []
    for purl in posts:
        pid = purl
        m = re.search(r'pfbid([A-Za-z0-9]+)', purl)
        if m: pid = m.group(0)
        else:
            m2 = re.search(r'fbid=([0-9]+)', purl)
            if m2: pid = m2.group(1)
            
        if pid in known_ids or purl in known_ids:
            break
        new_items.append({"id": pid, "url": purl, "title": ""})

    new_items.reverse()
    return new_items

# === KOORDYNATOR RADARU ===

def wczytaj_obserwowane_zrodla(filepath=SLEDZONE_FILE):
    """Wczytuje unikalne linki ze sledzone.txt ignorując komentarze i puste linie."""
    if not os.path.exists(filepath):
        return []
    sources = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line not in sources:
                sources.append(line)
    return sources

def wykonaj_cykl_radaru(db, task_queue, seen_urls_set=None, queue_lock=None):
    """Wykonuje jeden pełny przebieg sprawdzania wszystkich obserwowanych źródeł."""
    zrodla = wczytaj_obserwowane_zrodla()
    if not zrodla:
        return

    print(f"\n[RADAR] Rozpoczynam sprawdzanie {len(zrodla)} obserwowanych źródeł...")
    
    # 1. Sprawdzamy czy są jakieś zaległe zadania PENDING (np. po awarii programu)
    pending_tasks = db.get_pending_tasks()
    if pending_tasks:
        print(f"[RADAR] Wykryto {len(pending_tasks)} zaległych zadań PENDING — wznawiam kolejkowanie...")
        for pt in pending_tasks:
            t_url = pt["target_url"]
            plat = pt["platform"]
            if seen_urls_set is not None:
                if queue_lock:
                    with queue_lock: seen_urls_set.add(t_url)
                else:
                    seen_urls_set.add(t_url)
            task_queue.put(("URL", plat, t_url))
            print(f"  -> Wznowiono PENDING: [{plat}] {t_url}")

    # 2. Skanowanie poszczególnych źródeł
    for src_url in zrodla:
        platform = classify_source_type(src_url)
        if platform == "UNKNOWN":
            print(f"[RADAR] Nieznany typ platformy dla źródła: {src_url}")
            continue

        if not db.should_check(src_url, platform):
            continue

        print(f"  -> Skanowanie [{platform}]: {src_url}")
        known_ids = db.get_known_ids(src_url)
        
        try:
            new_items = []
            if platform == "YOUTUBE":
                new_items = skanuj_youtube(src_url, known_ids, limit=20)
            elif platform == "REDDIT":
                new_items = skanuj_reddit(src_url, known_ids, limit=25)
            elif platform == "INSTAGRAM":
                new_items = skanuj_instagram(src_url, known_ids, limit=15)
            elif platform == "FACEBOOK":
                new_items = skanuj_facebook(src_url, known_ids, limit=15)

            if new_items:
                print(f"     [+] Wykryto {len(new_items)} NOWYCH wpisów!")
                # Atomowa rejestracja w bazie ze statusem PENDING
                registered_tasks = db.register_pending_tasks(src_url, platform, new_items)
                
                # Dodanie do TASK_QUEUE w standardowym formacie krotki ("URL", platform, target_url)
                for t in registered_tasks:
                    target_url = t["target_url"]
                    if seen_urls_set is not None:
                        if queue_lock:
                            with queue_lock: seen_urls_set.add(target_url)
                        else:
                            seen_urls_set.add(target_url)
                    task_queue.put(("URL", platform, target_url))
                    print(f"     -> Zakolejkowano (PENDING): {target_url}")
            else:
                db.register_pending_tasks(src_url, platform, [])
                print(f"     [-] Brak nowych wpisów (wszystko aktualne).")

        except Exception as e:
            print(f"     [!] Błąd skanowania {src_url}: {e}")
            db.mark_error(src_url, platform, str(e))

        time.sleep(random.uniform(2.0, 4.0))

    print("[RADAR] Cykl sprawdzania zakończony.")

def radar_background_thread(task_queue, seen_urls_set, stop_event, queue_lock=None, radar_db=None):
    """Wątek działający w tle programu ŁOWCA."""
    db = radar_db if radar_db is not None else RadarDatabase()
    while not stop_event.is_set():
        try:
            wykonaj_cykl_radaru(db, task_queue, seen_urls_set, queue_lock)
        except Exception as e:
            print(f"[RADAR] Nieoczekiwany błąd w wątku: {e}")
            
        for _ in range(60):
            if stop_event.is_set(): break
            time.sleep(1.0)
