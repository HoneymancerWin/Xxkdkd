"""Интерактивная настройка: удобно с телефона, без редактирования файлов."""
from __future__ import annotations

import os
import time

import requests
import yaml


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        v = input(f"{prompt}{suffix}: ").strip()
        if v or default is not None:
            return v or default
        print("  Нужно ввести значение.")


def detect_chat_id(token: str) -> str | None:
    api = f"https://api.telegram.org/bot{token}"
    try:
        me = requests.get(f"{api}/getMe", timeout=20).json()
    except requests.RequestException as e:
        print(f"  Не удалось связаться с Telegram: {e}")
        return None
    if not me.get("ok"):
        print("  Telegram не принял токен — проверьте, что скопировали его целиком.")
        return None
    name = me["result"]["username"]
    print(f"\n  Бот @{name} найден. Откройте его в Telegram и нажмите «Старт» (или напишите ему что угодно).")
    print("  Жду сообщение до 2 минут...")
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            upd = requests.get(f"{api}/getUpdates", params={"timeout": 20}, timeout=30).json()
        except requests.RequestException:
            time.sleep(3)
            continue
        for u in reversed(upd.get("result", [])):
            msg = u.get("message") or u.get("my_chat_member") or {}
            chat = msg.get("chat")
            if chat:
                print(f"  Готово, ваш chat id: {chat['id']}")
                return str(chat["id"])
        time.sleep(2)
    return None


def run(path: str = "config.yaml") -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    example = os.path.join(here, "config.example.yaml")
    with open(example, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    print("=== Настройка Avito-монитора ===\n")
    print("1) В Telegram откройте @BotFather → /newbot → придумайте имя и логин (…bot).")
    print("   Он пришлёт токен вида 7123456789:AAH... — скопируйте и вставьте сюда.\n")
    token = ask("Токен бота")
    chat_id = detect_chat_id(token) or ask("Не удалось определить автоматически. Введите chat id (узнать у @userinfobot)")
    cfg["telegram"] = {"token": token, "chat_ids": [int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id]}

    print("\n2) Поиски. Откройте avito.ru в браузере (Chrome), найдите товар, выставьте фильтры")
    print("   и сортировку «По дате», скопируйте ссылку из адресной строки и вставьте сюда.\n")
    searches = []
    while True:
        from .avito import normalize_url
        from .avito import is_item_url
        raw = ask("Ссылка на поиск Авито")
        url = normalize_url(raw)
        if is_item_url(raw):
            print("  Это ссылка на одно объявление, а нужна на поиск. Сделал поиск по его названию:")
        print(f"  → {url}")
        name = ask("Как назвать этот поиск", "Поиск " + str(len(searches) + 1))
        s = {"name": name, "url": url}
        mp = ask("Рыночная цена в рублях (Enter — бот посчитает сам)", "")
        if mp:
            s["market_price"] = int("".join(ch for ch in mp if ch.isdigit()))
        s["discount"] = int(ask("Насколько % ниже рынка присылать", "20"))
        minp = ask("Минимальная цена, дешевле — мусор/скам (Enter — без ограничения)", "")
        if minp:
            s["min_price"] = int("".join(ch for ch in minp if ch.isdigit()))
        if ask("Только отличное/идеальное/новое состояние? (да/нет)", "да").lower().startswith("д"):
            s["condition_grade"] = "excellent"
        bat = ask("Минимальный % АКБ (для телефонов; Enter — не проверять)", "")
        if bat:
            s["min_battery"] = int(bat)
        searches.append(s)
        if not ask("Добавить ещё поиск? (да/нет)", "нет").lower().startswith("д"):
            break
    cfg["searches"] = searches

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"\nСохранено в {path}. Поменять настройки позже: python -m avito_monitor --setup")
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": cfg["telegram"]["chat_ids"][0],
                            "text": f"✅ Avito monitor настроен: поисков — {len(searches)}"}, timeout=20)
    except requests.RequestException:
        pass
