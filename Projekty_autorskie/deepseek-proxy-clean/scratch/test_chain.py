from itertools import chain
import queue
import threading

def _iter_lines_with_watchdog(generator, timeout_sec=10.0):
    q = queue.Queue()
    stop_ev = threading.Event()

    def reader():
        try:
            for item in generator:
                if stop_ev.is_set():
                    break
                q.put(("data", item))
            q.put(("end", None))
        except Exception as e:
            q.put(("error", e))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    while True:
        try:
            kind, val = q.get(timeout=timeout_sec)
            if kind == "data":
                yield val
            elif kind == "end":
                break
            elif kind == "error":
                raise val
        except queue.Empty:
            stop_ev.set()
            break

lines = ["line1", "line2", "line3"]
it = iter(lines)
w1 = _iter_lines_with_watchdog(it)

pre = []
for l in w1:
    pre.append(l)
    if l == "line1":
        break

print("Pre:", pre)
w2 = _iter_lines_with_watchdog(chain(pre, w1))
print("W2:", list(w2))