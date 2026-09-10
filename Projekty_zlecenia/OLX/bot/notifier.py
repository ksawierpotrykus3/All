"""Powiadomienia Telegram. Zero zewnętrznych zależności — czysty POST na Bot API.

Użycie:
    notifier = Notifier(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID)
    await notifier.send("tekst")
    await notifier.hit(hit)
    await notifier.critical("alarm")
"""
import asyncio

from curl_cffi.requests import AsyncSession

from . import config


class Notifier:
    """Wysyła wiadomości na czat Telegram przez Bot API."""

    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or config.TELEGRAM_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            from .logger import LOG_APP
            LOG_APP.warning(
                "NOTIFIER: brak tokena/chat_id — powiadomienia WYŁĄCZONE"
            )

    async def send(self, text: str):
        """Wyślij dowolny tekst. Wycisza błędy sieci — nie może wywalić bota."""
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            async with AsyncSession(timeout=10) as s:
                await s.post(url, json={"chat_id": self.chat_id, "text": text})
        except Exception as e:  # noqa: BLE001 — powiadomienie nie może zabić pętli
            from .logger import LOG_APP
            LOG_APP.error(f"NOTIFIER: nie udało się wysłać: {e}")

    async def hit(self, hit: dict):
        """Powiadomienie o trafieniu (okazji)."""
        label = hit.get("label", "HIT")
        price = hit.get("price")
        price_s = f"{price} zł" if price is not None else "?"
        title = hit.get("title", "")
        url = hit.get("url", "")
        region = hit.get("region", "")
        await self.send(
            f"🔥 TRAFIENIE [{label}] {price_s}\n"
            f"{title}\n"
            f"{region}\n"
            f"{url}"
        )

    async def critical(self, text: str):
        """Alarm krytyczny — ban, seed fail, watchdog."""
        await self.send(f"🚨 {text}")