# lowca.py - Wersja 8.0 (Wielowątkowa Kolejka Schowka + YouTube + Facebook + Reddit Media/Wideo/Komentarze + Transkrypcja Dysku z Archiwizacją)
import requests
import os
import time
import re
import sys
import shutil
import json
import queue
import threading
from datetime import datetime
import subprocess
from yt_dlp import YoutubeDL
import pyperclip
import whisper
import torch
from radar import SLEDZONE_FILE, wczytaj_obserwowane_zrodla, radar_background_thread, wykonaj_cykl_radaru, RadarDatabase
from task_queue import TASK_QUEUE_DIR, DiskQueueAdapter, queue_task_to_disk, list_disk_tasks, remove_disk_task, clear_disk_queue

# Obsługa kodowania UTF-8 dla konsoli Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

# --- Konfiguracja Ścieżek ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_OUTPUT_DIR = SCRIPT_DIR
FFMPEG_DIR = os.path.join(SCRIPT_DIR, "ffmpeg")

# Globalne dodanie FFMPEG do PATH
if os.path.exists(FFMPEG_DIR) and FFMPEG_DIR not in os.environ.get('PATH', ''):
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get('PATH', '')

# Foldery wyjściowe i robocze
FOLDER_YT = os.path.join(BASE_OUTPUT_DIR, "youtube")
FOLDER_REDDIT = os.path.join(BASE_OUTPUT_DIR, "reddit")
FOLDER_FB = os.path.join(BASE_OUTPUT_DIR, "facebook")
FOLDER_IG = os.path.join(BASE_OUTPUT_DIR, "instagram")
FOLDER_INPUT_DISK = os.path.join(BASE_OUTPUT_DIR, "do_transkrypcji")
FOLDER_ARCHIVE_DISK = os.path.join(FOLDER_INPUT_DISK, "archiwum")
FOLDER_OUTPUT_DISK = os.path.join(BASE_OUTPUT_DIR, "dysk")

# Tworzenie kompletnej struktury folderów
for d in [FOLDER_YT, FOLDER_REDDIT, FOLDER_FB, FOLDER_IG, FOLDER_INPUT_DISK, FOLDER_ARCHIVE_DISK, FOLDER_OUTPUT_DISK]:
    os.makedirs(d, exist_ok=True)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

ALLOWED_MEDIA_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ts',
    '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.opus'
}

# Globalny cache modelu Whisper (ładowanie raz do pamięci GPU)
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()

def get_whisper_model(model_name="base"):
    global _WHISPER_MODEL
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
            print(f"[Whisper] Ładowanie modelu '{model_name}' na urządzeniu: {device} ({device_name})...")
            t0 = time.time()
            _WHISPER_MODEL = whisper.load_model(model_name, device=device)
            print(f"[Whisper] Model gotowy w {time.time() - t0:.2f}s.")
        return _WHISPER_MODEL

def wyczysc_ekran(): 
    os.system('cls' if os.name == 'nt' else 'clear')

def sanitize_for_foldername(title):
    s = title.lower().strip()
    s = re.sub(r'[\s-]+', '_', s)
    s = re.sub(r'[^\w_]', '', s)
    return s[:100] if s else "bez_tytulu"

def format_timestamp(seconds):
    """Formatuje sekundy do [MM:SS] lub [HH:MM:SS]."""
    total_sec = int(seconds)
    hours, remainder = divmod(total_sec, 3600)
    mins, secs = divmod(remainder, 60)
    if hours > 0:
        return f"[{hours:02d}:{mins:02d}:{secs:02d}]"
    return f"[{mins:02d}:{secs:02d}]"

def format_whisper_segments(result):
    """Formatuje segmenty transkrypcji Whisper ze znacznikami czasu."""
    segments = result.get("segments", [])
    if segments:
        formatted_lines = []
        for seg in segments:
            start_sec = seg.get('start', 0)
            timestamp = format_timestamp(start_sec)
            seg_text = seg.get('text', '').strip()
            if seg_text:
                formatted_lines.append(f"{timestamp} {seg_text}")
        if formatted_lines:
            return "\n".join(formatted_lines)
    
    raw_text = result.get("text", "").strip()
    if raw_text:
        return raw_text
    return "[Brak wykrytej mowy / cisza / tło dźwiękowe]"

def transkrybuj_plik_audio(audio_path, model_name="base"):
    """Wspólna deterministyczna funkcja transkrypcji audio za pomocą Whisper."""
    model = get_whisper_model(model_name)
    use_fp16 = torch.cuda.is_available()
    result = model.transcribe(audio_path, fp16=use_fp16)
    return format_whisper_segments(result), result.get("language", "nieznany")

# === MODUŁ REDDIT ===
def build_and_format_comment_tree(comments_list):
    """
    Buduje prawdziwe drzewo hierarchiczne z listy komentarzy i formatuje numerację:
    1. Autor
        1.1. Autor
            1.1.1. Autor
        1.2. Autor
    2. Autor
    """
    if not comments_list:
        return "[Brak komentarzy]"
    
    nodes = {}
    roots = []
    
    for c in comments_list:
        tid = c.get('thingid')
        nodes[tid] = {
            'author': c.get('author', '[usunięty]'),
            'body': c.get('body', '').replace('\n', ' ').strip(),
            'depth': c.get('depth', 0),
            'parentid': c.get('parentid'),
            'children': []
        }
        
    for c in comments_list:
        tid = c.get('thingid')
        pid = c.get('parentid')
        node = nodes[tid]
        if pid and pid in nodes and pid != tid:
            nodes[pid]['children'].append(node)
        else:
            roots.append(node)
            
    output_lines = []
    
    def render_node(node, numbering, level):
        prefix = ".".join(map(str, numbering))
        indent = "    " * level
        author = node['author']
        body = node['body']
        if body:
            output_lines.append(f"{indent}{prefix}. {author}: {body}\n")
        
        for idx, child in enumerate(node['children'], 1):
            child_num = numbering + [idx]
            render_node(child, child_num, level + 1)
            
    for i, root in enumerate(roots, 1):
        render_node(root, [i], 0)
        
    return "\n".join(output_lines)

