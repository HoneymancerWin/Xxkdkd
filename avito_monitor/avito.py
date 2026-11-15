"""Загрузка и разбор поисковой выдачи Авито."""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from .analysis import Details

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

# 439 — собственный код Авито «слишком много запросов / похоже на бота».
BLOCK_CODES = {403, 429, 439}


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


def _parse_rating(text: str) -> float | None:
    m = re.search(r"\b([0-5][,.]\d)\b", text)
    return float(m.group(1).replace(",", ".")) if m else None


def _parse_reviews(text: str) -> int | None:
    m = re.search(r"(\d[\d\s ]*)\s*отзыв", text)
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def parse_item_page(html: str) -> Details:
    soup = BeautifulSoup(html, "html.parser")
    d = Details()

    def txt(*selectors: str) -> str:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return el.get_text("\n" if "description" in sel else " ", strip=True)
        return ""

    d.description = txt('[data-marker="item-view/item-description"]', '[itemprop="description"]',
                        '[class*="item-description"]')

    params_root = soup.select_one('[data-marker="item-view/item-params"]') or soup.select_one("#bx_item-params")
    for li in params_root.select("li") if params_root else []:
        line = li.get_text(" ", strip=True)
        if ":" in line:
            k, v = line.split(":", 1)
            d.params[k.strip()] = v.strip()
    d.condition = next((v for k, v in d.params.items() if k.lower().startswith("состояние")), "")

    seller = (soup.select_one('[data-marker="seller-info"]') or soup.select_one('[data-marker*="seller-info"]')
              or soup.select_one('[class*="seller-info"]'))
    seller_text = seller.get_text(" ", strip=True) if seller else ""
    d.seller_name = txt('[data-marker="seller-info/name"]', '[data-marker="seller-link/link"]')
    d.seller_type = txt('[data-marker="seller-info/label"]')
    if not d.seller_type:
        for t in ("Частное лицо", "Компания", "Магазин", "Реквизиты проверены"):
            if t in seller_text:
                d.seller_type = t
                break
    score_text = txt('[data-marker="seller-info/score"]', '[data-marker="seller-rating/score"]')
    d.seller_rating = _parse_rating(score_text or seller_text)
    reviews_text = txt('[data-marker="rating-caption/rating"]', '[data-marker="seller-info/summary"]')
    d.seller_reviews = _parse_reviews(reviews_text or seller_text)
    if d.seller_reviews is None and re.search(r"нет отзывов", seller_text, re.I):
        d.seller_reviews = 0
    m = re.search(r"(?:На Авито|На сайте) с ([^·\n]{3,20}?\d{4})", seller_text)
    d.seller_since = m.group(1).strip() if m else ""
    return d


def normalize_url(url: str) -> str:
    """Ссылки с телефона (m.avito.ru, без https) → полная версия сайта."""
    url = url.strip()
    m = re.search(r"(?:https?://)?(?:www\.|m\.)?avito\.ru\S*", url)  # ссылку могли вставить с текстом
    if m:
        url = m.group(0)
    if not url.startswith("http"):
        url = "https://" + url
    url = re.sub(r"^https?://(?:m\.|www\.)?avito\.ru", "https://www.avito.ru", url)
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    query.pop("context", None)
    path = parts.path.rstrip("/")
    segs = [p for p in path.split("/") if p]
    # Ссылка на одно объявление (/город/категория/название_123456789) → поиск по названию.
    m = re.fullmatch(r"(.+)_(\d{7,})", segs[-1]) if len(segs) >= 3 else None
    if m:
        path = "/" + "/".join(segs[:-1])
        query = {"q": m.group(1).replace("_", " ")}
    query.setdefault("s", "104")  # сортировка по дате — новые сверху
    return urlunparse(parts._replace(path=path, query=urlencode(query), fragment=""))


def is_item_url(url: str) -> bool:
    segs = [p for p in urlparse(url.split("#")[0]).path.split("/") if p]
    return len(segs) >= 3 and re.fullmatch(r".+_\d{7,}", segs[-1]) is not None


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
        self._warmed = False
        self._referer = BASE_URL + "/"

    def _warm_up(self) -> None:
        """Как живой человек: сначала главная страница (получаем cookies), потом поиск."""
        if self._warmed:
            return
        self._warmed = True
        try:
            self.session.get(BASE_URL + "/", timeout=self.timeout,
                             headers={"Sec-Fetch-Site": "none"}, **_IMPERSONATE)
            time.sleep(random.uniform(2, 4))
        except Exception as e:  # не критично
            log.debug("warm-up: %s", e)

    def fetch(self, url: str) -> str:
        self._warm_up()
        resp = self.session.get(url, timeout=self.timeout, headers={"Referer": self._referer},
                                **_IMPERSONATE)
        self._referer = url
        if resp.status_code in BLOCK_CODES:
            self._warmed = False  # после паузы начнём «сессию» заново
            self.session.cookies.clear()
            raise BlockedError(f"Авито ограничил доступ (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} на {url}")
        text = resp.text
        if "firewall" in text[:5000].lower() and 'data-marker="item' not in text:
            raise BlockedError(f"Капча/фаервол на {url}")
        return text

    def details(self, url: str) -> Details:
        time.sleep(random.uniform(*self.delay))
        return parse_item_page(self.fetch(url))

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
