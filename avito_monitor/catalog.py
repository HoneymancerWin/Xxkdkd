"""Категории товаров и определение модели по названию объявления.

Модель нужна, чтобы считать рынок честно: iPhone 13 128GB сравнивается с другими
iPhone 13 128GB, а не со всеми айфонами подряд.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlencode

CITIES = {
    "moskva": "Москва",
    "moskva_i_mo": "Москва и область",
    "sankt-peterburg": "Санкт-Петербург",
    "rossiya": "Вся Россия",
    "ekaterinburg": "Екатеринбург",
    "novosibirsk": "Новосибирск",
    "kazan": "Казань",
    "nizhniy_novgorod": "Нижний Новгород",
    "krasnodar": "Краснодар",
    "rostov-na-donu": "Ростов-на-Дону",
    "samara": "Самара",
    "chelyabinsk": "Челябинск",
}

# Объявления, где это слово стоит ДО названия модели, — аксессуары и услуги:
# «Чехол для iPhone 13», «Геймпад для PS5», «Ремонт MacBook». А «PS5 + 2 геймпада» — нормально.
ACCESSORY_WORDS = (
    "чехол", "чехл", "стекло", "защитн", "пленк", "кейс", "бампер", "накладк", "коробк", "зарядк",
    "кабель", "адаптер", "блок питания", "наушник", "ремешок", "геймпад", "джойстик", "контроллер",
    "dualsense", "dualshock", "игра", "игры", "диск", "подписк", "аккаунт", "ремонт", "замена", "дисплей",
    "экран", "матриц", "аккумулятор", "батаре", "корпус", "плата", "шлейф", "клавиатур", "подставк",
    "док-станц", "док станц", "сумк", "рюкзак", "держател", "кронштейн", "наклейк", "скин", "стилус",
    "мышь", "камера для", "запчаст", "разбор", "крышк", "сим-лоток", "лоток", "динамик", "кнопк",
)
# Такие объявления отбрасываются, где бы ни стояло слово.
ALWAYS_SKIP = ("куплю", "выкуп", "скупка", "скупаем", "аренд", "прокат", "в рассрочку без", "обмен на ")


def _norm(title: str) -> str:
    t = title.lower().replace("ё", "е")
    for a, b in (("айфон", "iphone"), ("эпл", "apple"), ("макбук", "macbook"), ("мак бук", "macbook"),
                 ("пиксель", "pixel"), ("пиксел", "pixel"), ("гугл", "google"), ("стим дек", "steam deck"),
                 ("стимдек", "steam deck"), ("steamdeck", "steam deck"), ("олед", "oled"), ("лсд", "lcd"),
                 ("иксбокс", "xbox"), ("хбокс", "xbox"), ("x-box", "xbox"), ("сериес", "series"),
                 ("сериа", "series"), ("плейстейшн", "playstation"), ("плейстейшен", "playstation"),
                 ("плэйстейшн", "playstation"), ("плэйстейшен", "playstation"), ("сони ", "sony "),
                 ("про макс", "pro max"), (" про", " pro"), ("плюс", "plus"), ("мини", "mini"),
                 ("слим", "slim"), ("эйр", "air"), ("гб", "gb"), ("тб", "tb")):
        t = t.replace(a, b)
    t = re.sub(r"\bм(\d)", r"m\1", t)  # «М1» кириллицей
    return t


def storage_of(t: str) -> str | None:
    m = re.search(r"\b\d{1,2}\s*/\s*(\d{2,4})\b", t)  # «8/256»
    if m and int(m.group(1)) in (32, 64, 128, 256, 512):
        return f"{m.group(1)}GB"
    m = re.search(r"\b(1|2)\s*tb\b", t)
    if m:
        return f"{m.group(1)}TB"
    m = re.search(r"\b(32|64|128|256|512)\s*(?:gb|g\b|гиг)", t) or re.search(r"\b(64|128|256|512)\b", t)
    return f"{m.group(1)}GB" if m else None


@dataclass
class Model:
    name: str               # «iPhone 13 Pro»
    variant: str | None     # «256GB» — уточнение для рынка (если указано)
    pos: int                # где в названии нашлась модель


def _iphone(t: str) -> Model | None:
    m = re.search(r"iphone\s*(\d{1,2}|xs|xr|x|se)(?:\s*(pro\s*max|pro|plus|max|mini|e)\b)?", t)
    if not m:
        return None
    gen = m.group(1).upper()
    if gen.isdigit() and not 6 <= int(gen) <= 20:
        return None
    var = (m.group(2) or "").replace("  ", " ")
    name = f"iPhone {gen}" + (f" {var.title()}" if var else "")
    return Model(name, storage_of(t), m.start())


def _pixel(t: str) -> Model | None:
    m = re.search(r"pixel\s*(\d{1,2}a?|fold)(?:\s*(pro\s*xl|pro\s*fold|pro|xl|a)\b)?", t)
    if not m:
        return None
    var = m.group(2) or ""
    return Model(f"Pixel {m.group(1)}" + (f" {var.title().replace('Xl', 'XL')}" if var else ""), storage_of(t), m.start())


def _macbook(t: str) -> Model | None:
    m = re.search(r"macbook\s*(air|pro)?", t)
    if not m:
        return None
    kind = (m.group(1) or "").title()
    chip = re.search(r"\bm([1-6])\s*(pro|max|ultra)?\b", t)
    if chip:
        cpu = f"M{chip.group(1)}" + (f" {chip.group(2).title()}" if chip.group(2) else "")
    else:
        y = re.search(r"\b(20[12]\d)\b", t)
        cpu = f"Intel {y.group(1)}" if y else "Intel"
    size = (re.search(r"\b(13|14|15|16)(?:[.,]\d)?\s*(?:\"|''|”|дюйм|inch|in\b)", t)
            or re.search(r"macbook\s*(?:air|pro)?\s*(13|14|15|16)\b", t))
    name = " ".join(x for x in ("MacBook", kind, cpu) if x)
    return Model(name, f'{size.group(1)}"' if size else None, m.start())


def _steam_deck(t: str) -> Model | None:
    m = re.search(r"steam\s*deck", t)
    if not m:
        return None
    kind = "OLED" if "oled" in t else "LCD"
    return Model(f"Steam Deck {kind}", storage_of(t), m.start())


def _xbox_series(letter: str) -> Callable[[str], Model | None]:
    def f(t: str) -> Model | None:
        m = re.search(rf"(?:xbox\s*)?series\s*{letter}\b", t)
        if not m or ("xbox" not in t and "microsoft" not in t):
            return None
        other = "x" if letter == "s" else "s"
        if re.search(rf"series\s*{other}\b", t):
            return None  # «Series S/X» — непонятно что продают
        return Model(f"Xbox Series {letter.upper()}", storage_of(t), m.start())
    return f


def _playstation(t: str) -> Model | None:
    m = re.search(r"(?:\bps|playstation|play station)\s*([45])\b", t)
    if not m:
        return None
    gen = m.group(1)
    kind = "Pro" if re.search(r"\bpro\b", t) else "Slim" if "slim" in t else ""
    if gen == "5" and not kind and re.search(r"\b(?:fat|фат|толст)", t):
        kind = "Fat"
    digital = re.search(r"digital|диджитал|цифров|без дисковод", t)
    name = f"PS{gen}" + (f" {kind}" if kind else "") + (" Digital" if digital and gen == "5" else "")
    return Model(name, None, m.start())


@dataclass
class Category:
    id: str
    title: str
    queries: list[str]
    detect: Callable[[str], Model | None]
    min_price: int                      # дешевле — точно не сам товар (аксессуары, скам)
    battery: bool = False               # проверять АКБ
    enabled: bool = True
    exclude: tuple[str, ...] = field(default_factory=tuple)

    def urls(self, city: str) -> list[str]:
        return [f"https://www.avito.ru/{city}?{urlencode({'q': q, 's': '104'})}" for q in self.queries]


CATEGORIES: dict[str, Category] = {c.id: c for c in [
    Category("iphone", "📱 iPhone", ["iphone"], _iphone, 4000, battery=True),
    Category("pixel", "📱 Google Pixel", ["google pixel"], _pixel, 3000, battery=True),
    Category("macbook", "💻 MacBook", ["macbook"], _macbook, 12000, battery=True),
    Category("steamdeck", "🎮 Steam Deck", ["steam deck"], _steam_deck, 12000),
    Category("xbox_s", "🎮 Xbox Series S", ["xbox series s"], _xbox_series("s"), 8000),
    Category("xbox_x", "🎮 Xbox Series X", ["xbox series x"], _xbox_series("x"), 15000, enabled=False),
    Category("ps5", "🎮 PlayStation 5", ["playstation 5"], _playstation, 15000, exclude=("ps4", "playstation 4")),
    Category("ps4", "🎮 PlayStation 4", ["playstation 4"], _playstation, 5000, enabled=False,
             exclude=("ps5", "playstation 5")),
]}


def classify(cat: Category, title: str) -> Model | None:
    """Модель товара или None, если это аксессуар/услуга/другой товар."""
    t = _norm(title)
    if any(w in t for w in ALWAYS_SKIP) or any(w in t for w in cat.exclude):
        return None
    model = cat.detect(t)
    if not model:
        return None
    head = t[:model.pos]
    if any(w in head for w in ACCESSORY_WORDS):
        return None
    return model
