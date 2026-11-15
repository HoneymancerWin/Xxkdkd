import threading

import pytest

from avito_monitor.analysis import Details
from avito_monitor.avito import Item
from avito_monitor.bot import Bot
from avito_monitor.catalog import CATEGORIES as C, classify
from avito_monitor.main import Settings, monitor, process_category
from avito_monitor.storage import Storage


@pytest.mark.parametrize("cat,title,expected", [
    ("iphone", "iPhone 13 128 ГБ", ("iPhone 13", "128GB")),
    ("iphone", "Смартфон Apple iPhone 15 Pro Max 256gb", ("iPhone 15 Pro Max", "256GB")),
    ("iphone", "Айфон 12 про 8/128", ("iPhone 12 Pro", "128GB")),
    ("iphone", "Чехол для iPhone 13", None),
    ("iphone", "Куплю iPhone 14", None),
    ("iphone", "Ремонт iPhone любой сложности", None),
    ("pixel", "Google Pixel 7a 8/128", ("Pixel 7a", "128GB")),
    ("pixel", "Pixel 8 Pro 256gb", ("Pixel 8 Pro", "256GB")),
    ("macbook", "MacBook Air 13 M1 8/256", ("MacBook Air M1", '13"')),
    ("macbook", "Apple MacBook Pro 14\" M3 Pro 18/512", ("MacBook Pro M3 Pro", '14"')),
    ("macbook", "Зарядка для MacBook", None),
    ("steamdeck", "Steam Deck OLED 512GB", ("Steam Deck OLED", "512GB")),
    ("steamdeck", "Steam Deck 64gb", ("Steam Deck LCD", "64GB")),
    ("steamdeck", "Стим дек олед 1тб", ("Steam Deck OLED", "1TB")),
    ("xbox_s", "Игровая приставка Microsoft Xbox Series S 1TB", ("Xbox Series S", "1TB")),
    ("xbox_s", "Геймпад Xbox Series S/X", None),
    ("ps5", "Sony PlayStation 5 Slim с дисководом", ("PS5 Slim", None)),
    ("ps5", "PS5 Digital Edition + 2 геймпада", ("PS5 Digital", None)),
    ("ps5", "Игра для PS5 God of War", None),
])
def test_classify(cat, title, expected):
    m = classify(C[cat], title)
    assert (m and (m.name, m.variant)) == expected or (m is None and expected is None)


class FakeClient:
    def __init__(self):
        self.items = []
        self.detail = Details(description="Идеальное состояние, АКБ 92%", condition="Отличное",
                              seller_name="Алексей", seller_rating=4.9, seller_reviews=20)

    def search(self, url, pages):
        return self.items if "iphone" in url else []

    def details(self, url):
        return self.detail


class FakeTG:
    chat_ids = [1]

    def __init__(self):
        self.sent, self.calls = [], []

    def send(self, text, markup=None, chat_id=None, preview=False):
        self.sent.append((text, markup))

    def call(self, method, http_timeout=20, **p):
        self.calls.append((method, p))
        return True


@pytest.fixture
def env(tmp_path):
    db = Storage(str(tmp_path / "db.sqlite"))
    return db, Settings(db), FakeTG(), FakeClient()


def iphones(n=8, base=20000):
    return [Item(f"m{i}", "iPhone 13 128GB", base + i * 200, f"u{i}") for i in range(n)]


def test_finds_deal_by_model_market(env):
    db, st, tg, client = env
    client.items = iphones() + [Item("x", "iPhone 15 Pro 256GB", 70000, "ux")]
    process_category(client, db, tg, C["iphone"], st)
    assert tg.sent == []                                   # первый проход — только цены

    client.items += [Item("cheap", "iPhone 13 128 гб", 15000, "ucheap"),     # −26% → находка
                     Item("ok", "iPhone 13 128GB", 19500, "uok"),            # почти рынок
                     Item("case", "Чехол для iPhone 13", 15000, "ucase")]    # аксессуар
    process_category(client, db, tg, C["iphone"], st)
    assert len(tg.sent) == 1
    text, kb = tg.sent[0]
    assert "ucheap" in text and "iPhone 13 128GB" in text and "АКБ" in text
    assert kb["inline_keyboard"][1][0]["callback_data"].startswith("buy:")


def test_deal_rejected_by_condition(env):
    db, st, tg, client = env
    client.items = iphones()
    process_category(client, db, tg, C["iphone"], st)
    client.detail = Details(description="есть царапины", condition="Хорошее", seller_reviews=5, seller_rating=4.9)
    client.items.append(Item("cheap", "iPhone 13 128GB", 15000, "ucheap"))
    process_category(client, db, tg, C["iphone"], st)
    assert tg.sent == []


def test_bot_buy_and_sell_flow(env):
    db, st, tg, client = env
    client.items = iphones()
    process_category(client, db, tg, C["iphone"], st)
    client.items.append(Item("cheap", "iPhone 13 128GB", 15000, "ucheap"))
    process_category(client, db, tg, C["iphone"], st)
    bot = Bot(tg, db, st, threading.Event())
    deal_id = int(tg.sent[0][1]["inline_keyboard"][1][0]["callback_data"].split(":")[1])

    bot.handle({"callback_query": {"id": "q", "data": f"buy:{deal_id}",
                                   "message": {"chat": {"id": 1}, "message_id": 5}}})
    assert db.deal(deal_id)["status"] == "bought"
    text, kb = bot.bought_view()
    assert "Потрачено" in text and "15 000" in text
    bot.handle({"callback_query": {"id": "q", "data": f"sold:{deal_id}",
                                   "message": {"chat": {"id": 1}, "message_id": 6}}})
    bot.handle({"message": {"chat": {"id": 1}, "text": "19 000"}})
    assert db.deal(deal_id)["sold_price"] == 19000
    assert "+4 000" in bot.bought_view()[0]


def test_bot_settings_and_categories(env):
    db, st, tg, client = env
    bot = Bot(tg, db, st, threading.Event())
    q = lambda data: bot.handle({"callback_query": {"id": "q", "data": data,
                                                    "message": {"chat": {"id": 1}, "message_id": 1}}})
    assert st["discount"] == 20
    q("cyc:discount")
    assert st["discount"] == 25
    q("cyc:grade")
    assert st["grade"] == "good"
    q("city:sankt-peterburg")
    assert st["city"] == "sankt-peterburg"
    assert st.cat_on(C["xbox_x"]) is False
    q("cat:xbox_x")
    assert st.cat_on(C["xbox_x"]) is True


def test_bot_ignores_strangers(env):
    db, st, tg, client = env
    bot = Bot(tg, db, st, threading.Event())
    bot.handle({"message": {"chat": {"id": 999}, "text": "🛒 Покупки"}})
    assert "доступа нет" in tg.sent[-1][0]


def test_monitor_once(env, monkeypatch):
    monkeypatch.setattr("avito_monitor.main.time.sleep", lambda s: None)
    db, st, tg, client = env
    client.items = iphones()
    monitor(client, db, tg, st, threading.Event(), once=True)
    assert db.get("status")["items"] == 8
    assert db.market_overview("iphone", 21)[0][0] == "iPhone 13 128GB"
