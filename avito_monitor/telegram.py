"""Отправка уведомлений в Telegram через Bot API."""
from __future__ import annotations

import html
import logging
import time

import requests

from .analysis import GRADE_RU

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


def _plural_reviews(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} отзыв"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} отзыва"
    return f"{n} отзывов"


def format_item(search_name: str, item, market: float | None, reason: str, old_price: int | None = None,
                details=None, analysis=None) -> str:
    e = html.escape
    head = "🔥" if not analysis or analysis.score >= 7 else "👀" if analysis.score >= 4 else "⚠️"
    lines = [f"{head} <b>{e(search_name)}</b>", f'<a href="{e(item.url)}">{e(item.title)}</a>']
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

    if details:
        cond = [e(details.condition)] if details.condition else []
        if analysis:
            g = e(GRADE_RU[analysis.grade])
            if analysis.grade == "excellent":
                g = f"<b>{g}</b>"
            if analysis.grade_note and not analysis.grade_note.startswith("в объявлении"):
                g += f" ({e(analysis.grade_note)})"
            cond.append(g)
        if cond:
            lines.append("📦 Состояние: " + " → ".join(cond))
        if analysis and analysis.battery is not None:
            lines.append(f"🔋 АКБ: <b>{analysis.battery}%</b>")
        extra = [f"{k}: {v}" for k, v in details.params.items() if not k.lower().startswith("состояние")][:4]
        if extra:
            lines.append("🔧 " + e(" · ".join(extra)))
        seller = [details.seller_name or "Продавец"]
        if details.seller_rating is not None:
            seller.append(f"⭐ {details.seller_rating:.1f}")
        if details.seller_reviews is not None:
            seller.append(_plural_reviews(details.seller_reviews))
        if details.seller_type:
            seller.append(details.seller_type)
        if details.seller_since:
            seller.append(f"с {details.seller_since}")
        lines.append("👤 " + e(" · ".join(seller)))
    if analysis:
        lines.append(f"🧮 Оценка сделки: <b>{analysis.score:g}/10</b>")
        if analysis.red:
            lines.append("❗ " + e(", ".join(analysis.red)))
        if analysis.green:
            lines.append("✅ " + e(", ".join(analysis.green)))
    if details and details.description:
        desc = " ".join(details.description.split())
        lines.append(f"📝 {e(desc[:300])}{'…' if len(desc) > 300 else ''}")
    lines.append(f"<i>{e(reason)}</i>")
    return "\n".join(lines)
