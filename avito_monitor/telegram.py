"""Отправка уведомлений в Telegram через Bot API."""
from __future__ import annotations

import html
import logging
import time

import requests

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_ids: list[str | int], proxy: str | None = None):
        self.api = f"https://api.telegram.org/bot{token}"
        self.chat_ids = chat_ids
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def send(self, text: str) -> None:
        for chat_id in self.chat_ids:
            for attempt in range(3):
                try:
                    r = requests.post(
                        f"{self.api}/sendMessage",
                        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                              "disable_web_page_preview": False},
                        timeout=20,
                        proxies=self.proxies,
                    )
                    if r.status_code == 429:
                        time.sleep(r.json().get("parameters", {}).get("retry_after", 5))
                        continue
                    r.raise_for_status()
                    break
                except requests.RequestException as e:
                    log.warning("Telegram: ошибка отправки (%s), попытка %d", e, attempt + 1)
                    time.sleep(3)


def fmt_price(p: float | int | None) -> str:
    return "—" if p is None else f"{int(p):,}".replace(",", " ") + " ₽"


def format_item(search_name: str, item, market: float | None, reason: str, old_price: int | None = None) -> str:
    e = html.escape
    lines = [f"🔥 <b>{e(search_name)}</b>", f'<a href="{e(item.url)}">{e(item.title)}</a>']
    price_line = f"💰 <b>{fmt_price(item.price)}</b>"
    if old_price:
        price_line += f" (было {fmt_price(old_price)})"
    lines.append(price_line)
    if market and item.price:
        diff = (1 - item.price / market) * 100
        lines.append(f"📊 Рынок ~{fmt_price(market)} · дешевле на {diff:.0f}%")
    if item.location:
        lines.append(f"📍 {e(item.location)}")
    if item.date:
        lines.append(f"🕒 {e(item.date)}")
    lines.append(f"<i>{e(reason)}</i>")
    return "\n".join(lines)
