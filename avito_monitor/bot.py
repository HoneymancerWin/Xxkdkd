"""Telegram-бот: панель кнопок, находки, покупки, категории, цены, настройки."""
from __future__ import annotations

import html
import logging
import re
import threading
import time

from .catalog import CATEGORIES, CITIES
from .storage import Storage
from .telegram import Telegram, fmt_price

log = logging.getLogger(__name__)
e = html.escape

B_DEALS, B_BOUGHT, B_CATS, B_PRICES = "🔥 Находки", "🛒 Покупки", "📦 Категории", "📈 Цены"
B_SETTINGS, B_NOW, B_PAUSE, B_RESUME = "⚙️ Настройки", "🔄 Проверить сейчас", "⏸ Пауза", "▶️ Продолжить"

CYCLES = {
    "discount": [10, 15, 20, 25, 30, 40],
    "grade": ["excellent", "good", "any"],
    "min_rating": [None, 4.0, 4.5, 4.8],
    "min_reviews": [0, 1, 3, 10],
    "min_battery": [None, 80, 85, 90, 95, 100],
    "interval": [120, 180, 300, 600],
    "delivery": [True, False],
}
GRADE_LABEL = {"excellent": "новое / отличное", "good": "без дефектов", "any": "любое"}


def ago(ts: float | None) -> str:
    if not ts:
        return "ещё не было"
    s = int(time.time() - ts)
    if s < 60:
        return "только что"
    if s < 3600:
        return f"{s // 60} мин назад"
    if s < 86400:
        return f"{s // 3600} ч назад"
    return f"{s // 86400} дн назад"


def pct(price, market) -> str:
    return f"−{(1 - price / market) * 100:.0f}%" if price and market else ""


