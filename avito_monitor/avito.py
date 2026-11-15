"""Загрузка и разбор поисковой выдачи Авито."""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://www.avito.ru"

try:  # curl_cffi притворяется настоящим Chrome — Авито реже блокирует
    from curl_cffi import requests as http

    _IMPERSONATE = {"impersonate": "chrome"}
except ImportError:  # pragma: no cover
    import requests as http

    _IMPERSONATE = {}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class BlockedError(RuntimeError):
    """Авито отдал 403/429 или страницу с капчей."""


@dataclass
class Item:
    id: str
    title: str
    price: int | None
    url: str
    location: str = ""
    date: str = ""
    description: str = ""


def _digits(text: str | None) -> int | None:
    if not text:
        return None
    d = re.sub(r"\D", "", text)
    return int(d) if d else None


def parse_search_page(html: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[Item] = []
    for node in soup.select('[data-marker="item"]'):
        item_id = node.get("data-item-id") or node.get("id", "").lstrip("i")
        link = node.select_one('a[data-marker="item-title"]') or node.select_one("a[href]")
        if not item_id or not link:
            continue
        title = (link.get("title") or link.get_text(" ", strip=True)).strip()

        price = None
        meta = node.select_one('meta[itemprop="price"]')
        if meta is not None:
            price = _digits(meta.get("content"))
        if price is None:
            p = node.select_one('[data-marker="item-price"]')
            price = _digits(p.get_text(" ", strip=True)) if p else None

        def text_of(selector: str) -> str:
            el = node.select_one(selector)
            return el.get_text(" ", strip=True) if el else ""

        items.append(
            Item(
                id=str(item_id),
                title=title,
                price=price,
                url=urljoin(BASE_URL, link.get("href", "")),
                location=text_of('[data-marker="item-address"]') or text_of('[class*="geo-root"]'),
                date=text_of('[data-marker="item-date"]'),
                description=text_of('[class*="item-description"]') or text_of('meta[itemprop="description"]'),
            )
        )
    return items


def _with_page(url: str, page: int) -> str:
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    if page > 1:
        query["p"] = str(page)
    else:
        query.pop("p", None)
    return urlunparse(parts._replace(query=urlencode(query)))


class AvitoClient:
    def __init__(self, proxy: str | None = None, timeout: int = 30, delay: tuple[float, float] = (3, 7)):
        self.session = http.Session()
        self.session.headers.update(HEADERS)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self.timeout = timeout
        self.delay = delay

    def fetch(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout, **_IMPERSONATE)
        if resp.status_code in (403, 429):
            raise BlockedError(f"HTTP {resp.status_code} на {url}")
        resp.raise_for_status()
        text = resp.text
        if "firewall" in text[:5000].lower() and 'data-marker="item"' not in text:
            raise BlockedError(f"Капча/фаервол на {url}")
        return text

    def search(self, url: str, pages: int = 1) -> list[Item]:
        result: dict[str, Item] = {}
        for page in range(1, pages + 1):
            if page > 1:
                time.sleep(random.uniform(*self.delay))
            items = parse_search_page(self.fetch(_with_page(url, page)))
            log.debug("%s стр.%d: %d объявлений", url, page, len(items))
            if not items:
                break
            for it in items:
                result.setdefault(it.id, it)
        return list(result.values())
