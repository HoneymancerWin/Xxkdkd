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


def normalize(raw: str, scheme: str = "http") -> str:
    raw = raw.strip()
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


def explain(e: Exception, proxy: str) -> str:
    text = str(e)
    pwd = re.search(r"//[^:@/]+:([^@/]+)@", proxy or "")
    if pwd:
        text = text.replace(pwd.group(1), "***")
    if "407" in text:
        return "неверный логин или пароль (407)"
    if "timed out" in text.lower() or "timeout" in e.__class__.__name__.lower():
        return "прокси не отвечает по времени (не тот порт или прокси ещё не активирован)"
    if "refused" in text.lower():
        return "порт закрыт (не тот порт или тип прокси)"
    if "SOCKS" in text or "socks" in text:
        return "ошибка SOCKS: " + text[-120:]
    return f"{e.__class__.__name__}: {text[-160:]}"


def reachable(proxy: str) -> str | None:
    """None — прокси работает, иначе текст ошибки."""
    try:
        requests.get("http://ip-api.com/json/", proxies={"http": proxy, "https": proxy}, timeout=15)
        return None
    except Exception as e:
        return explain(e, proxy)


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
        print(f"  ❌ Прокси не отвечает: {explain(e, proxy)}")
        return False
    # 1) работает ли HTTPS вообще
    for site in ("https://ya.ru", "https://www.google.com"):
        try:
            requests.get(site, proxies=proxies, timeout=20)
            print(f"  ✅ HTTPS через прокси работает ({site[8:]})")
            break
        except Exception as e:
            print(f"  ⚠️ {site[8:]}: {explain(e, proxy)}")
    else:
        print("  ❌ Через прокси не открываются HTTPS-сайты. Это ограничение прокси — напишите продавцу.")
        return False
    # 2) пускает ли продавец прокси на Авито (обычный http, без шифрования)
    try:
        requests.get("http://www.avito.ru/", proxies=proxies, timeout=20, allow_redirects=False)
    except Exception as e:
        print(f"  ❌ Прокси не пускает на avito.ru: {explain(e, proxy)}")
        print("     Похоже, продавец блокирует Авито на этом прокси. Попросите замену «под Авито».")
        return False
    # 3) так же, как ходит сам бот
    from .avito import AvitoClient, BlockedError, parse_search_page
    client = AvitoClient(proxy=proxy, delay=(1, 2))
    try:
        items = parse_search_page(client.fetch("https://www.avito.ru/rossiya?q=iphone&s=104"))
        if items:
            print(f"  ✅ Авито открывается, объявлений на странице: {len(items)}")
            return True
        print("  ⚠️ Авито открылся, но объявлений не видно — пришлите скриншот разработчику.")
    except BlockedError as e:
        print(f"  ❌ {e} — этот IP Авито не пускает. Нужен другой прокси (лучше мобильный).")
    except Exception as e:
        print(f"  ❌ Не удалось открыть Авито: {explain(e, proxy)}")
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
        explicit = re.match(r"^(https?|socks5h?|socks4)://", value.strip(), re.I)
        url = normalize(value)
        if not explicit:  # тип не указан — пробуем HTTP, потом SOCKS5
            print("Определяю тип прокси…")
            errors = {}
            for scheme in ("http", "socks5h"):
                candidate = normalize(value, scheme)
                err = reachable(candidate)
                if err is None:
                    url = candidate
                    print(f"  тип: {'HTTP' if scheme == 'http' else 'SOCKS5'} — работает")
                    break
                errors[scheme] = err
            else:
                print("  ❌ Не подключается ни как HTTP, ни как SOCKS5:")
                for k, v in errors.items():
                    print(f"     {'HTTP' if k == 'http' else 'SOCKS5'}: {v}")
        print(f"Прокси: {hide(url)}")
        if target == "avito":
            print("Проверяю Авито…")
            if not check(url):
                print("Всё равно сохранил — можно поменять командой ещё раз.")
        section["proxy"] = url
    with open(CONFIG, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print("Сохранено, перезапускаю бота.")


if __name__ == "__main__":
    main()
