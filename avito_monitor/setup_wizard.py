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
    print("=== Настройка Avito-монитора ===\n")
    print("Нужен только токен Telegram-бота. Всё остальное (категории, город, скидка,")
    print("состояние, продавец) настраивается кнопками прямо в Telegram.\n")
    print("В Telegram откройте @BotFather → /newbot → придумайте имя и логин (…bot).")
    print("Он пришлёт токен вида 7123456789:AAH... — скопируйте и вставьте сюда.\n")
    while True:
        token = ask("Токен бота").strip()
        chat_id = detect_chat_id(token)
        if chat_id:
            break
        if ask("Не получилось. Ввести chat id вручную (узнать у @userinfobot)? (да/нет)", "нет").lower().startswith("д"):
            chat_id = ask("chat id")
            break

    cfg = {"telegram": {"token": token, "chat_ids": [int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id]}}
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"\nГотово! Сохранено в {path}. Дальше — кнопки в Telegram.")
