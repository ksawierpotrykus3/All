"""
fingerprint_harvester.py — jednorazowy harvest fingerprintu DataDome z Camoufox.

Zasada: Camoufox tylko dla fingerprintu (raz, przy setupie), reszta przez curl_cffi + Node.js.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any

from camoufox.async_api import AsyncCamoufox

FINGERPRINT_PATH = Path(__file__).parent / "fingerprint_datadome.json"


async def harvest_fingerprint() -> Dict[str, Any]:
    """
    Jednorazowy harvest fingerprintu DataDome z Camoufox.
    Zapisuje do fingerprint_datadome.json dla późniejszego użycia.
    """
    async with AsyncCamoufox(
        headless=True,
        fingerprint_preset=True,
        block_webgl=False,  # WebGL potrzebny dla DataDome
    ) as browser:
        page = await browser.new_page()
        await page.goto("https://www.vinted.pl", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Wyciągnij fingerprint DataDome
        fingerprint = await page.evaluate("""
            () => {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl');
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');

                return {
                    webgl_vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
                    webgl_renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL),
                    canvas_fingerprint: canvas.toDataURL(),
                    screen_width: window.screen.width,
                    screen_height: window.screen.height,
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    user_agent: navigator.userAgent,
                    platform: navigator.platform,
                    hardware_concurrency: navigator.hardwareConcurrency,
                    device_memory: navigator.deviceMemory,
                };
            }
        """)

        # Zapisz do pliku
        FINGERPRINT_PATH.write_text(
            json.dumps(fingerprint, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"✅ Fingerprint zapisany do: {FINGERPRINT_PATH}")
        return fingerprint


async def main():
    fingerprint = await harvest_fingerprint()
    print(f"WebGL Renderer: {fingerprint['webgl_renderer']}")
    print(f"User-Agent: {fingerprint['user_agent']}")


if __name__ == "__main__":
    asyncio.run(main())