class Bot:
    def __init__(self, tg: Telegram, db: Storage, st, wake: threading.Event):
        self.tg, self.db, self.st, self.wake = tg, db, st, wake
        self.owners = {str(c) for c in tg.chat_ids}
        self.awaiting: dict[str, int] = {}  # chat_id → deal_id, ждём цену продажи

    # ---------- клавиатуры ----------
    def menu(self) -> dict:
        return {"keyboard": [[B_DEALS, B_BOUGHT], [B_CATS, B_PRICES], [B_SETTINGS, B_NOW],
                             [B_RESUME if self.st["paused"] else B_PAUSE]],
                "resize_keyboard": True, "is_persistent": True}

    def hello(self) -> None:
        if time.time() - (self.db.get("hello_ts") or 0) < 6 * 3600:
            return  # не спамим при каждом перезапуске
        self.db.set("hello_ts", time.time())
        cats = ", ".join(c.title for c in CATEGORIES.values() if self.st.cat_on(c))
        self.tg.send(
            "🤖 <b>Бот запущен</b>\n"
            f"Слежу: {cats}\nГород: {CITIES.get(self.st['city'], self.st['city'])}\n\n"
            "Первые проходы я собираю цены, чтобы понять рынок каждой модели, — находки пойдут следом.\n"
            "Кнопки внизу — управление.", markup=self.menu())

    # ---------- цикл ----------
    def poll(self) -> None:
        offset = self.db.get("tg_offset", 0)
        while True:
            upd = self.tg.call("getUpdates", http_timeout=40, offset=offset, timeout=25)
            if upd is None:
                time.sleep(5)
                continue
            for u in upd:
                offset = u["update_id"] + 1
                try:
                    self.handle(u)
                except Exception:
                    log.exception("ошибка обработки сообщения Telegram")
            if upd:
                self.db.set("tg_offset", offset)

    def handle(self, u: dict) -> None:
        if "callback_query" in u:
            q = u["callback_query"]
            chat = str(q["message"]["chat"]["id"])
            if chat not in self.owners:
                return
            note = self.on_callback(q["data"], chat, q["message"]["message_id"])
            self.tg.call("answerCallbackQuery", callback_query_id=q["id"], text=note or "")
            return
        msg = u.get("message")
        if not msg or "text" not in msg:
            return
        chat = str(msg["chat"]["id"])
        if chat not in self.owners:
            self.tg.send("Это личный бот, доступа нет.", chat_id=chat)
            return
        self.on_text(msg["text"].strip(), chat)

    # ---------- текст и кнопки меню ----------
    def on_text(self, text: str, chat: str) -> None:
        if chat in self.awaiting and re.search(r"\d", text):
            deal_id = self.awaiting.pop(chat)
            price = int(re.sub(r"\D", "", text))
            self.db.set_deal(deal_id, status="sold", sold_price=price)
            d = self.db.deal(deal_id)
            profit = price - d["price"]
            self.tg.send(f"💰 Записал: {e(d['model'])} продан за {fmt_price(price)}, "
                         f"{'прибыль' if profit >= 0 else 'убыток'} <b>{fmt_price(abs(profit))}</b>",
                         chat_id=chat, markup=self.menu())
            return
        self.awaiting.pop(chat, None)
        if text == B_DEALS:
            self.send_deals(chat)
        elif text == B_BOUGHT:
            self.send_bought(chat)
        elif text == B_CATS:
            self.tg.send(*self.cats_view(), chat_id=chat)
        elif text == B_PRICES:
            self.send_prices(chat)
        elif text == B_SETTINGS:
            self.tg.send(*self.settings_view(), chat_id=chat)
        elif text == B_NOW:
            self.wake.set()
            self.tg.send("🔄 Запустил проверку." if not self.st["paused"] else
                         "Бот на паузе — нажмите «▶️ Продолжить».", chat_id=chat)
        elif text in (B_PAUSE, B_RESUME):
            self.st["paused"] = text == B_PAUSE
            self.wake.set()
            self.tg.send("⏸ Пауза. Новые объявления не проверяю." if text == B_PAUSE
                         else "▶️ Продолжаю следить.", chat_id=chat, markup=self.menu())
        else:
            self.tg.send(
                "Я присылаю объявления дешевле рынка. Кнопки:\n"
                f"{B_DEALS} — последние находки\n{B_BOUGHT} — что купили, выгода и прибыль\n"
                f"{B_CATS} — что отслеживать\n{B_PRICES} — рыночные цены по моделям\n"
                f"{B_SETTINGS} — город, скидка, состояние, продавец, АКБ",
                chat_id=chat, markup=self.menu())

    # ---------- экраны ----------
    def deals_view(self) -> tuple[str, dict | None]:
        rows = self.db.deals(("new",), 10)
        if not rows:
            return "Пока находок нет. Как только появится что-то дешевле рынка — пришлю.", None
        lines, kb, pair = ["🔥 <b>Последние находки</b>\n"], [], []
        for i, d in enumerate(rows, 1):
            lines.append(f"{i}. <a href=\"{e(d['url'])}\">{e(d['model'])}</a> — <b>{fmt_price(d['price'])}</b> "
                         f"{pct(d['price'], d['market'])} · {ago(d['ts'])}")
            pair += [{"text": f"✅ {i}", "callback_data": f"buy:{d['id']}:l"},
                     {"text": f"👎 {i}", "callback_data": f"skip:{d['id']}:l"}]
            if len(pair) == 4:
                kb.append(pair)
                pair = []
        if pair:
            kb.append(pair)
        lines.append("\n✅ — купил, 👎 — убрать из списка")
        return "\n".join(lines), {"inline_keyboard": kb}

    def send_deals(self, chat: str) -> None:
        self.tg.send(*self.deals_view(), chat_id=chat)

    def bought_view(self) -> tuple[str, dict | None]:
        rows = self.db.deals(("bought", "sold"), 30)
        if not rows:
            return "Покупок пока нет. Нажмите «✅ Купил» под находкой, и она появится здесь.", None
        spent = saved = profit = 0
        lines, kb, buttons = ["🛒 <b>Покупки</b>\n"], [], []
        for i, d in enumerate(rows, 1):
            spent += d["price"]
            gain = (d["market"] or d["price"]) - d["price"]
            saved += gain
            line = (f"{i}. <a href=\"{e(d['url'])}\">{e(d['model'])}</a> — {fmt_price(d['price'])}"
                    f" (рынок {fmt_price(d['market'])}, выгода {fmt_price(gain)})")
            if d["status"] == "sold":
                p = d["sold_price"] - d["price"]
                profit += p
                line += f"\n    💰 продан за {fmt_price(d['sold_price'])} → {'+' if p >= 0 else '−'}{fmt_price(abs(p))}"
            else:
                buttons.append({"text": f"💰 Продал {i}", "callback_data": f"sold:{d['id']}"})
            lines.append(line)
        lines.append(f"\nПотрачено: <b>{fmt_price(spent)}</b>\nДешевле рынка на: <b>{fmt_price(saved)}</b>")
        if profit:
            lines.append(f"Прибыль с продаж: <b>{'+' if profit >= 0 else '−'}{fmt_price(abs(profit))}</b>")
        for j in range(0, len(buttons), 3):
            kb.append(buttons[j:j + 3])
        return "\n".join(lines), {"inline_keyboard": kb} if kb else None

    def send_bought(self, chat: str) -> None:
        self.tg.send(*self.bought_view(), chat_id=chat)

    def cats_view(self) -> tuple[str, dict]:
        kb = [[{"text": f"{'✅' if self.st.cat_on(c) else '⬜'} {c.title}", "callback_data": f"cat:{c.id}"}]
              for c in CATEGORIES.values()]
        return ("📦 <b>Что отслеживать</b>\nНажмите, чтобы включить или выключить. "
                "Новая категория первые проходы собирает цены, потом начнёт присылать находки."), \
            {"inline_keyboard": kb}

    def send_prices(self, chat: str) -> None:
        lines = ["📈 <b>Рыночные цены</b> (медиана объявлений за 3 недели)\n"]
        for c in CATEGORIES.values():
            if not self.st.cat_on(c):
                continue
            rows = self.db.market_overview(c.id, 21, 8)
            lines.append(f"<b>{c.title}</b>")
            if not rows:
                lines.append("  пока собираю данные…")
            for name, price, n in rows:
                lines.append(f"  {e(name)} — {fmt_price(price)} <i>({n})</i>")
            lines.append("")
        self.tg.send("\n".join(lines), chat_id=chat)

    def settings_view(self) -> tuple[str, dict]:
        st, s = self.st, self.db.get("status") or {}
        state = "⏸ на паузе" if st["paused"] else "🟢 работает"
        if s.get("blocked") and not st["paused"]:
            left = max(0, int((s.get("until") or 0) - time.time())) // 60
            state = f"🔴 Авито ограничил доступ, повтор через {left} мин"
        today = self.db.deals_count_since(time.time() - 86400)
        text = (f"⚙️ <b>Настройки</b>\n\nСостояние: {state}\nПоследняя проверка: {ago(s.get('ts'))}"
                f" · распознано объявлений: {s.get('items', 0)}\nНаходок за сутки: {today}\n\n"
                "Нажмите на параметр, чтобы поменять:")
        r, b = st["min_rating"], st["min_battery"]
        kb = [
            [{"text": f"📍 Город: {CITIES.get(st['city'], st['city'])}", "callback_data": "city"}],
            [{"text": f"🚚 {'Только с Авито Доставкой' if st['delivery'] else 'С доставкой и без'}",
              "callback_data": "cyc:delivery"}],
            [{"text": f"💸 Дешевле рынка на: {st['discount']}%+", "callback_data": "cyc:discount"}],
            [{"text": f"📦 Состояние: {GRADE_LABEL[st['grade']]}", "callback_data": "cyc:grade"}],
            [{"text": f"⭐ Рейтинг продавца: {'от ' + str(r) if r else 'любой'}", "callback_data": "cyc:min_rating"}],
            [{"text": f"💬 Отзывов у продавца: {'от ' + str(st['min_reviews']) if st['min_reviews'] else 'любое число'}",
              "callback_data": "cyc:min_reviews"}],
            [{"text": f"🔋 АКБ: {'от ' + str(b) + '%' if b else 'не проверять'}", "callback_data": "cyc:min_battery"}],
            [{"text": f"⏱ Проверка: раз в {st['interval'] // 60} мин", "callback_data": "cyc:interval"}],
        ]
        return text, {"inline_keyboard": kb}

    def city_view(self) -> tuple[str, dict]:
        items = [{"text": ("• " if k == self.st["city"] else "") + v, "callback_data": f"city:{k}"}
                 for k, v in CITIES.items()]
        kb = [items[i:i + 2] for i in range(0, len(items), 2)]
        kb.append([{"text": "◀️ Назад", "callback_data": "settings"}])
        return "📍 Где искать?", {"inline_keyboard": kb}

    # ---------- inline-кнопки ----------
    def edit(self, chat: str, msg_id: int, view: tuple[str, dict | None]) -> None:
        text, kb = view
        params = {"chat_id": chat, "message_id": msg_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True}
        if kb:
            params["reply_markup"] = kb
        self.tg.call("editMessageText", **params)

    def on_callback(self, data: str, chat: str, msg_id: int) -> str | None:
        from .main import deal_keyboard
        parts = data.split(":")
        act = parts[0]
        if act in ("buy", "unbuy", "skip", "unskip"):
            deal_id = int(parts[1])
            d = self.db.deal(deal_id)
            if not d:
                return "Не нашёл"
            status = {"buy": "bought", "unbuy": "new", "skip": "skipped", "unskip": "new"}[act]
            self.db.set_deal(deal_id, status=status, bought_ts=time.time() if act == "buy" else None)
            if len(parts) > 2:  # нажали в списке находок
                self.edit(chat, msg_id, self.deals_view())
            else:
                self.tg.call("editMessageReplyMarkup", chat_id=chat, message_id=msg_id,
                             reply_markup=deal_keyboard(deal_id, d["url"], status))
            return {"bought": "Записал в покупки 🛒", "skipped": "Убрал", "new": "Вернул"}[status]
        if act == "sold":
            self.awaiting[chat] = int(parts[1])
            d = self.db.deal(int(parts[1]))
            self.tg.send(f"За сколько продали «{e(d['model'])}»? Напишите число.", chat_id=chat)
            return None
        if act == "cat":
            c = CATEGORIES[parts[1]]
            self.db.set(f"cat:{c.id}", not self.st.cat_on(c))
            self.edit(chat, msg_id, self.cats_view())
            self.wake.set()
            return "Включено" if self.st.cat_on(c) else "Выключено"
        if act == "cyc":
            key = parts[1]
            values = CYCLES[key]
            cur = self.st[key]
            self.st[key] = values[(values.index(cur) + 1) % len(values)] if cur in values else values[0]
            self.edit(chat, msg_id, self.settings_view())
            if key == "interval":
                self.wake.set()
            return None
        if act == "city":
            if len(parts) == 1:
                self.edit(chat, msg_id, self.city_view())
                return None
            self.st["city"] = parts[1]
            self.edit(chat, msg_id, self.settings_view())
            self.wake.set()
            return f"Город: {CITIES[parts[1]]}"
        if act == "settings":
            self.edit(chat, msg_id, self.settings_view())
        return None