def obsluz_reddita(url, max_scroll_rounds=25):
    print(f"\n[Reddit] Wykryto link: {url}")
    print("Rozpoczynam przetwarzanie...")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[BŁĄD] Brak zainstalowanej biblioteki playwright w Pythonie.")
        return False

    try:
        print("  -> Uruchamianie wbudowanej przeglądarki...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()
            
            print("  -> Ładowanie strony posta...")
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(2000)
            
            # Pętla dynamicznego rozwijania drzewa komentarzy
            print("  -> Rozwijanie drzewa komentarzy...")
            last_comment_count = 0
            stuck_rounds = 0
            
            for r in range(max_scroll_rounds):
                page.mouse.wheel(0, 8000)
                page.wait_for_timeout(800)
                
                buttons = page.locator('button[aria-label*="replies"], button[aria-label*="reply"], button:has-text("more repl"), faceplate-partial[loading="lazy"]')
                btn_cnt = buttons.count()
                if btn_cnt > 0:
                    for b_i in range(min(8, btn_cnt)):
                        try:
                            buttons.nth(b_i).click(timeout=800)
                            page.wait_for_timeout(200)
                        except Exception:
                            pass
                            
                curr_count = page.locator('shreddit-comment').count()
                if curr_count > last_comment_count:
                    print(f"     Wczytano: {curr_count} komentarzy...")
                    last_comment_count = curr_count
                    stuck_rounds = 0
                else:
                    stuck_rounds += 1
                    if stuck_rounds >= 3 and curr_count > 0:
                        break
                        
            print(f"  -> Zakończono wczytywanie. Łącznie znaleziono: {last_comment_count} komentarzy.")
            
            # Ekstrakcja danych
            extracted = page.evaluate("""() => {
                const post = document.querySelector('shreddit-post');
                const title = post ? (post.getAttribute('post-title') || document.title) : document.title;
                const author = post ? (post.getAttribute('author') || '[nieznany]') : '[nieznany]';
                const postType = post ? post.getAttribute('post-type') : '';
                
                let body = "";
                const bodyEl = document.querySelector('div[slot="text-body"]') || document.querySelector('#post-rtjson-content');
                if (bodyEl) {
                    body = bodyEl.innerText.trim();
                }
                
                // Zdjęcia
                const images = [];
                const mediaContainers = document.querySelectorAll('div[slot="post-media-container"], gallery-carousel, shreddit-media-lightbox-container');
                mediaContainers.forEach(container => {
                    const imgEls = container.querySelectorAll('img');
                    imgEls.forEach(img => {
                        const src = img.src;
                        if (src && !src.includes('avatar') && !src.includes('snoo') && !src.includes('styles.redditmedia.com') && !src.includes('redditstatic.com') && !src.includes('icon') && !src.includes('emoji')) {
                            images.push(src);
                        }
                    });
                });
                
                // Wideo
                const player = document.querySelector('shreddit-player');
                let videoUrl = null;
                if (player) {
                    const packaged = player.getAttribute('packaged-media-json');
                    if (packaged) {
                        try {
                            const pkg = JSON.parse(packaged);
                            const mp4s = pkg?.playbackMp4s?.permutations;
                            if (mp4s && mp4s.length > 0) {
                                const highest = mp4s[mp4s.length - 1];
                                videoUrl = highest?.source?.url;
                            }
                        } catch(e) {}
                    }
                    if (!videoUrl) {
                        videoUrl = player.getAttribute('src');
                    }
                }
                
                // Komentarze
                const comments = [];
                const commentEls = document.querySelectorAll('shreddit-comment');
                commentEls.forEach(c => {
                    const tid = c.getAttribute('thingid');
                    const pid = c.getAttribute('parentid');
                    const cAuthor = c.getAttribute('author') || '[usunięty]';
                    const depth = parseInt(c.getAttribute('depth') || '0', 10);
                    
                    let cBody = "";
                    const cBodyEl = c.querySelector('div[slot="comment"]') || c.querySelector('p');
                    if (cBodyEl) {
                        cBody = cBodyEl.innerText.trim();
                    }
                    if (tid && cBody) {
                        comments.push({ thingid: tid, parentid: pid, author: cAuthor, depth: depth, body: cBody });
                    }
                });
                
                return {
                    title: title,
                    author: author,
                    postType: postType,
                    body: body,
                    images: images,
                    videoUrl: videoUrl,
                    comments: comments
                };
            }""")
            
            browser.close()

        title = extracted.get('title') or "post_reddit"
        title_clean = re.sub(r'\s*:\s*r\/\w+\s*$', '', title).strip()
        author = extracted.get('author') or "[nieznany]"
        body = extracted.get('body') or ""
        images = extracted.get('images') or []
        video_url = extracted.get('videoUrl')
        comments = extracted.get('comments') or []

        final_folder_path = os.path.join(FOLDER_REDDIT, f"{datetime.now().strftime('%Y%m%d')}_{sanitize_for_foldername(title_clean)}")
        os.makedirs(final_folder_path, exist_ok=True)

        sciezka_do_tresci = os.path.join(final_folder_path, 'tresc.txt')
        with open(sciezka_do_tresci, 'w', encoding='utf-8') as f:
            f.write(f"### {title_clean} ###\n\n")
            f.write(f"Źródło: {url}\n")
            f.write(f"Autor: {author}\n")
            f.write(f"Liczba wczytanych komentarzy: {len(comments)}\n")
            f.write(f"Data pobrania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            if body:
                f.write(f"{body}\n\n")
            f.write("### HIERARCHIA KOMENTARZY ###\n\n")

            tree_text = build_and_format_comment_tree(comments)
            f.write(tree_text + "\n")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Referer': 'https://www.reddit.com/'
        }

        # Pobieranie zdjęć (z deduplikacją)
        seen_media_ids = set()
        downloaded_imgs = 0
        for img_url in images:
            m = re.search(r'([a-zA-Z0-9]{10,20})\.(?:jpeg|jpg|png)', img_url)
            media_id = m.group(1) if m else img_url
            if media_id in seen_media_ids:
                continue
            seen_media_ids.add(media_id)
            
            if 'preview.redd.it' in img_url or 'cf.preview.redd.it' in img_url:
                ext_match = re.search(r'\.(jpeg|jpg|png)', img_url)
                ext_str = ext_match.group(1) if ext_match else 'jpg'
                full_res = f"https://i.redd.it/{media_id}.{ext_str}"
            else:
                full_res = img_url
                
            try:
                r_img = requests.get(full_res, headers=headers, timeout=15)
                if r_img.status_code != 200:
                    r_img = requests.get(img_url, headers=headers, timeout=15)
                if r_img.status_code == 200:
                    downloaded_imgs += 1
                    ext = ".png" if "png" in r_img.headers.get('Content-Type', '') else ".jpg"
                    img_path = os.path.join(final_folder_path, f"obrazek_{downloaded_imgs}{ext}")
                    with open(img_path, "wb") as img_f:
                        img_f.write(r_img.content)
                    print(f"  -> Obrazek #{downloaded_imgs} zapisany.")
            except Exception as e:
                print(f"  -> Błąd pobierania obrazka: {e}")

        # Pobieranie i transkrypcja wideo (jeśli występuje)
        saved_video = False
        if video_url:
            print("  -> Pobieranie pliku wideo...")
            vid_path = os.path.join(final_folder_path, "wideo.mp4")
            try:
                r_vid = requests.get(video_url, headers=headers, stream=True, timeout=30)
                if r_vid.status_code == 200:
                    with open(vid_path, "wb") as f_v:
                        for chunk in r_vid.iter_content(chunk_size=1024*1024):
                            if chunk: f_v.write(chunk)
                    saved_video = True
                    print(f"  -> Zapisano wideo ({os.path.getsize(vid_path) / 1024:.1f} KB).")
                else:
                    ydl_opts = {
                        'outtmpl': os.path.join(final_folder_path, 'wideo.%(ext)s'),
                        'quiet': True
                    }
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    saved_video = True
                    print("  -> Pobrano wideo za pomocą yt-dlp.")
            except Exception as e:
                print(f"  -> Błąd pobierania wideo: {e}")

            # Transkrypcja audio z wideo (jeśli istnieje)
            if saved_video and os.path.exists(vid_path):
                temp_audio = os.path.join(final_folder_path, "temp_video_audio.mp3")
                ffmpeg_bin = os.path.join(FFMPEG_DIR, "ffmpeg.exe") if os.path.exists(os.path.join(FFMPEG_DIR, "ffmpeg.exe")) else "ffmpeg"
                cmd = [ffmpeg_bin, "-y", "-i", vid_path, "-vn", "-acodec", "libmp3lame", temp_audio]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0 and os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000:
                        print("  -> Transkrypcja ścieżki dźwiękowej wideo za pomocą Whisper...")
                        trans_text, lang = transkrybuj_plik_audio(temp_audio)
                        with open(os.path.join(final_folder_path, "transkrypcja_wideo.txt"), "w", encoding="utf-8") as f_tr:
                            f_tr.write(f"### TRANSKRYPCJA WIDEO ###\nJęzyk: {lang}\n\n{trans_text}\n")
                        print("  -> Zapisano transkrypcję wideo.")
                except Exception as e_tr:
                    print(f"  [Ostrzeżenie] Nie udało się przetranskrybować wideo: {e_tr}")
                finally:
                    if os.path.exists(temp_audio):
                        try: os.remove(temp_audio)
                        except Exception: pass

        print(f"\n[SUKCES] Dane z Reddita ({len(comments)} komentarzy, {downloaded_imgs} zdjęć) zostały zapisane w:\n   {os.path.abspath(final_folder_path)}")
        return True

    except Exception as e:
        print(f"[BŁĄD] Przetwarzanie linku z Reddita nie powiodło się: {e}")
        return False

# === MODUŁ YOUTUBE ===
def obsluz_youtube(url):
    print(f"\n[YouTube] Wykryto link: {url}")
    print("Rozpoczynam przetwarzanie...")
    
    cookies_path = os.path.join(SCRIPT_DIR, 'cookies.txt')
    use_cookies = os.path.exists(cookies_path)
    
    temp_folder = os.path.join(FOLDER_YT, f"_temp_audio_{int(time.time()*1000)}")
    os.makedirs(temp_folder, exist_ok=True)
    temp_audio_path = os.path.join(temp_folder, 'temp_audio.mp3')
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_folder, 'temp_audio.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': FFMPEG_DIR if os.path.exists(FFMPEG_DIR) else None,
        'quiet': True,
        'no_warnings': True,
    }
    
    if use_cookies:
        ydl_opts['cookiefile'] = cookies_path

    try:
        print("  -> Pobieranie audio i metadanych z YouTube...")
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'film_youtube')
            channel_name = info.get('uploader', 'Nieznany twórca')
            upload_date = info.get('upload_date', 'Nieznana data')
            duration = info.get('duration_string', 'Nieznany')
            description = info.get('description', '')

        # Transkrypcja za pomocą Whisper
        print("  -> Transkrypcja Whisper...")
        transcription_content, lang = transkrybuj_plik_audio(temp_audio_path)

        # Folder docelowy
        final_folder_path = os.path.join(FOLDER_YT, f"{datetime.now().strftime('%Y%m%d')}_{sanitize_for_foldername(video_title)}")
        os.makedirs(final_folder_path, exist_ok=True)

        sciezka_do_transkrypcji = os.path.join(final_folder_path, 'transkrypcja.txt')
        sciezka_do_info = os.path.join(final_folder_path, 'info.txt')

        with open(sciezka_do_transkrypcji, 'w', encoding='utf-8') as f:
            f.write(transcription_content)

        with open(sciezka_do_info, 'w', encoding='utf-8') as f:
            f.write(f"Tytuł: {video_title}\nKanał: {channel_name}\nData publikacji: {upload_date}\nCzas trwania: {duration}\nJęzyk: {lang}\nŹródło: {url}\n\nOpis:\n{description}")

        print(f"[SUKCES] Dane z YouTube zostały zapisane w:\n   {os.path.abspath(final_folder_path)}")
        return True

    except Exception as e:
        print(f"[BŁĄD] Przetwarzanie linku z YouTube nie powiodło się: {e}")
        return False
    finally:
        if os.path.exists(temp_folder):
            try:
                shutil.rmtree(temp_folder)
            except Exception:
                pass

