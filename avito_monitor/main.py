"""Точка входа: цикл мониторинга по категориям + Telegram-бот с кнопками."""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import threading
import time

import yaml

from .analysis import DAMAGE, analyze, find_flags
from .avito import AvitoClient, BlockedError, Item
from .catalog import CATEGORIES, Category, Model, classify
from .storage import Storage
from .telegram import Telegram, fmt_price, format_item

log = logging.getLogger("avito_monitor")

# Всё, что меняется кнопками в Telegram. Значения по умолчанию.
SETTINGS = {
    "city": "rossiya",        # вся Россия
    "delivery": True,         # только объявления с Авито Доставкой (важно, когда ищем по всей России)
    "discount": 20,           # % ниже рынка модели
    "grade": "excellent",     # excellent — новое/как новое/отличное; good — без дефектов; any — любое
    "min_rating": 4.5,        # рейтинг продавца (None — не проверять)
    "min_reviews": 0,         # минимум отзывов у продавца
    "min_battery": 85,        # АКБ для телефонов/ноутбуков (None — не проверять)
    "interval": 180,          # секунд между проходами
    "paused": False,
}

TECH = {
    "pages": 2,               # страниц выдачи на запрос
    "min_samples": 5,         # минимум объявлений модели для оценки рынка
    "history_days": 21,
    "reject_red_flags": ["iCloud", "заблокирован", "на запчасти", "копия", "реплика", "в залоге"],
    "min_score": 4,
}


class Settings:
    def __init__(self, db: Storage, overrides: dict | None = None):
        self.db = db
        self.overrides = overrides or {}

    def __getitem__(self, key: str):
        return self.db.get(key, self.overrides.get(key, SETTINGS.get(key)))

    def __setitem__(self, key: str, value) -> None:
        self.db.set(key, value)

    def cat_on(self, cat: Category) -> bool:
        return self.db.get(f"cat:{cat.id}", cat.enabled)

    def analysis_rules(self, cat: Category) -> dict:
        grade = self["grade"]
        return {
            "condition_grade": None if grade == "any" else grade,
            "allow_new": True,
            "min_seller_rating": self["min_rating"],
            "min_seller_reviews": self["min_reviews"],
            "min_battery": self["min_battery"] if cat.battery else None,
            "reject_red_flags": TECH["reject_red_flags"],
            "min_score": TECH["min_score"],
        }


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    tg = cfg.setdefault("telegram", {})
    tg["token"] = os.environ.get("TELEGRAM_TOKEN", tg.get("token"))
    if os.environ.get("TELEGRAM_CHAT_ID"):
        tg["chat_ids"] = [c.strip() for c in os.environ["TELEGRAM_CHAT_ID"].split(",")]
    if not tg.get("token") or not tg.get("chat_ids"):
        sys.exit("Нет токена бота или chat id. Запустите: python -m avito_monitor --setup")
    return cfg


def looks_broken(title: str) -> bool:
    red, _, _ = find_flags(title)
    return any(f in DAMAGE for f in red)


def deal_keyboard(deal_id: int, url: str, status: str = "new") -> dict:
    if status == "bought":
        row = [{"text": "✅ Куплено", "callback_data": "noop"},
               {"text": "↩️ Отменить", "callback_data": f"unbuy:{deal_id}"}]
    elif status == "skipped":
        row = [{"text": "👎 Скрыто", "callback_data": "noop"},
               {"text": "↩️ Вернуть", "callback_data": f"unskip:{deal_id}"}]
    else:
        row = [{"text": "✅ Купил", "callback_data": f"buy:{deal_id}"},
               {"text": "👎 Не интересно", "callback_data": f"skip:{deal_id}"}]
    return {"inline_keyboard": [[{"text": "🔗 Открыть на Авито", "url": url}], row]}


def process_category(client: AvitoClient, db: Storage, tg: Telegram, cat: Category, st: Settings) -> dict:
    city = st["city"]
    key = f"{cat.id}:{city}"
    found: dict[str, tuple[Item, Model]] = {}
    for url in cat.urls(city, st["delivery"]):
        for it in client.search(url, TECH["pages"]):
            if it.price and it.price >= cat.min_price:
                m = classify(cat, it.title)
                if m:
                    found.setdefault(it.id, (it, m))

    for it, m in found.values():
        if not looks_broken(it.title):  # битые не портят рыночную цену
            db.record_price(cat.id, it.id, m.name, m.variant, it.price)

    first_run = not db.has_any(key)
    sent = 0
    discount = st["discount"]
    for it, m in found.values():
        seen, old_price = db.seen_price(key, it.id)
        dropped = bool(seen and old_price and it.price < old_price)
        if (not seen or dropped) and not first_run:
            market, n, basis = db.market_for(cat.id, m.name, m.variant, TECH["history_days"], TECH["min_samples"])
            if market and it.price <= market * (1 - discount / 100):
                sent += notify_if_good(client, db, tg, cat, st, it, m, market, n, basis,
                                       old_price if dropped else None)
        db.mark_seen(key, it.id, it.price)
    db.commit()
    log.info("[%s] распознано объявлений: %d%s, отправлено: %d", cat.title, len(found),
             " (первый проход — собираю цены)" if first_run else "", sent)
    return {"items": len(found), "sent": sent}


