"""
spike_harvest_signals.py — zbiera REALNE sygnały fingerprintu z Camoufox (Firefox 152)
i zapisuje do harvest_signals.json.

Cel: podpięcie prawdziwych wartości (canvas, WebGL, audio, navigator, screen, timezone,
permissions, storage, media) pod lekki silnik JS (hybrid_consume_loop.js), który sam
nie ma dostępu do API przeglądarki.

Użycie:
    python spike_harvest_signals.py --url "https://www.vinted.pl/items/9807925466-genesis-krypton-700"

Wymaga: camoufox (pip install camoufox[geoip]).
"""
import argparse
import json
import sys
import time
from pathlib import Path

try:
    from camoufox.sync_api import Camoufox
except ImportError:
    print("Brak camoufox. Zainstaluj: pip install camoufox[geoip]")
    sys.exit(1)


def harvest(url: str, wait_ms: int = 4000) -> dict:
    """Uruchamia Camoufox (Firefox 152, fingerprint_preset), zbiera realne sygnały."""
    with Camoufox(headless=True, fingerprint_preset=True, block_webgl=True) as browser:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)  # pozwól SDK/JS się zainicjalizować

        signals = page.evaluate("""
            async () => {
                const out = {};
                // --- Navigator / platforma ---
                out.userAgent = navigator.userAgent;
                out.platform = navigator.platform;
                out.language = navigator.language;
                out.languages = (navigator.languages ?? []).join(',');
                out.cookieEnabled = navigator.cookieEnabled;
                out.hardwareConcurrency = navigator.hardwareConcurrency ?? 0;
                out.maxTouchPoints = navigator.maxTouchPoints ?? 0;
                out.deviceMemory = navigator.deviceMemory ?? 0;
                out.webdriver = !!navigator.webdriver;

                out.screen_width = screen.width;
                out.screen_height = screen.height;
                out.screen_avail_width = screen.availWidth;
                out.screen_avail_height = screen.availHeight;
                out.screen_color_depth = screen.colorDepth;
                out.inner_width = innerWidth;
                out.inner_height = innerHeight;
                out.outer_width = outerWidth;
                out.outer_height = outerHeight;
                out.device_pixel_ratio = devicePixelRatio;
                out.visual_viewport_width = visualViewport ? visualViewport.width : null;
                out.visual_viewport_height = visualViewport ? visualViewport.height : null;
                out.visual_viewport_scale = visualViewport ? visualViewport.scale : null;
                out.orientation_type = screen.orientation ? screen.orientation.type : null;

                out.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone ?? null;
                out.timezone_offset = new Date().getTimezoneOffset();

                try {
                    const c = document.createElement('canvas');
                    c.width = 240; c.height = 60;
                    const g = c.getContext('2d');
                    if (g) {
                        g.fillStyle = '#f60'; g.fillRect(0, 0, 240, 60);
                        g.fillStyle = '#069'; g.font = '18px Arial';
                        g.fillText('Cwm fjordbank glyphs vext quiz', 2, 20);
                        g.fillStyle = '#f90'; g.beginPath(); g.arc(60, 40, 20, 0, Math.PI * 2); g.fill();
                        out.canvas_data_url = c.toDataURL();
                        const d = g.getImageData(0, 0, 240, 60).data;
                        let nz = 0;
                        for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) nz++;
                        out.canvas_alpha_nonzero = nz / (240 * 60);
                    }
                } catch (e) { out.canvas_error = String(e); }

                try {
                    const c = document.createElement('canvas');
                    const gl = c.getContext('webgl') ?? c.getContext('experimental-webgl');
                    if (gl) {
                        out.webgl_vendor = gl.getParameter(gl.VENDOR);
                        out.webgl_renderer = gl.getParameter(gl.RENDERER);
                        out.webgl_version = gl.getParameter(gl.VERSION);
                        out.webgl_shading = gl.getParameter(gl.SHADING_LANGUAGE_VERSION);
                        const dbg = gl.getExtension('WEBGL_debug_renderer_info');
                        if (dbg) {
                            out.webgl_unmasked_vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                            out.webgl_unmasked_renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                        }
                        out.webgl_extensions = (gl.getSupportedExtensions() ?? []).join(',');
                    }
                } catch (e) { out.webgl_error = String(e); }

                try {
                    const ac = new OfflineAudioContext(2, 44100, 44100);
                    const osc = ac.createOscillator();
                    osc.type = 'triangle'; osc.frequency.value = 10000;
                    const comp = ac.createDynamicsCompressor();
                    comp.threshold.value = -50; comp.knee.value = 40;
                    comp.ratio.value = 12; comp.attack.value = 0; comp.release.value = 0.25;
                    osc.connect(comp); comp.connect(ac.destination); osc.start(0);
                    const buf = await ac.startRendering();
                    const d = buf.getChannelData(0);
                    let sum = 0;
                    for (let i = 0; i < d.length; i++) sum += d[i];
                    out.audio_sum = sum;
                    out.audio_sample_rate = buf.sampleRate;
                    out.audio_channels = buf.numberOfChannels;
                } catch (e) { out.audio_error = String(e); }

                out.perm_geolocation = 0;
                out.perm_notifications = 0;
                out.perm_camera = 0;
                out.perm_microphone = 0;
                out.perm_persistent_storage = 0;
                const pmap = { prompt: 0, granted: 1, denied: 2 };
                const pkeys = ['perm_geolocation', 'perm_notifications', 'perm_camera', 'perm_microphone', 'perm_persistent_storage'];
                if (navigator.permissions && navigator.permissions.query) {
                    const pnames = ['geolocation', 'notifications', 'camera', 'microphone', 'persistent-storage'];
                    for (let i = 0; i < pnames.length; i++) {
                        try { const s = await navigator.permissions.query({ name: pnames[i] }); out[pkeys[i]] = pmap[s.state] ?? 0; } catch (e) {}
                    }
                }

                out.cookie_enabled = !!navigator.cookieEnabled;
                try { localStorage.setItem('_t', '1'); localStorage.removeItem('_t'); out.localstorage = 1; } catch (e) { out.localstorage = 0; }
                out.indexeddb = !!window.indexedDB;
                out.storage_quota = null; out.storage_usage = null; out.storage_persisted = 0;
                try {
                    if (navigator.storage && navigator.storage.estimate) {
                        const est = await navigator.storage.estimate();
                        out.storage_quota = est.quota; out.storage_usage = est.usage;
                    }
                    if (navigator.storage && navigator.storage.persisted) {
                        out.storage_persisted = (await navigator.storage.persisted()) ? 1 : 0;
                    }
                } catch (e) { out.storage_error = String(e); }

                try {
                    const a = document.createElement('audio');
                    const v = document.createElement('video');
                    const at = ['audio/ogg', 'audio/flac', 'audio/mp3', 'audio/aac', 'audio/x-m4a'];
                    const vt = ['video/mp4; codecs="avc1.42E01E"', 'video/webm; codecs="vp8"', 'video/webm; codecs="vp9"'];
                    const cmap = { '': 0, 'maybe': 1, 'probably': 2 };
                    out.audio_can_play = at.map(t => cmap[a.canPlayType(t)] ?? 0).join(',');
                    out.video_can_play = vt.map(t => cmap[v.canPlayType(t)] ?? 0).join(',');
                } catch (e) { out.media_error = String(e); }

                out.service_worker = 'serviceWorker' in navigator ? 1 : 0;
                out.webassembly = typeof WebAssembly !== 'undefined' ? 1 : 0;
                try { out.webgl1 = !!document.createElement('canvas').getContext('webgl'); } catch (e) { out.webgl1 = 0; }
                try { out.webgl2 = !!document.createElement('canvas').getContext('webgl2'); } catch (e) { out.webgl2 = 0; }
                out.webrtc = !!(window.RTCPeerConnection ?? window.webkitRTCPeerConnection);
                out.shared_array_buffer = typeof SharedArrayBuffer !== 'undefined' ? 1 : 0;
                out.cross_origin_isolated = self.crossOriginIsolated ? 1 : 0;
                out.audio_context = !!(window.AudioContext ?? window.webkitAudioContext);
                out.offline_audio_context = !!window.OfflineAudioContext;
                out.automation_globals = ['__webdriver_evaluate', '__webdriver_script_function', '__webdriver_script_func', '$cdc_asdjflasutopfhvcZLmcfl_', '$chrome'].filter(k => k in window).join(',');

                return out;
            }
        """)

        return signals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.vinted.pl/items/9807925466-genesis-krypton-700")
    parser.add_argument("--out", default=str(Path(__file__).with_name("harvest_signals.json")))
    parser.add_argument("--wait", type=int, default=4000)
    args = parser.parse_args()

    print(f"[harvest] Zbieranie sygnalow z: {args.url}")
    signals = harvest(args.url, args.wait)

    payload = {
        "collected_at_ts": time.time(),
        "url": args.url,
        "signals": signals,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[harvest] Zapisano {len(signals)} sygnalow do: {out_path}")


if __name__ == "__main__":
    main()