# === MODUŁ FACEBOOK ===
def obsluz_facebook(url):
    print(f"\n[Facebook] Wykryto link: {url}")
    print("Rozpoczynam przetwarzanie...")
    
    use_cookies = os.path.exists(os.path.join(SCRIPT_DIR, "cookies.txt"))
    cookie_path = os.path.join(SCRIPT_DIR, "cookies.txt")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[BŁĄD] Brak zainstalowanej biblioteki playwright w Pythonie.")
        return False

    try:
        print("  -> Uruchamianie wbudowanej przeglądarki...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 1000}
            )
            if use_cookies:
                fb_cookies = []
                with open(cookie_path, 'r', encoding='utf-8', errors='ignore') as f:
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
                            fb_cookies.append(c_dict)
                if fb_cookies:
                    context.add_cookies(fb_cookies)
                
            page = context.new_page()
            print("  -> Ładowanie strony posta...")
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(3500)
            
            # 1. Zamykamy banery cookies oraz okienka
            try:
                page.evaluate("""() => {
                    const els = Array.from(document.querySelectorAll('div[role="button"], button, span'));
                    for (const el of els) {
                        const t = (el.innerText || '').toLowerCase();
                        const a = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (t.includes('zezwól na wszystkie pliki cookie') || a.includes('zezwól na wszystkie pliki cookie') || t === 'zezwól na wszystkie pliki cookie') {
                            el.click();
                            break;
                        }
                    }
                    document.querySelectorAll('div[aria-label*="Zamknij czat"], div[aria-label*="Close chat"]').forEach(b => b.click());
                }""")
                page.wait_for_timeout(1500)
            except Exception:
                pass

            # 2. Przełączanie filtra z "Najtrafniejsze" na "Wszystkie komentarze" (All comments)
            try:
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('div[role="button"], span[role="button"], div[aria-haspopup="menu"]'));
                    for (const b of btns) {
                        const t = (b.innerText || '').toLowerCase().trim();
                        if (t.includes('najtrafniejsze') || t.includes('most relevant') || t.includes('najistotniejsze')) {
                            b.click();
                            break;
                        }
                    }
                }""")
                page.wait_for_timeout(1200)
                page.evaluate("""() => {
                    const items = Array.from(document.querySelectorAll('div[role="menuitem"], div[role="button"], span, div[tabindex="0"]'));
                    for (const it of items) {
                        const t = (it.innerText || '').toLowerCase().trim();
                        if (t === 'wszystkie komentarze' || t === 'all comments' || t.startsWith('wszystkie komentarze') || t.startsWith('all comments')) {
                            it.click();
                            break;
                        }
                    }
                }""")
                page.wait_for_timeout(2000)
            except Exception:
                pass

            # 2b. Rozwijanie pełnej treści posta ("Zobacz więcej" / "See more")
            print("  -> Rozwijanie pełnej treści posta (Zobacz więcej / See more)...")
            for _ in range(15):
                clicked = False
                try:
                    clicked = page.evaluate("""() => {
                        const isCommentLike = (s) => /(komentarz|comment|odpowied|repl|poprzedni|previous)/.test(s);
                        const isSeeMore = (s) => /(zobacz więcej|zobacz wiecej|wyświetl więcej|wyswietl wiecej|see more|view more|read more|czytaj więcej|czytaj wiecej|zobacz całość|zobacz calosc|zobacz pelna tresc|zobacz pełną treść|więcej|wiecej|more)/.test(s);
                        const cands = Array.from(document.querySelectorAll('div[role="button"], span[role="button"], div[tabindex="0"], span[tabindex="0"], button'));
                        for (const el of cands) {
                            const t = (el.innerText || '').toLowerCase();
                            if (t && isSeeMore(t) && !isCommentLike(t)) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }""")
                except Exception:
                    clicked = False
                if not clicked:
                    break
                page.wait_for_timeout(600)

            # 3. Pętla rozwijania "Wyświetl więcej komentarzy" oraz "Wyświetl odpowiedzi"
            print("  -> Rozwijanie pełnej listy komentarzy i odpowiedzi...")
            last_cnt = 0
            stuck_cnt = 0
            for round_i in range(50):
                page.evaluate("""() => {
                    document.querySelectorAll('div[role="button"], span[role="button"]').forEach(btn => {
                        const txt = (btn.innerText || '').toLowerCase().trim();
                        if (txt.includes('wyświetl więcej komentarzy') || 
                            txt.includes('zobacz więcej komentarzy') || 
                            txt.includes('view more comments') ||
                            txt.includes('poprzednie komentarze') ||
                            txt.includes('zobacz kolejne komentarze') ||
                            txt.includes('wyświetl kolejne komentarze') ||
                            txt.includes('zobacz więcej') ||
                            txt.includes('więcej odpowiedzi') ||
                            txt.includes('kolejne odpowiedzi') ||
                            ((txt.includes('odpowied') || txt.includes('repl')) && !txt.startsWith('odpowiedz') && !txt.startsWith('reply'))) {
                            try { btn.click(); } catch(e) {}
                        }
                    });
                    const dialog = document.querySelector('div[role="dialog"]');
                    if (dialog) dialog.scrollTop = dialog.scrollHeight;
                    window.scrollBy(0, 3000);
                }""")
                page.mouse.wheel(0, 3500)
                page.wait_for_timeout(600)
                
                curr_cnt = page.locator('div[role="article"]').count()
                if curr_cnt != last_cnt:
                    last_cnt = curr_cnt
                    stuck_cnt = 0
                else:
                    stuck_cnt += 1
                    if stuck_cnt >= 10 and curr_cnt > 30:
                        break

            # Pobranie danych ze strony
            data = page.evaluate("""() => {
                // Główny kontener posta: modal / feed unit / main.
                const scopedContainer =
                    document.querySelector('div[role="dialog"]') ||
                    document.querySelector('div[data-pagelet*="Story"]') ||
                    document.querySelector('div[data-pagelet*="FeedUnit_0"]') ||
                    document.querySelector('div[role="main"]') ||
                    document.body;

                // Element jest komentarzem/odpowiedzią, a nie treścią głównego posta.
                const isInsideComment = (el) => !!(el.closest('div[role="article"]') || el.closest('ul[role="group"]'));
                const isInsideChatOrDock = (el) => !!(el.closest('div[data-pagelet*="ChatTab"]') || el.closest('div[data-pagelet*="Dock"]') || el.closest('div[role="region"]'));

                const cleanPostText = (s) => {
                    let t = (s || '').trim();
                    // Usuń znaki zero-width / kierunkowe, którymi Facebook zaciemnia tekst.
                    t = t.replace(/[\\u200B-\\u200F\\u202A-\\u202E\\u2060-\\u2064\\uFEFF\\u00AD\\u034F]/g, '');
                    t = t.replace(/\\s*…\\s*(wyświetl więcej|wyswietl wiecej|zobacz więcej|zobacz wiecej|więcej|wiecej|see more|view more|read more|more)\\s*\\.?\\s*$/i, '');
                    t = t.replace(/\\s*\\.\\.\\.\\s*(więcej|wiecej|more)\\s*$/i, '');
                    t = t.replace(/\\s*(wyświetl mniej|wyswietl mniej|pokaż mniej|pokaz mniej|see less|… mniej|\\.\\.\\. mniej)\\s*$/i, '');
                    const lines = t.split('\\n').map(x => x.trim()).filter(x => x.length > 0);
                    const keep = [];
                    for (const ln of lines) {
                        if (/^(must follow|obserwuj|follow)\\b/i.test(ln)) break;
                        if (/^more information$/i.test(ln)) continue;
                        keep.push(ln);
                    }
                    return keep.join('\\n').trim();
                };

                const isObfuscatedName = (s) => {
                    const clean = s.split(String.fromCharCode(10)).join(' ').split(String.fromCharCode(13)).join(' ');
                    const parts = clean.split(' ').map(x => x.trim()).filter(x => x.length > 0);
                    return parts.length > 6 && parts.every(x => x.length <= 3);
                };

                const isNoiseText = (s) => {
                    if (!s) return true;
                    if (/^(post|facebook)$/i.test(s.trim())) return true;
                    if (s.includes('Komentarze') || s.includes('Udostępnij') || s.includes('Polub') ||
                        s.includes('O czym myślisz') || s.includes('Utwórz post') ||
                        s.includes('Najtrafniejsze') || s.includes('Napisz komentarz') ||
                        s.includes('Odpowiedz') || s.includes('Edytowano') || s.includes('od autora')) return true;
                    // Odrzucamy nagłówek techniczny z powtarzającym się słowem "Facebook".
                    const words = s.split(/\\s+/).filter(Boolean);
                    const fbCount = words.filter(w => /^facebook$/i.test(w)).length;
                    if (fbCount > 5) return true;
                    return false;
                };

                // 1) Treść posta: najdłuższy sensowny fragment [dir=auto] spoza komentarzy,
                //    w obrębie GŁÓWNEGO kontenera (modal). To rozwiązuje problem brania
                //    treści innego posta z feedu obok.
                let postText = "";
                if (scopedContainer) {
                    const candidates = scopedContainer.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                    candidates.forEach(m => {
                        if (isInsideComment(m) || isInsideChatOrDock(m)) return;
                        const t = cleanPostText(m.innerText);
                        if (isNoiseText(t) || isObfuscatedName(t) || t.length < 40) return;
                        if (t.length > postText.length) postText = t;
                    });
                }

                // 2) Fallback: meta og:description (czysty opis posta).
                if (!postText) {
                    postText = cleanPostText(document.querySelector('meta[property="og:description"]')?.content || "");
                    if (postText && postText.length < 20) postText = "";
                }

                // 3) Fallback: elementy spoza artykułów (stary mechanizm).
                if (!postText) {
                    const msgs = document.querySelectorAll(
                        'div[data-ad-preview="message"], div[data-ad-comet-preview="message"], ' +
                        'div[data-ad-rendering-role="story_message"], div[data-nt="FB:TEXT4"], ' +
                        'div[data-pagelet*="Stories"] div[dir="auto"], div[data-pagelet*="stories"] div[dir="auto"], ' +
                        'div[role="main"] div[dir="auto"], div[dir="auto"], span[dir="auto"]'
                    );
                    msgs.forEach(m => {
                        if (isInsideComment(m) || isInsideChatOrDock(m)) return;
                        const t = cleanPostText(m.innerText);
                        if (isNoiseText(t) || isObfuscatedName(t) || t.length < 40) return;
                        if (t.length > postText.length) postText = t;
                    });
                }

                // Autor posta: szukamy wyłącznie w głównym kontenerze, poza komentarzami.
                let author = "";
                const h_tags = scopedContainer.querySelectorAll('h2, h3, a > strong, span[dir="auto"] > strong, a[role="link"] strong');
                for (let h of h_tags) {
                    if (isInsideComment(h) || isInsideChatOrDock(h)) continue;
                    const t = cleanPostText(h.innerText);
                    if (t && t.length > 2 && t.length < 50 &&
                        !t.includes('Facebook') && !t.includes('Komentarze') && !t.includes('Udostępnij') &&
                        !t.includes('Menu') && !t.includes('Post') && !t.includes('Zaloguj') &&
                        !t.includes('Utwórz post') && !t.includes('Brak historii') && !t.includes('od autora')) {
                        author = t;
                        break;
                    }
                }
                if (!author) author = "Facebook";

                // Zdjęcia dołączone do posta
                const postImages = [];
                const seenUrls = new Set();
                const ogImg = document.querySelector('meta[property="og:image"]')?.content;
                if (ogImg && !ogImg.includes('cookie') && !ogImg.includes('rsrc.php')) {
                    seenUrls.add(ogImg.split('?')[0]);
                    postImages.push(ogImg);
                }
                document.querySelectorAll('img').forEach(img => {
                    if (!img.closest('div[role="article"]') && !img.closest('div[data-pagelet*="ChatTab"]') && !img.closest('div[data-pagelet*="Dock"]') && !img.closest('div[role="region"]')) {
                        const src = img.src;
                        if (src && !src.startsWith('data:') && !src.includes('rsrc.php') && !src.includes('emoji') && !src.includes('p50x50') && !src.includes('p100x100') && !src.includes('p200x200') && !src.includes('cookie') && !src.includes('hsts-pixel')) {
                            const w = img.naturalWidth || img.width || 0;
                            const h = img.naturalHeight || img.height || 0;
                            const alt = img.getAttribute('alt') || '';
                            if (w > 300 || h > 300 || (alt.length > 20 && !alt.toLowerCase().includes('profilow'))) {
                                const clean = src.split('?')[0];
                                if (!seenUrls.has(clean)) {
                                    seenUrls.add(clean);
                                    postImages.push(src);
                                }
                            }
                        }
                    }
                });

                // Sprawdzenie czy w samym poście jest wideo
                const hasVideo = (document.querySelector('video') !== null) && (window.location.href.includes('/reel/') || window.location.href.includes('/videos/') || window.location.href.includes('/watch') || window.location.href.includes('/share/v/'));

                // Komentarze
                const comments = [];
                const seenSigs = new Set();
                
                const commentArticles = document.querySelectorAll('div[role="article"]');
                commentArticles.forEach(art => {
                    // Ignoruj okienka czatu Messenger i wiadomości prywatnych
                    if (art.closest('div[data-pagelet*="ChatTab"]') || art.closest('div[aria-label*="Czat"]') || art.closest('div[role="region"]') || art.closest('div[data-pagelet*="Dock"]')) {
                        return;
                    }

                    let cAuthor = "";
                    const links = art.querySelectorAll('a[role="link"], a[attributionsrc], a');
                    for (let l of links) {
                        const txt = l.innerText.trim();
                        if (txt && txt.length > 1 && !txt.includes('Odpowiedz') && !txt.includes('Udostępnij') && !txt.includes('Lubię to') && !txt.includes('dni') && !txt.includes('godz') && !txt.includes('min') && !txt.includes('tydz') && !txt.includes('od autora') && !txt.includes('Edytowano')) {
                            cAuthor = txt;
                            break;
                        }
                    }
                    if (!cAuthor) cAuthor = "Użytkownik";

                    let cText = "";
                    const textEls = art.querySelectorAll('div[dir="auto"][lang], div[dir="auto"], span[dir="auto"]');
                    textEls.forEach(te => {
                        const t = te.innerText.trim();
                        if (t && t.length > cText.length && t !== cAuthor && !t.includes('Odpowiedz') && !t.includes('Udostępnij') && !t.includes('Lubię to') && !t.includes('Edytowano') && !t.includes('od autora')) {
                            cText = t;
                        }
                    });

                    const sticker = art.querySelector('img[src*="fbcdn.net"], img[src*="giphy"]');
                    if (!cText && sticker && (sticker.src.includes('stickers') || sticker.src.includes('images'))) {
                        cText = "[Naklejka / Obrazek]";
                    }

                    if (cText) {
                        const sig = `${cAuthor}:::${cText}`;
                        if (!seenSigs.has(sig)) {
                            seenSigs.add(sig);
                            const isReply = art.closest('ul ul') !== null || art.parentElement.closest('div[role="article"]') !== null || art.closest('div[role="group"]') !== null;
                            comments.push({ author: cAuthor, text: cText, isReply: isReply });
                        }
                    }
                });

                return {
                    author: author,
                    postText: postText,
                    postImages: postImages,
                    hasVideo: hasVideo,
                    comments: comments,
                    pageTitle: document.title
                };
            }""")
            browser.close()

        author = data.get('author') or "Facebook"
        post_text = data.get('postText') or ""
        images = data.get('postImages') or []
        comments = data.get('comments') or []
        is_video_post = data.get('hasVideo', False) or "/reel/" in url.lower() or "/videos/" in url.lower() or "/watch" in url.lower() or "/share/v/" in url.lower()
        page_title = data.get('pageTitle') or "post_facebook"

        title_snippet = post_text.split('\n')[0][:60] if post_text else page_title[:60]
        folder_name = f"{datetime.now().strftime('%Y%m%d')}_{sanitize_for_foldername(title_snippet if title_snippet else author)}"
        final_folder = os.path.join(FOLDER_FB, folder_name)
        os.makedirs(final_folder, exist_ok=True)

        # Inteligentne budowanie drzewa komentarzy i odpowiedzi
        tree_lines = []
        main_index = 0
        reply_index = 0
        top_level_authors = []
        
        for c in comments:
            c_auth = c.get('author', 'Użytkownik')
            c_text = c.get('text', '').replace('\n', ' ').strip()
            
            # Sprawdzenie czy komentarz odwołuje się do poprzedniego autora (odpowiedź)
            matched_parent = False
            for prev_auth in top_level_authors:
                if c_text.startswith(prev_auth) or f"@{prev_auth}" in c_text:
                    matched_parent = True
                    break
                    
            if c.get('isReply', False) or matched_parent:
                reply_index += 1
                tree_lines.append(f"    {max(1, main_index)}.{reply_index}. {c_auth}: {c_text}")
            else:
                main_index += 1
                reply_index = 0
                top_level_authors.append(c_auth)
                tree_lines.append(f"{main_index}. {c_auth}: {c_text}")

        # Zapis tresc.txt
        tresc_path = os.path.join(final_folder, "tresc.txt")
        with open(tresc_path, "w", encoding="utf-8") as f:
            f.write(f"### POST FACEBOOK ###\n\n")
            f.write(f"Źródło: {url}\n")
            f.write(f"Autor: {author}\n")
            f.write(f"Data pobrania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Liczba unikalnych komentarzy: {len(comments)}\n\n")
            if post_text:
                f.write(f"--- TREŚĆ POSTA ---\n{post_text}\n\n")
            f.write("--- KOMENTARZE I ODPOWIEDZI ---\n\n")
            if tree_lines:
                f.write("\n\n".join(tree_lines) + "\n")
            else:
                f.write("[Brak komentarzy lub post nie zawiera komentarzy]\n")

        # Pobieranie tylko właściwych zdjęć posta
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Referer': 'https://www.facebook.com/'
        }
        seen_imgs = set()
        img_count = 0
        for img_url in images:
            clean_url = img_url.split('?')[0]
            if clean_url in seen_imgs:
                continue
            seen_imgs.add(clean_url)
            try:
                r = requests.get(img_url, headers=headers, timeout=15)
                if r.status_code == 200:
                    img_count += 1
                    ext = ".png" if "png" in r.headers.get('Content-Type', '') else ".jpg"
                    img_path = os.path.join(final_folder, f"obrazek_{img_count}{ext}")
                    with open(img_path, "wb") as f_img:
                        f_img.write(r.content)
                    print(f"  -> Obrazek #{img_count} zapisany.")
            except Exception as e:
                print(f"  -> Błąd pobierania obrazka: {e}")

        # Pobieranie wideo TYLKO gdy to faktycznie post wideo / rolka
        if is_video_post:
            print("  -> Wykryto wideo/rolkę Facebooka, pobieranie wideo...")
            temp_audio = os.path.join(final_folder, "temp_fb_audio.mp3")
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(final_folder, 'wideo.%(ext)s'),
                'ffmpeg_location': FFMPEG_DIR if os.path.exists(FFMPEG_DIR) else None,
                'quiet': True,
                'no_warnings': True,
            }
            if use_cookies:
                ydl_opts['cookiefile'] = cookie_path

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                print("  -> Plik wideo zapisany.")
                
                vid_files = [os.path.join(final_folder, f) for f in os.listdir(final_folder) if f.startswith('wideo.') and not f.endswith('.txt')]
                if vid_files:
                    vid_file = vid_files[0]
                    ffmpeg_bin = os.path.join(FFMPEG_DIR, "ffmpeg.exe") if os.path.exists(os.path.join(FFMPEG_DIR, "ffmpeg.exe")) else "ffmpeg"
                    cmd = [ffmpeg_bin, "-y", "-i", vid_file, "-vn", "-acodec", "libmp3lame", temp_audio]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0 and os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000:
                        print("  -> Transkrypcja mowy z filmu Whisperem...")
                        trans_text, lang = transkrybuj_plik_audio(temp_audio)
                        with open(os.path.join(final_folder, "transkrypcja.txt"), "w", encoding="utf-8") as f_tr:
                            f_tr.write(f"### TRANSKRYPCJA AUDIO ###\nJęzyk: {lang}\n\n{trans_text}\n")
                        print("  -> Zapisano transkrypcję audio.")
            except Exception as e_vid:
                print(f"  -> Informacja o wideo: {e_vid}")
            finally:
                if os.path.exists(temp_audio):
                    try: os.remove(temp_audio)
                    except Exception: pass

        with open(os.path.join(final_folder, "info.txt"), "w", encoding="utf-8") as f_inf:
            f_inf.write(f"Tytuł/Opis: {title_snippet}\nAutor: {author}\nŹródło: {url}\nData: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nKomentarze: {len(comments)}\nZdjęcia: {img_count}\n")

        print(f"\n[SUKCES] Dane z Facebooka ({len(comments)} komentarzy, {img_count} zdjęć) zapisane w:\n   {os.path.abspath(final_folder)}")
        return True

    except Exception as e:
        print(f"[BŁĄD] Przetwarzanie linku z Facebooka nie powiodło się: {e}")
        return False

# === MODUŁ INSTAGRAM ===
def extract_instagram_from_page(html, page_url):
    """Ekstrahuje metadane, slajdy karuzeli oraz komentarze z HTML / stanu JSON Instagrama."""
    soup = BeautifulSoup(html, "html.parser")
    
    author = "Instagram_User"
    caption = ""
    og_title = ""
    
    for meta in soup.find_all("meta"):
        p = meta.get("property") or meta.get("name") or ""
        c = meta.get("content") or ""
        if p == "og:title":
            og_title = c
            if " on Instagram: " in c:
                author = c.split(" on Instagram: ")[0].strip()
                caption = c.split(" on Instagram: ", 1)[1].strip().strip('"')
            elif "• Instagram" in c:
                author = c.split("•")[0].strip()
        elif p == "og:description" and not caption:
            if ' - ' in c and ': "' in c:
                parts = c.split(': "', 1)
                caption = parts[1].rstrip('"')
                
    if not author or author == "Instagram_User":
        tw_title = soup.find("meta", attrs={"name": "twitter:title"})
        if tw_title and tw_title.get("content"):
            author = tw_title.get("content").split("•")[0].strip()

    carousel_images = []
    scripts = soup.find_all("script", type="application/json")
    
    def walk_media(obj):
        if isinstance(obj, dict):
            if "carousel_media" in obj and isinstance(obj["carousel_media"], list):
                for slide in obj["carousel_media"]:
                    cands = slide.get("image_versions2", {}).get("candidates", [])
                    if cands and cands[0].get("url"):
                        carousel_images.append(cands[0].get("url"))
            elif "image_versions2" in obj and "candidates" in obj["image_versions2"]:
                cands = obj["image_versions2"]["candidates"]
                if cands and cands[0].get("url") and not carousel_images:
                    carousel_images.append(cands[0].get("url"))
            for v in obj.values():
                walk_media(v)
        elif isinstance(obj, list):
            for it in obj:
                walk_media(it)

    for s in scripts:
        if not s.string: continue
        if "carousel_media" in s.string or "image_versions2" in s.string:
            try:
                d = json.loads(s.string)
                walk_media(d)
                if carousel_images:
                    break
            except Exception:
                pass

    comments = []
    seen_comments = set()
    
    def walk_comments(obj):
        if isinstance(obj, dict):
            if "text" in obj and ("user" in obj or "owner" in obj or "from" in obj):
                user_obj = obj.get("user") or obj.get("owner") or obj.get("from") or {}
                username = user_obj.get("username") if isinstance(user_obj, dict) else str(user_obj)
                text = obj.get("text", "")
                if username and text and username not in ["Instagram", "Meta"]:
                    sig = f"{username}:::{text}"
                    if sig not in seen_comments and len(comments) < 200:
                        seen_comments.add(sig)
                        children = []
                        for ch in obj.get("preview_child_comments", []):
                            cu = ch.get("user", {}).get("username") or ch.get("owner", {}).get("username")
                            ct = ch.get("text")
                            if cu and ct:
                                children.append((cu, ct))
                        comments.append({
                            "user": username,
                            "text": text,
                            "children": children
                        })
            for v in obj.values():
                walk_comments(v)
        elif isinstance(obj, list):
            for it in obj:
                walk_comments(it)

    for s in scripts:
        if not s.string: continue
        try:
            d = json.loads(s.string)
            walk_comments(d)
        except Exception:
            pass

    return {
        "author": author,
        "caption": caption,
        "og_title": og_title,
        "carousel_images": carousel_images,
        "comments": comments
    }

def obsluz_instagram(url):
    """Pobiera posty, karuzele zdjęć, rolki i komentarze z Instagrama."""
    print(f"\n[Instagram] Wykryto link: {url}")
    print("Rozpoczynam przetwarzanie...")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[BŁĄD] Brak zainstalowanej biblioteki playwright.")
        return False

    is_video_post = "/reel/" in url or "/reels/" in url or "/tv/" in url

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 1000}
            )
            page = context.new_page()
            print("  -> Ładowanie strony Instagram...")
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(3500)
            
            # 1. Zamykanie banera cookies
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('button').forEach(b => {
                        const t = b.innerText.toLowerCase();
                        if (t.includes('allow') || t.includes('decline') || t.includes('zezwól') || t.includes('odrzuć')) b.click();
                    });
                }""")
                page.wait_for_timeout(1000)
            except Exception:
                pass

            # 2. Zamykanie okienka logowania [X]
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('div[role="dialog"] svg, div[role="dialog"] button').forEach(el => {
                        const label = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (label.includes('close') || label.includes('zamknij')) {
                            el.closest('button')?.click();
                        }
                    });
                }""")
                page.wait_for_timeout(1000)
            except Exception:
                pass

            # 3. Rozwijanie komentarzy i odpowiedzi (do 200)
            print("  -> Rozwijanie komentarzy i odpowiedzi (limit do 200)...")
            for _ in range(8):
                page.evaluate("""() => {
                    document.querySelectorAll('button, span, div[role="button"]').forEach(el => {
                        const txt = el.innerText.toLowerCase().trim();
                        if (txt.includes('odpowiedzi') || txt.includes('replies') || txt.includes('wczytaj') || txt.includes('załaduj') || txt.includes('load more')) {
                            el.click();
                        }
                    });
                }""")
                page.wait_for_timeout(600)

            html = page.content()
            browser.close()

        # Wyciągamy dane z HTML i stanu
        parsed = extract_instagram_from_page(html, url)
        author = parsed['author']
        caption = parsed['caption']
        comments = parsed['comments']
        carousel_images = parsed['carousel_images']
        
        title_snippet = caption.split('\n')[0][:60] if caption else author
        folder_name = f"{datetime.now().strftime('%Y%m%d')}_{sanitize_for_foldername(title_snippet)}"
        final_folder = os.path.join(FOLDER_IG, folder_name)
        os.makedirs(final_folder, exist_ok=True)

        # Budowanie drzewa komentarzy
        tree_lines = []
        main_idx = 0
        for c in comments:
            main_idx += 1
            tree_lines.append(f"{main_idx}. {c['user']}: {c['text']}")
            for reply_idx, (chu, cht) in enumerate(c.get('children', []), 1):
                tree_lines.append(f"    {main_idx}.{reply_idx}. {chu}: {cht}")

        # Zapis tresc.txt
        tresc_path = os.path.join(final_folder, "tresc.txt")
        with open(tresc_path, "w", encoding="utf-8") as f:
            f.write(f"### POST INSTAGRAM ###\n\n")
            f.write(f"Źródło: {url}\n")
            f.write(f"Autor: {author}\n")
            f.write(f"Data pobrania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Liczba komentarzy: {len(comments)}\n\n")
            if caption:
                f.write(f"--- OPIS POSTA ---\n{caption}\n\n")
            f.write("--- KOMENTARZE I ODPOWIEDZI ---\n\n")
            if tree_lines:
                f.write("\n\n".join(tree_lines) + "\n")
            else:
                f.write("[Brak komentarzy lub post nie zawiera komentarzy]\n")

        # Pobieranie zdjęć / karuzeli
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Referer': 'https://www.instagram.com/'
        }
        img_count = 0
        for img_url in carousel_images:
            try:
                r = requests.get(img_url, headers=headers, timeout=15)
                if r.status_code == 200:
                    img_count += 1
                    img_path = os.path.join(final_folder, f"obrazek_{img_count}.jpg")
                    with open(img_path, "wb") as f_img:
                        f_img.write(r.content)
                    print(f"  -> Obrazek #{img_count} zapisany.")
            except Exception as e:
                print(f"  -> Błąd pobierania obrazka: {e}")

        # Pobieranie wideo jeśli to film / rolka
        if is_video_post:
            print("  -> Pobieranie pliku wideo w jakości HD...")
            temp_audio = os.path.join(final_folder, "temp_ig_audio.mp3")
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(final_folder, 'wideo.%(ext)s'),
                'ffmpeg_location': FFMPEG_DIR if os.path.exists(FFMPEG_DIR) else None,
                'quiet': True,
                'no_warnings': True,
            }
            if os.path.exists(os.path.join(SCRIPT_DIR, 'cookies.txt')):
                ydl_opts['cookiefile'] = os.path.join(SCRIPT_DIR, 'cookies.txt')

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                print("  -> Plik wideo zapisany.")
                
                vid_files = [os.path.join(final_folder, f) for f in os.listdir(final_folder) if f.startswith('wideo.') and not f.endswith('.txt')]
                if vid_files:
                    vid_file = vid_files[0]
                    ffmpeg_bin = os.path.join(FFMPEG_DIR, "ffmpeg.exe") if os.path.exists(os.path.join(FFMPEG_DIR, "ffmpeg.exe")) else "ffmpeg"
                    cmd = [ffmpeg_bin, "-y", "-i", vid_file, "-vn", "-acodec", "libmp3lame", temp_audio]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0 and os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000:
                        print("  -> Transkrypcja mowy z filmu Whisperem...")
                        trans_text, lang = transkrybuj_plik_audio(temp_audio)
                        with open(os.path.join(final_folder, "transkrypcja.txt"), "w", encoding="utf-8") as f_tr:
                            f_tr.write(f"### TRANSKRYPCJA AUDIO ###\nJęzyk: {lang}\n\n{trans_text}\n")
                        print("  -> Zapisano transkrypcję audio.")
            except Exception as e_vid:
                print(f"  -> Informacja o wideo: {e_vid}")
            finally:
                if os.path.exists(temp_audio):
                    try: os.remove(temp_audio)
                    except Exception: pass

        with open(os.path.join(final_folder, "info.txt"), "w", encoding="utf-8") as f_inf:
            f_inf.write(f"Tytuł/Opis: {title_snippet}\nAutor: {author}\nŹródło: {url}\nData: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nKomentarze: {len(comments)}\nZdjęcia: {img_count}\n")

        print(f"\n[SUKCES] Dane z Instagrama ({len(comments)} komentarzy, {img_count} zdjęć) zapisane w:\n   {os.path.abspath(final_folder)}")
        return True

    except Exception as e:
        print(f"[BŁĄD] Przetwarzanie linku z Instagrama nie powiodło się: {e}")
        return False

# === MODUŁ PLIKÓW LOKALNYCH (DYSK) ===
def is_file_ready(filepath, check_interval=1.0):
    """Sprawdza, czy plik przestał rosnąć (zakończono jego kopiowanie)."""
    try:
        size1 = os.path.getsize(filepath)
        time.sleep(check_interval)
        size2 = os.path.getsize(filepath)
        return size1 == size2 and size1 > 0
    except Exception:
        return False

def bezpieczne_przeniesienie_do_archiwum(source_path, archive_dir):
    """Przenosi plik do folderu archiwum, rozwiązując ewentualne kolizje nazw."""
    os.makedirs(archive_dir, exist_ok=True)
    base_name = os.path.basename(source_path)
    dest_path = os.path.join(archive_dir, base_name)
    
    if os.path.exists(dest_path):
        name_part, ext_part = os.path.splitext(base_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = os.path.join(archive_dir, f"{name_part}_{timestamp}{ext_part}")
    
    shutil.move(source_path, dest_path)
    return dest_path

def obsluz_plik_lokalny(filepath):
    """Transkrybuje plik lokalny z dysku, zapisuje transkrypcję do 'dysk/' i archiwizuje plik."""
    if not os.path.exists(filepath):
        print(f"[BŁĄD] Plik nie istnieje: {filepath}")
        return False

    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        print(f"[OSTRZEŻENIE] Pomijam plik o nieobsługiwanym rozszerzeniu: {filename}")
        return False

    if not is_file_ready(filepath):
        print(f"[Czekam] Plik {filename} jest jeszcze kopiowany lub zablokowany...")
        return False

    print(f"\n[Dysk] Rozpoczynam transkrypcję lokalnego pliku: {filename}")
    filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  -> Rozmiar pliku: {filesize_mb:.2f} MB")
    
    clean_name = os.path.splitext(filename)[0]
    final_folder_path = os.path.join(FOLDER_OUTPUT_DISK, f"{datetime.now().strftime('%Y%m%d')}_{sanitize_for_foldername(clean_name)}")
    os.makedirs(final_folder_path, exist_ok=True)
    
    transcription_out_path = os.path.join(final_folder_path, 'transkrypcja.txt')
    info_out_path = os.path.join(final_folder_path, 'info.txt')

    try:
        print("  -> Transkrypcja Whisper...")
        transcription_content, lang = transkrybuj_plik_audio(filepath)

        with open(transcription_out_path, "w", encoding="utf-8") as f:
            f.write(transcription_content)

        with open(info_out_path, "w", encoding="utf-8") as f:
            f.write(f"Oryginalny plik: {filename}\nRozmiar: {filesize_mb:.2f} MB\nJęzyk: {lang}\nData przetworzenia: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nŚcieżka źródłowa: {os.path.abspath(filepath)}\n")

        if not os.path.exists(transcription_out_path) or os.path.getsize(transcription_out_path) == 0:
            raise RuntimeError(f"Plik transkrypcji nie został poprawnie utworzony: {transcription_out_path}")

        print(f"[SUKCES] Transkrypcja zapisana w:\n   {os.path.abspath(final_folder_path)}")

        archive_dest = bezpieczne_przeniesienie_do_archiwum(filepath, FOLDER_ARCHIVE_DISK)
        print(f"[Archiwum] Przeniesiono plik źródłowy do:\n   {os.path.abspath(archive_dest)}")
        return True

    except Exception as e:
        print(f"[BŁĄD] Transkrypcja pliku {filename} nie powiodła się: {e}")
        return False

def pobierz_pliki_z_kolejki_dysk():
    """Zwraca listę plików oczekujących w folderze 'do_transkrypcji' z pominięciem archiwum."""
    if not os.path.exists(FOLDER_INPUT_DISK):
        return []
    
    pliki = []
    try:
        for entry in os.scandir(FOLDER_INPUT_DISK):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ALLOWED_MEDIA_EXTENSIONS:
                    pliki.append(entry.path)
    except Exception as e:
        print(f"[BŁĄD] Nie udało się przeskanować folderu {FOLDER_INPUT_DISK}: {e}")
    
    pliki.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
    return pliki

# === ROZPOZNAWANIE I KOLEJKA LINKÓW ===
def classify_url(url):
    u = url.strip().lower()
    if "reddit.com" in u or "redd.it" in u:
        return "REDDIT"
    if "youtube.com/watch" in u or "youtu.be/" in u or "youtube.com/shorts/" in u or "youtube.com/live" in u:
        return "YOUTUBE"
    if "facebook.com" in u or "fb.watch" in u or "fb.com" in u:
        return "FACEBOOK"
    if "instagram.com" in u or "instagr.am" in u:
        return "INSTAGRAM"
    return None

def przetworz_link(link):
    """Kieruje link do odpowiedniego modułu."""
    clean_link = link.strip()
    url_type = classify_url(clean_link)
    if url_type == "REDDIT":
        return obsluz_reddita(clean_link)
    elif url_type == "YOUTUBE":
        return obsluz_youtube(clean_link)
    elif url_type == "FACEBOOK":
        return obsluz_facebook(clean_link)
    elif url_type == "INSTAGRAM":
        return obsluz_instagram(clean_link)
    else:
        print(f"[!] Nieznany format linku: {clean_link}")
        return False

# === SYSTEM KOLEJKI PLIKOWEJ (task_queue/) ===
DISK_QUEUE_ADAPTER = DiskQueueAdapter()
SEEN_URLS = set()
QUEUE_LOCK = threading.Lock()
STOP_EVENT = threading.Event()
GLOBAL_RADAR_DB = RadarDatabase()

def clipboard_listener_thread():
    """Wątek monitorujący schowek — linki trafiają do fizycznej kolejki task_queue/."""
    last_clipboard_raw = ""
    while not STOP_EVENT.is_set():
        try:
            curr_raw = pyperclip.paste().strip()
        except Exception:
            curr_raw = ""

        if curr_raw and curr_raw != last_clipboard_raw:
            last_clipboard_raw = curr_raw
            url_type = classify_url(curr_raw)
            if url_type:
                with QUEUE_LOCK:
                    if curr_raw not in SEEN_URLS:
                        SEEN_URLS.add(curr_raw)
                        created = queue_task_to_disk(url_type, curr_raw)
                        if created:
                            print(f"\n[KOLEJKA] + Dodano link do task_queue/: [{url_type}] {curr_raw}")
                        else:
                            print(f"\n[KOLEJKA] Link już istnieje w kolejce plikowej: {curr_raw}")

        time.sleep(0.35)

def _handle_disk_task(entry):
    """Przetwarza jedno zadanie z kolejki plikowej."""
    data = entry["data"]
    file_path = entry["file_path"]
    target_url = data.get("target_url")
    platform = data.get("platform", "UNKNOWN")

    if not target_url:
        remove_disk_task(file_path)
        return

    print(f"\n[ZADANIE] Rozpoczynam przetwarzanie [{platform}]")
    print(f" -> Cel: {target_url}")
    print(f" -> Pozostało w task_queue/: {len(list_disk_tasks())}")

    GLOBAL_RADAR_DB.mark_task_processing(target_url)

    sukces = False
    error_msg = "Przetwarzanie zwróciło False"
    try:
        sukces = przetworz_link(target_url)
    except Exception as e:
        print(f"[BŁĄD] Wystąpił niespodziewany wyjątek w zadaniu: {e}")
        error_msg = str(e)

    if sukces:
        GLOBAL_RADAR_DB.mark_task_done(target_url)
        remove_disk_task(file_path)
        print("[OK] Zadanie zakończone i usunięte z kolejki plikowej.")
    else:
        GLOBAL_RADAR_DB.mark_task_failed(target_url, error_msg)

        retries = data.get("retries", 0) + 1
        max_retries = data.get("max_retries", 3)

        if retries >= max_retries:
            remove_disk_task(file_path)
            print(f"[FAILED] Zadanie usunięte po {max_retries} próbach: {target_url}")
        else:
            data["retries"] = retries
            data["last_error"] = error_msg
            tmp_path = file_path + ".tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, file_path)
            except Exception:
                pass
            print(f"[RETRY] Zadanie pozostaje w kolejce (próba {retries}/{max_retries}).")
            time.sleep(2)

def queue_worker_thread():
    """Główny wątek roboczy. Przetwarza kolejkę plikową i folder do_transkrypcji."""
    while not STOP_EVENT.is_set():
        tasks = list_disk_tasks()
        if tasks:
            _handle_disk_task(tasks[0])
            continue

        pliki_dysk = pobierz_pliki_z_kolejki_dysk()
        if pliki_dysk:
            plik = pliki_dysk[0]
            print(f"\n[KOLEJKA] Rozpoczynam przetwarzanie pliku z dysku: {os.path.basename(plik)}")
            obsluz_plik_lokalny(plik)
            print("\n[INFO] Oczekiwanie na kolejne linki lub pliki...")
        else:
            time.sleep(0.5)

def wyswietl_stan_poczatkowy():
    wyczysc_ekran()
    device_info = f"CUDA ({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else "CPU"
    cookies_info = "Wykryto (cookies.txt)" if os.path.exists(os.path.join(SCRIPT_DIR, 'cookies.txt')) else "Brak (opcjonalne)"
    zrodla = wczytaj_obserwowane_zrodla(SLEDZONE_FILE)
    radar_info = f"Aktywny ({len(zrodla)} obserwowanych źródeł w sledzone.txt)" if zrodla else "Brak źródeł (edytuj sledzone.txt)"

    print("=" * 68)
    print("      ŁOWCA v8.1 — KOLEJKA PLIKOWA + RADAR + TRANSKRYPCJA")
    print("=" * 68)
    print(f" Folder projektu:       {BASE_OUTPUT_DIR}")
    print(f" Folder kolejki:        {TASK_QUEUE_DIR}")
    print(f" Folder YouTube:        {FOLDER_YT}")
    print(f" Folder Facebook:       {FOLDER_FB}")
    print(f" Folder Instagram:      {FOLDER_IG}")
    print(f" Folder Reddit:         {FOLDER_REDDIT}")
    print(f" Folder Wejściowy Dysk: {FOLDER_INPUT_DISK}")
    print(f" Folder Archiwum Dysk:  {FOLDER_ARCHIVE_DISK}")
    print(f" Folder Wyjściowy Dysk: {FOLDER_OUTPUT_DISK}")
    print(f" Moduł Radaru (Watcher):{radar_info}")
    print(f" Silnik Whisper:        {device_info}")
    print(f" Ciasteczka FB/YT:      {cookies_info}")
    print("=" * 68)
    print(" MOŻLIWOŚCI SYSTEMU:")
    print("  1. RADAR: W tle sam monitoruje profile/kanały z 'sledzone.txt' i pobiera nowości!")
    print("  2. SCHOWEK: Kopiuj linki (CTRL+C) — wpadają do task_queue/")
    print("  3. DYSK: Wrzuć pliki do 'do_transkrypcji' -> zostaną przetworzone w tle")
    print("  4. Kolejka plikowa: podgląd 'python lowca.py --show-queue'")
    print("     czyszczenie:      'python lowca.py --clear-queue'")
    print("=" * 68)

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()

        if arg in ["--clear-queue", "--clear"]:
            n = clear_disk_queue()
            print(f"[KOLEJKA] Usunięto {n} zadań z task_queue/.")
            return

        if arg in ["--show-queue", "--queue"]:
            tasks = list_disk_tasks()
            print(f"[KOLEJKA] Liczba zadań w task_queue/: {len(tasks)}")
            for i, t in enumerate(tasks, 1):
                d = t["data"]
                print(f"  {i}. [{d.get('platform', '?')}] {d.get('target_url')}")
                print(f"     retries: {d.get('retries', 0)}/{d.get('max_retries', 3)} | last_error: {d.get('last_error')}")
            return

        if arg in ["--radar", "--skanuj", "-r"]:
            print("[RADAR] Uruchamiam jednorazowy cykl skanowania radaru...")
            wykonaj_cykl_radaru(GLOBAL_RADAR_DB, DISK_QUEUE_ADAPTER, SEEN_URLS, QUEUE_LOCK)
            print("[RADAR] Skanowanie zakończone. Przetwarzam kolejkę plikową...")
            while not STOP_EVENT.is_set():
                tasks = list_disk_tasks()
                if not tasks:
                    break
                _handle_disk_task(tasks[0])
            return

        if arg in ["--lokalne", "--batch", "-b", "--kolejka"]:
            pliki = pobierz_pliki_z_kolejki_dysk()
            print(f"[Dysk] Znaleziono {len(pliki)} plików.")
            for p in pliki:
                obsluz_plik_lokalny(p)
            return

        if os.path.isfile(arg):
            obsluz_plik_lokalny(arg)
            return

        if os.path.isdir(arg):
            for item in os.listdir(arg):
                full_p = os.path.join(arg, item)
                if os.path.isfile(full_p):
                    obsluz_plik_lokalny(full_p)
            return

        if arg.startswith("http://") or arg.startswith("https://"):
            przetworz_link(arg)
            return

    wyswietl_stan_poczatkowy()
    print("\n[INFO] Monitor kolejki plikowej i Radar aktywne. Kopiuj linki lub edytuj 'sledzone.txt'...")

    t_clip = threading.Thread(target=clipboard_listener_thread, daemon=True)
    t_work = threading.Thread(target=queue_worker_thread, daemon=True)
    t_radar = threading.Thread(
        target=radar_background_thread,
        args=(DISK_QUEUE_ADAPTER, SEEN_URLS, STOP_EVENT, QUEUE_LOCK, GLOBAL_RADAR_DB),
        daemon=True
    )

    t_clip.start()
    t_work.start()
    t_radar.start()

    try:
        while not STOP_EVENT.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n[INFO] Zatrzymywanie programu ŁOWCA... Do zobaczenia!")
        STOP_EVENT.set()
        time.sleep(0.5)

if __name__ == "__main__":
    main()
