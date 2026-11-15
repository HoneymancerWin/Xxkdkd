"""Точка входа: цикл мониторинга."""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time

import yaml

from .analysis import analyze
from .avito import AvitoClient, BlockedError, Item
from .market import market_price
from .storage import Storage
from .telegram import Telegram, fmt_price, format_item

log = logging.getLogger("avito_monitor")

DEFAULTS = {
    "pages": 2,              # сколько страниц выдачи читать
    "discount": None,        # % ниже рынка, чтобы считать выгодным
    "max_price": None,       # абсолютный потолок цены
    "min_price": None,       # отсекать мусор/«цены за 1 ₽»
    "include": [],           # все слова должны быть в заголовке/описании
    "exclude": [],           # ни одного из этих слов
    "market_price": None,    # рыночная цена вручную (иначе считается по выдаче)
    "min_samples": 15,       # минимум цен для оценки рынка
    "history_days": 14,      # окно истории цен
    "notify_price_drops": True,
    "notify_on_first_run": False,
    # --- анализ страницы объявления ---
    "details": True,             # открывать объявление: описание, состояние, продавец
    "conditions": [],            # допустимые состояния, напр. ["Новое", "Б/у"]; пусто = любые
    "min_seller_rating": None,   # напр. 4.5
    "min_seller_reviews": None,  # напр. 3
    "seller_types": [],          # напр. ["Частное лицо"]
    "reject_red_flags": [],      # отсеивать при этих признаках, напр. ["iCloud", "предоплата"]
    "min_score": None,           # минимальная оценка сделки 0–10
    "condition_grade": None,     # "excellent" — только отличное/идеальное, "good" — без дефектов
    "allow_new": True,           # false — отсеивать новые
    "allow_unknown_condition": False,  # пропускать, если продавец не описал состояние
    "min_battery": None,         # минимальное здоровье АКБ, %
    "require_battery": False,    # отсеивать, если процент АКБ не указан
}


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    tg = cfg.setdefault("telegram", {})
    tg["token"] = os.environ.get("TELEGRAM_TOKEN", tg.get("token"))
    if os.environ.get("TELEGRAM_CHAT_ID"):
        tg["chat_ids"] = [c.strip() for c in os.environ["TELEGRAM_CHAT_ID"].split(",")]
    if not tg.get("token") or not tg.get("chat_ids"):
        sys.exit("Укажите telegram.token и telegram.chat_ids в конфиге (или TELEGRAM_TOKEN / TELEGRAM_CHAT_ID)")
    if not cfg.get("searches"):
        sys.exit("В конфиге нет ни одного поиска (searches)")
    base = {**DEFAULTS, **(cfg.get("defaults") or {})}
    cfg["searches"] = [{**base, **s} for s in cfg["searches"]]
    for s in cfg["searches"]:
        s.setdefault("name", s["url"])
        s["include"] = [w.lower() for w in s["include"] or []]
        s["exclude"] = [w.lower() for w in s["exclude"] or []]
    return cfg


def matches_words(item: Item, s: dict) -> bool:
    text = f"{item.title} {item.description}".lower()
    if any(w not in text for w in s["include"]):
        return False
    return not any(w in text for w in s["exclude"])


def is_deal(item: Item, s: dict, market: float | None) -> tuple[bool, str]:
    """Возвращает (подходит ли, пояснение)."""
    p = item.price
    if p is None:
        return False, "нет цены"
    if s["min_price"] and p < s["min_price"]:
        return False, "ниже min_price"
    reasons = []
    if s["max_price"]:
        if p > s["max_price"]:
            return False, "выше max_price"
        reasons.append(f"≤ {fmt_price(s['max_price'])}")
    if s["discount"]:
        if market is None:
            return False, "мало данных о рынке"
        threshold = market * (1 - s["discount"] / 100)
        if p > threshold:
            return False, "не ниже рынка"
        reasons.append(f"на {s['discount']}%+ ниже рынка")
    return True, ", ".join(reasons) or "новое объявление"


