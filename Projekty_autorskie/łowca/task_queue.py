# task_queue.py - Trwała kolejka plikowa (task_queue/) dla programu ŁOWCA
import os
import sys
import json
import time
import hashlib
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_QUEUE_DIR = os.path.join(SCRIPT_DIR, "task_queue")
os.makedirs(TASK_QUEUE_DIR, exist_ok=True)

DISK_QUEUE_LOCK = threading.Lock()

def _url_to_filename(url):
    """Tworzy bezpieczną, deterministyczną nazwę pliku dla danego URL."""
    clean_name = "".join(c if c.isalnum() else "_" for c in url)[:40].strip("_")
    h = hashlib.md5(url.encode('utf-8')).hexdigest()[:10]
    return f"{clean_name}_{h}.json"

def queue_task_to_disk(platform, target_url, retries=0, max_retries=3, extra_data=None):
    """Zapisuje zadanie do folderu task_queue/ jako atomowy plik JSON. Zwraca True jeśli utworzono nowy plik."""
    with DISK_QUEUE_LOCK:
        filename = _url_to_filename(target_url)
        file_path = os.path.join(TASK_QUEUE_DIR, filename)
        
        if os.path.exists(file_path):
            return False # Zadanie już istnieje w kolejce plikowej
            
        task_data = {
            "platform": platform,
            "target_url": target_url,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "retries": retries,
            "max_retries": max_retries,
            "last_error": None
        }
        if extra_data:
            task_data.update(extra_data)
            
        tmp_path = file_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(task_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, file_path)
            return True
        except Exception as e:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass
            print(f"[BŁĄD] Nie udało się zapisać zadania do kolejki plikowej: {e}")
            return False

def list_disk_tasks():
    """Zwraca listę wszystkich oczekujących zadań z folderu task_queue/ posortowanych po czasie utworzenia."""
    with DISK_QUEUE_LOCK:
        if not os.path.exists(TASK_QUEUE_DIR):
            return []
            
        tasks = []
        try:
            entries = [os.path.join(TASK_QUEUE_DIR, f) for f in os.listdir(TASK_QUEUE_DIR) if f.endswith(".json")]
            entries.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
            
            for fpath in entries:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        tasks.append({
                            "file_path": fpath,
                            "data": data
                        })
                except Exception:
                    pass
        except Exception as e:
            print(f"[BŁĄD] Błąd listowania kolejki plikowej: {e}")
            
        return tasks

def remove_disk_task(file_path):
    """Usuwa plik zadania z task_queue/."""
    with DISK_QUEUE_LOCK:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            print(f"[BŁĄD] Nie udało się usunąć pliku zadania {file_path}: {e}")
        return False

def clear_disk_queue():
    """Czyści cały folder task_queue/ i zwraca liczbę usuniętych plików."""
    with DISK_QUEUE_LOCK:
        count = 0
        if not os.path.exists(TASK_QUEUE_DIR):
            return 0
        for f in os.listdir(TASK_QUEUE_DIR):
            if f.endswith(".json") or f.endswith(".tmp"):
                try:
                    os.remove(os.path.join(TASK_QUEUE_DIR, f))
                    count += 1
                except Exception:
                    pass
        return count

class DiskQueueAdapter:
    """Adapter udostępniający interfejs put() kompatybilny z modułem radaru i kolejką w pamięci."""
    def put(self, item):
        # Format krotki: ("URL", platform, target_url) lub ("DISK", ..., path)
        if isinstance(item, tuple) and len(item) >= 3:
            t_type, platform, target_url = item[0], item[1], item[2]
            if t_type == "URL":
                queue_task_to_disk(platform, target_url)
        elif isinstance(item, dict):
            plat = item.get("platform", "UNKNOWN")
            t_url = item.get("target_url")
            if t_url:
                queue_task_to_disk(plat, t_url, extra_data=item)

    def empty(self):
        return len(list_disk_tasks()) == 0

    def qsize(self):
        return len(list_disk_tasks())
