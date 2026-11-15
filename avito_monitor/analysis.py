"""Анализ объявления: описание, состояние, продавец → оценка сделки."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# (основа слова/фраза, что показать, вес). Ищется без учёта регистра по описанию и заголовку.
RED_FLAGS = [
    # повреждения и неисправности
    ("разбит", "разбит", 3), ("трещин", "трещины", 2),
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
    # «купил — не пригодилось», «подарили»
    ("не пригодил", "не пригодился"), ("не подошел", "не подошёл"), ("не подошёл", "не подошёл"),
    ("подарили", "подарок"), ("подарок", "подарок"), ("не пользовал", "не использовался"),
    ("не использовал", "не использовался"), ("не распаков", "не распакован"), ("в пленках", "в заводских плёнках"),
    ("в заводской", "в заводских плёнках"), ("запечатан", "запечатан"), ("ни разу не", "ни разу не использовался"),
]

DAMAGE = {
    "разбит", "трещины", "не включается", "не работает", "не заряжается", "не ловит сеть", "залит",
    "утоплен", "после воды", "дефект", "неисправен", "глючит", "битые пиксели", "полосы на экране",
    "на запчасти", "под ремонт", "требует ремонта",
}

# Следы износа: не поломка, но «отличным» такое уже не назовёшь.
WEAR_FLAGS = [
    ("царапин", "царапины"), ("царапк", "царапины"), ("поцарап", "царапины"), ("скол", "сколы"),
    ("потерт", "потёртости"), ("потёрт", "потёртости"), ("вмятин", "вмятины"), ("следы использ", "следы использования"),
    ("следы эксплуат", "следы использования"), ("износ", "износ"), ("выгорел", "выгорание экрана"),
    ("хорошее состояни", "хорошее (не отличное) состояние"), ("хорошем состояни", "хорошее (не отличное) состояние"), ("нормальное состояни", "нормальное состояние"),
    ("удовлетворит", "удовлетворительное состояние"), ("рабочее состояни", "«рабочее состояние»"),
]

# Явные признаки отличного состояния.
EXCELLENT_FLAGS = [
    ("идеальн", "идеальное"), ("отличн", "отличное"), ("как нов", "как новый"), ("состояние нового", "как новый"),
    ("без царапин", "без царапин"), ("без единой царапин", "без царапин"), ("без сколов", "без сколов"),
    ("без потерт", "без потёртостей"), ("без следов", "без следов использования"), ("10/10", "10/10"),
    ("10 из 10", "10/10"), ("всегда в чехл", "всегда в чехле"), ("с первого дня в чехл", "всегда в чехле"),
    ("с защитным стекл", "под стеклом"), ("пленк", "под плёнкой"), ("плёнк", "под плёнкой"),
]

# Значения поля «Состояние» на Авито.
_COND_EXCELLENT = ("отличн", "идеальн", "как нов")
_COND_BAD = ("хорош", "удовлетвор", "ремонт", "запчаст", "неисправ", "плох")

_BATTERY = re.compile(
    r"(?:акб|акум\w*|аккум\w*|батаре\w*|емкост\w*|ёмкост\w*|battery|здоровье)\D{0,25}?(\d{2,3})\s*%"
    r"|(\d{2,3})\s*%\s*(?:акб|аккум\w*|емкост\w*|ёмкост\w*)"
)

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
    grade: str = "unknown"         # new / excellent / good / bad / unknown
    grade_note: str = ""
    battery: int | None = None     # здоровье АКБ, %
    wear: list[str] = field(default_factory=list)


GRADE_RU = {"new": "новое", "excellent": "отличное", "good": "есть следы износа",
            "bad": "дефекты/неисправность", "unknown": "не понятно из описания"}


def _labels(text: str, flags) -> list[str]:
    out = []
    for stem, label in flags:
        if label not in out and _found(text, stem):
            out.append(label)
    return out


def parse_battery(text: str) -> int | None:
    vals = [int(a or b) for a, b in _BATTERY.findall(text.lower())]
    vals = [v for v in vals if 50 <= v <= 100]
    return min(vals) if vals else None


def grade_condition(title: str, d: Details, red: list[str]) -> tuple[str, str, list[str]]:
    """Реальное состояние товара.

    Главный источник — обязательное поле «Состояние» на Авито (Новое / Отличное / Хорошее /
    Удовлетворительное / Требует ремонта…). Описание только уточняет: если там упомянуты
    дефекты или износ, «Отличное» понижается.
    """
    text = f"{title}\n{d.description}".lower().replace("ё", "е")
    cond = d.condition.lower()
    wear = _labels(text, WEAR_FLAGS)
    damage = [f for f in red if f in DAMAGE]
    if damage:
        return "bad", "в описании: " + ", ".join(damage), wear
    if any(w in cond for w in _COND_BAD):
        return ("good" if "хорош" in cond else "bad"), f"в объявлении: {d.condition}", wear
    if "нов" in cond and "как" not in cond:
        return "new", "", wear
    if any(w in cond for w in _COND_EXCELLENT):
        if wear:
            return "good", f"указано «{d.condition}», но в описании: " + ", ".join(wear), wear
        return "excellent", f"в объявлении: {d.condition}", wear
    # Поле пустое (не прочитали) или общее «Б/у» — смотрим описание.
    if wear:
        return "good", "в описании: " + ", ".join(wear), wear
    good = _labels(text, EXCELLENT_FLAGS)
    if good:
        return "excellent", "по описанию: " + ", ".join(good), wear
    if not cond:
        return "unknown", "не удалось прочитать поле «Состояние»", wear
    return "unknown", f"указано только «{d.condition}»", wear


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

    grade, note, wear = grade_condition(title, d, red)
    battery = parse_battery(f"{title} {d.description} {' '.join(d.params.values())}")
    score += {"excellent": 1, "good": -1, "bad": -2}.get(grade, 0)
    if battery is not None:
        score += 1 if battery >= 90 else -1 if battery < 80 else 0
    score = max(0.0, min(10.0, score))

    a = Analysis(score=round(score, 1), red=red, green=green, grade=grade, grade_note=note,
                 battery=battery, wear=wear)
    want = s.get("condition_grade")
    min_bat = s.get("min_battery")
    if grade == "new" and s.get("allow_new") is False:
        a.reject = "новое (нужно б/у)"
    elif want == "excellent" and grade not in ("excellent", "new") and not (
            grade == "unknown" and (s.get("allow_unknown_condition") or not d.condition)):
        # Пустое поле — скорее всего, поменялась вёрстка Авито: не теряем объявление, а помечаем.
        a.reject = f"состояние: {GRADE_RU[grade]}" + (f" ({note})" if note else "")
    elif want == "good" and grade in ("bad",):
        a.reject = f"состояние: {GRADE_RU[grade]} ({note})"
    elif min_bat and battery is not None and battery < min_bat:
        a.reject = f"АКБ {battery}% < {min_bat}%"
    elif min_bat and battery is None and s.get("require_battery"):
        a.reject = "не указан износ АКБ"
    elif s.get("conditions") and not any(c.lower() in cond for c in s["conditions"]):
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
