"""Настройка прокси: python -m avito_monitor.proxy_cmd avito|telegram <прокси|off|check>.

Понимает форматы, в которых прокси обычно выдают продавцы:
  ip:port:login:password · login:password@ip:port · http://... · socks5://...
"""
from __future__ import annotations

import re
import sys

import requests
import yaml

CONFIG = "config.yaml"


def normalize(raw: str) -> str:
    raw = raw.strip()
    scheme = "http"
    m = re.match(r"^(https?|socks5h?|socks4)://(.+)$", raw, re.I)
    if m:
        scheme, raw = m.group(1).lower(), m.group(2)
    if scheme == "socks5":
        scheme = "socks5h"  # DNS тоже через прокси
    if "@" not in raw:
        parts = raw.split(":")
        if len(parts) == 4:  # ip:port:login:password
            ip, port, login, pwd = parts
            raw = f"{login}:{pwd}@{ip}:{port}"
    return f"{scheme}://{raw}"


def hide(url: str) -> str:
    return re.sub(r"//([^:@/]+):([^@/]+)@", r"//\1:***@", url)


def check(proxy: str | None) -> bool:
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        info = requests.get("http://ip-api.com/json/?fields=query,country,city,isp,mobile,hosting",
                            proxies=proxies, timeout=20).json()
        kind = "мобильный" if info.get("mobile") else "дата-центр" if info.get("hosting") else "домашний"
        print(f"  IP: {info.get('query')} · {info.get('country')}, {info.get('city')} · {info.get('isp')} ({kind})")
        if info.get("country") != "Russia":
            print("  ⚠️ IP не российский — Авито, скорее всего, не пустит.")
    except Exception as e:
        print(f"  ❌ Прокси не отвечает: {e.__class__.__name__}. Проверьте адрес, порт, логин и пароль.")
        return False
    try:
        r = requests.get("https://www.avito.ru/rossiya?q=iphone", proxies=proxies, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9"})
        if r.status_code == 200 and 'data-marker="item' in r.text:
            print("  ✅ Авито открывается, объявления видны.")
            return True
        print(f"  ❌ Авито ответил кодом {r.status_code} — этот IP он не пускает. Нужен другой прокси.")
    except Exception as e:
        print(f"  ❌ Не удалось открыть Авито: {e.__class__.__name__}")
    return False


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    value = sys.argv[2] if len(sys.argv) > 2 else "check"
    if target not in ("avito", "telegram"):
        sys.exit("Использование: avito proxy <прокси|off|check>  или  avito tgproxy <прокси|off>")
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    section = cfg if target == "avito" else cfg.setdefault("telegram", {})

    if value == "check":
        cur = section.get("proxy")
        print(f"Сейчас: {hide(cur) if cur else 'без прокси'}")
        if target == "avito":
            check(cur)
        return
    if value == "off":
        section.pop("proxy", None)
        print(f"Прокси для {'Авито' if target == 'avito' else 'Telegram'} выключен.")
    else:
        url = normalize(value)
        print(f"Прокси: {hide(url)}")
        if target == "avito":
            print("Проверяю…")
            if not check(url):
                print("Всё равно сохранил — можно поменять командой ещё раз.")
        section["proxy"] = url
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print("Сохранено, перезапускаю бота.")


if __name__ == "__main__":
    main()
