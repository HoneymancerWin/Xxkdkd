"""Анализ объявления: описание, состояние, продавец → оценка сделки."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# (основа слова/фраза, что показать, вес). Ищется без учёта регистра по описанию и заголовку.
RED_FLAGS = [
    # повреждения и неисправности
    ("разбит", "разбит", 3), ("трещин", "трещины", 2), ("скол", "сколы", 1),
    ("не включа", "не включается", 4), ("не работа", "не работает", 3),
    ("не заряжа", "не заряжается", 3), ("не ловит", "не ловит сеть", 2),
    ("залит", "залит", 3), ("утоп", "утоплен", 3), ("после воды", "после воды", 3),
    ("дефект", "дефект", 2), ("неисправ", "неисправен", 3), ("глючит", "глючит", 2),
    ("битый пиксел", "битые пиксели", 2), ("полос", "полосы на экране", 2),
    ("на запчаст", "на запчасти", 5), ("под ремонт", "под ремонт", 4), ("требует ремонт", "требует ремонта", 4),
    ("был в ремонт", "был в ремонте", 1), ("менял", "менялись детали", 1), ("не оригинал", "не оригинал", 2),
    ("копия", "копия", 4), ("реплик", "реплика", 4), ("люкс копи", "копия", 4),
    # блокировки
    ("icloud", "iCloud", 4), ("айклауд", "iCloud", 4), ("заблокирован", "заблокирован", 4),
    ("привязан к аккаунт", "привязан к аккаунту", 4), ("в залоге", "в залоге", 4),
    ("без документ", "без документов", 2),
    # признаки мошенничества
    ("предоплат", "предоплата", 3), ("только доставк", "только доставка", 1),
    ("пишите в whatsapp", "уводит в мессенджер", 2), ("пишите в ватсап", "уводит в мессенджер", 2),
    ("пишите в телеграм", "уводит в мессенджер", 2), ("пишите в tg", "уводит в мессенджер", 2),
    ("звонки не принима", "звонки не принимает", 1), ("срочно", "срочная продажа", 0.5),
    ("торг не уместен", "без торга", 0), ("из-за границ", "товар из-за границы", 1),
]

GREEN_FLAGS = [
    ("чек", "есть чек"), ("гаранти", "гарантия"), ("полный комплект", "полный комплект"),
    ("коробк", "коробка"), ("идеальн", "идеальное состояние"), ("как нов", "как новый"),
    ("без царапин", "без царапин"), ("один владел", "один владелец"), ("оригинал", "оригинал"),
    ("не вскрыва", "не вскрывался"), ("рст", "РСТ"), ("ростест", "РСТ"), ("на гарантии", "на гарантии"),
    ("проверка при встрече", "проверка при встрече"), ("личная встреча", "личная встреча"),
]

# «без X», «не X», «без царапин и сколов», «ни царапин, ни сколов»
_NEGATION = re.compile(r"(?:\bбез|\bнет|\bни|\bне)\s+(?:\w+[\s,]+(?:и\s+|или\s+|ни\s+)?)?$")


@dataclass
class Details:
    description: str = ""
    params: dict[str, str] = field(default_factory=dict)
    condition: str = ""
    seller_name: str = ""
    seller_type: str = ""          # «Частное лицо» / «Компания» / «Магазин»
    seller_rating: float | None = None
    seller_reviews: int | None = None
    seller_since: str = ""


@dataclass
class Analysis:
    score: float
    red: list[str]
    green: list[str]
    reject: str | None = None      # причина отсева, если не прошло фильтры


def _found(text: str, stem: str) -> bool:
    for m in re.finditer(re.escape(stem), text):
        before = text[max(0, m.start() - 20):m.start()]
        after = text[m.end():m.end() + 15]
        if stem.startswith("не ") or stem.startswith("без "):
            return True
        if _NEGATION.search(before) or re.match(r"\w*\s*(?:нет|отсутству)", after):
            continue  # «без сколов», «не битый», «трещин нет»
        return True
    return False


def find_flags(text: str) -> tuple[list[str], list[str], float]:
    text = text.lower().replace("ё", "е")
    red, penalty = [], 0.0
    for stem, label, weight in RED_FLAGS:
        if label not in red and _found(text, stem):
            red.append(label)
            penalty += weight
    green = []
    for stem, label in GREEN_FLAGS:
        if label in green:
            continue
        pattern = r"\b" + re.escape(stem) if len(stem) <= 4 else re.escape(stem)
        if re.search(pattern, text) and _found(text, stem):
            green.append(label)
    return red, green, penalty


def analyze(title: str, d: Details, s: dict) -> Analysis:
    red, green, penalty = find_flags(f"{title}\n{d.description}")
    score = 6.0 - min(penalty, 6) + min(len(green) * 0.5, 2)

    cond = d.condition.lower()
    if "нов" in cond:
        score += 1
    elif "запчаст" in cond or "неисправ" in cond:
        score -= 4
        if "на запчасти" not in red:
            red.append(f"состояние: {d.condition}")

    r, n = d.seller_rating, d.seller_reviews
    if r is not None:
        score += 2 if r >= 4.8 else 1 if r >= 4.5 else -1 if r < 4.0 else 0
    if not n:
        score -= 1
        red.append("у продавца нет отзывов")
    elif n >= 20:
        score += 1
    score = max(0.0, min(10.0, score))

    a = Analysis(score=round(score, 1), red=red, green=green)
    if s.get("conditions") and not any(c.lower() in cond for c in s["conditions"]):
        a.reject = f"состояние «{d.condition or 'не указано'}»"
    elif s.get("min_seller_rating") and (r is None or r < s["min_seller_rating"]) and n:
        a.reject = f"рейтинг продавца {r}"
    elif s.get("min_seller_reviews") and (n or 0) < s["min_seller_reviews"]:
        a.reject = f"отзывов у продавца: {n or 0}"
    elif s.get("seller_types") and not any(t.lower() in d.seller_type.lower() for t in s["seller_types"]):
        a.reject = f"тип продавца «{d.seller_type}»"
    elif s.get("reject_red_flags") and any(f in red for f in s["reject_red_flags"]):
        a.reject = "стоп-признаки: " + ", ".join(f for f in red if f in s["reject_red_flags"])
    elif s.get("min_score") and a.score < s["min_score"]:
        a.reject = f"оценка {a.score} < {s['min_score']}"
    return a