def process_search(client: AvitoClient, db: Storage, tg: Telegram, s: dict) -> None:
    name = s["name"]
    items = [i for i in client.search(s["url"], s["pages"]) if matches_words(i, s)]

    for it in items:
        if it.price and (not s["min_price"] or it.price >= s["min_price"]):
            db.record_price(name, it.id, it.price)
    history = db.recent_prices(name, s["history_days"])
    if s["market_price"]:
        market = float(s["market_price"])
    else:
        market = market_price(history) if len(history) >= s["min_samples"] else None

    first_run = not db.has_any(name)
    sent = 0
    for it in items:
        seen, old_price = db.seen_price(name, it.id)
        dropped = (seen and s["notify_price_drops"] and old_price and it.price
                   and it.price < old_price)
        if (not seen or dropped) and not (first_run and not s["notify_on_first_run"]):
            ok, reason = is_deal(it, s, market)
            details = analysis = None
            if ok and s["details"]:
                try:
                    details = client.details(it.url)
                except BlockedError:
                    raise
                except Exception as e:
                    log.warning("[%s] не удалось открыть %s: %s", name, it.url, e)
                if details:
                    it.description = details.description
                    analysis = analyze(it.title, details, s)
                    if not matches_words(it, s):
                        ok, why = False, "стоп-слово в описании"
                    elif analysis.reject:
                        ok, why = False, analysis.reject
                    if not ok:
                        log.info("[%s] отсеяно %s: %s", name, it.url, why)
            if ok:
                if dropped:
                    reason = "📉 цена снижена · " + reason
                tg.send(format_item(name, it, market, reason, old_price if dropped else None,
                                    details, analysis))
                sent += 1
        db.mark_seen(name, it.id, it.price)
    db.commit()
    log.info("[%s] объявлений: %d, рынок: %s, история: %d, отправлено: %d%s",
             name, len(items), fmt_price(market), len(history), sent,
             " (первый запуск — только запоминаю)" if first_run else "")


def run(cfg: dict, once: bool = False) -> None:
    client = AvitoClient(proxy=cfg.get("proxy"))
    db = Storage(cfg.get("db", "avito_monitor.db"))
    tg = Telegram(cfg["telegram"]["token"], cfg["telegram"]["chat_ids"],
                  proxy=cfg["telegram"].get("proxy"))
    interval = cfg.get("interval", 180)
    backoff = 0
    while True:
        blocked = False
        for s in cfg["searches"]:
            try:
                process_search(client, db, tg, s)
            except BlockedError as e:
                log.warning("Блокировка Авито: %s", e)
                blocked = True
                break
            except Exception:
                log.exception("[%s] ошибка", s["name"])
            time.sleep(random.uniform(4, 9))
        if once:
            return
        if blocked:
            backoff = min(backoff * 2 or 300, 3600)
            if backoff >= 1200:
                tg.send(f"⚠️ Авито блокирует запросы, пауза {backoff // 60} мин. Подумайте о прокси.")
            log.info("Пауза %d с из-за блокировки", backoff)
            time.sleep(backoff)
            continue
        backoff = 0
        time.sleep(interval * random.uniform(0.8, 1.2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Мониторинг Авито с уведомлениями в Telegram")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--once", action="store_true", help="один проход и выход")
    ap.add_argument("--test-telegram", action="store_true", help="отправить тестовое сообщение")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    cfg = load_config(args.config)
    if args.test_telegram:
        Telegram(cfg["telegram"]["token"], cfg["telegram"]["chat_ids"],
                 proxy=cfg["telegram"].get("proxy")).send("✅ Avito monitor: связь с Telegram работает")
        return
    log.info("Запуск: %d поиск(ов), интервал %s с", len(cfg["searches"]), cfg.get("interval", 180))
    try:
        run(cfg, once=args.once)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