def notify_if_good(client, db, tg, cat, st, it, m, market, n, basis, old_price) -> int:
    details = analysis = None
    try:
        details = client.details(it.url)
    except BlockedError:
        raise
    except Exception as e:
        log.warning("не удалось открыть %s: %s", it.url, e)
    if details:
        it.description = details.description
        analysis = analyze(it.title, details, st.analysis_rules(cat))
        if analysis.reject:
            log.info("[%s] отсеяно %s (%s): %s", cat.title, m.name, fmt_price(it.price), analysis.reject)
            return 0
    reason = f"на {(1 - it.price / market) * 100:.0f}% ниже рынка {basis} (по {n} объявл.)"
    if old_price:
        reason = "📉 цена снижена · " + reason
    deal_id = db.add_deal(cat=cat.id, item_id=it.id, model=f"{m.name} {m.variant or ''}".strip(),
                          title=it.title, url=it.url, price=it.price, market=market,
                          score=analysis.score if analysis else None)
    tg.send(format_item(cat.title, it, market, reason, old_price, details, analysis),
            markup=deal_keyboard(deal_id, it.url), preview=True)
    return 1


def monitor(client: AvitoClient, db: Storage, tg: Telegram, st: Settings, wake: threading.Event,
            once: bool = False) -> None:
    backoff = 0
    while True:
        if st["paused"] and not once:
            wake.wait(30)
            wake.clear()
            continue
        blocked = False
        total = {"items": 0, "sent": 0}
        for cat in [c for c in CATEGORIES.values() if st.cat_on(c)]:
            try:
                r = process_category(client, db, tg, cat, st)
                total = {k: total[k] + r[k] for k in total}
            except BlockedError as e:
                log.warning("Блокировка Авито: %s. Если включён VPN — выключите его для Termux.", e)
                blocked = True
                break
            except Exception as e:
                msg = str(e)
                if "Connection refused" in msg:
                    msg = "соединение отклонено (прокси или сеть не пускают на Авито)"
                elif "Max retries" in msg or "timed out" in msg:
                    msg = "нет соединения с Авито"
                log.error("[%s] ошибка: %s", cat.title, msg[:200])
                log.debug("подробности", exc_info=True)
            time.sleep(random.uniform(4, 9))
        status = {"ts": time.time(), "blocked": blocked, **total}
        if once:
            db.set("status", status)
            return
        if blocked:
            backoff = min(backoff * 2 or 300, 3600)
            if backoff == 300 and not db.get("block_warned"):
                db.set("block_warned", True)
                tg.send("⚠️ Авито не пускает (ошибка 439). Почти всегда причина — VPN: Авито режет зарубежные IP.\n"
                        "Выключите VPN для Termux или включите в VPN-приложении обход российских сайтов. "
                        f"Повторю через {backoff // 60} мин.")
            elif backoff >= 1200:
                tg.send(f"⚠️ Авито блокирует запросы, пауза {backoff // 60} мин. "
                        "Выключите VPN или переключитесь на мобильный интернет.")
            status["until"] = time.time() + backoff
            db.set("status", status)
            wake.wait(backoff)
        else:
            backoff = 0
            db.set("block_warned", False)
            db.set("status", status)
            wake.wait(st["interval"] * random.uniform(0.8, 1.2))
        wake.clear()


def main() -> None:
    ap = argparse.ArgumentParser(description="Мониторинг Авито с уведомлениями в Telegram")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--once", action="store_true", help="один проход и выход")
    ap.add_argument("--test-telegram", action="store_true", help="отправить тестовое сообщение")
    ap.add_argument("--setup", action="store_true", help="настройка (токен бота)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    if args.setup or not os.path.exists(args.config):
        from .setup_wizard import run as setup
        setup(args.config)
        if args.setup:
            return
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    cfg = load_config(args.config)
    tg = Telegram(cfg["telegram"]["token"], cfg["telegram"]["chat_ids"], proxy=cfg["telegram"].get("proxy"))
    if args.test_telegram:
        tg.send("✅ Avito monitor: связь с Telegram работает")
        return
    db = Storage(cfg.get("db", "avito_monitor.db"))
    st = Settings(db, cfg.get("settings"))
    wake = threading.Event()
    client = AvitoClient(proxy=cfg.get("proxy"))

    from .bot import Bot
    bot = Bot(tg, db, st, wake)
    if not args.once:
        threading.Thread(target=bot.poll, daemon=True).start()
        bot.hello()
    cats = [c.title for c in CATEGORIES.values() if st.cat_on(c)]
    log.info("Запуск: %s; город %s", ", ".join(cats), st["city"])
    try:
        monitor(client, db, tg, st, wake, once=args.once)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
