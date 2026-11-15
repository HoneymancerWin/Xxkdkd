from avito_monitor.avito import Item, parse_search_page
from avito_monitor.main import DEFAULTS, is_deal, process_search
from avito_monitor.market import market_price
from avito_monitor.storage import Storage

HTML = """
<div data-marker="catalog-serp">
  <div data-marker="item" data-item-id="111">
    <a data-marker="item-title" href="/moskva/telefony/iphone_13_111" title="iPhone 13 128GB">x</a>
    <meta itemprop="price" content="30000">
    <div data-marker="item-date">5 минут назад</div>
  </div>
  <div data-marker="item" data-item-id="222">
    <a data-marker="item-title" href="/moskva/telefony/iphone_13_222"><h3>iPhone 13 разбит</h3></a>
    <p data-marker="item-price">12 500 ₽</p>
  </div>
</div>
"""


def test_parse():
    items = parse_search_page(HTML)
    assert [i.id for i in items] == ["111", "222"]
    assert items[0].price == 30000 and items[0].title == "iPhone 13 128GB"
    assert items[0].url == "https://www.avito.ru/moskva/telefony/iphone_13_111"
    assert items[1].price == 12500 and items[1].title == "iPhone 13 разбит"


def test_market_trims_outliers():
    assert market_price([1, 50000, 50000, 52000, 48000, 51000, 49000, 50000, 50000, 999999]) == 50000


def test_is_deal():
    s = {**DEFAULTS, "discount": 20, "min_price": 10000}
    it = Item("1", "t", 39000, "u")
    assert is_deal(it, s, 50000)[0]
    assert not is_deal(Item("1", "t", 45000, "u"), s, 50000)[0]
    assert not is_deal(Item("1", "t", 5000, "u"), s, 50000)[0]
    assert not is_deal(it, s, None)[0]          # без данных о рынке не спамим


class FakeClient:
    def __init__(self):
        self.items = []

    def search(self, url, pages):
        return self.items


class FakeTG:
    def __init__(self):
        self.msgs = []

    def send(self, text):
        self.msgs.append(text)


def test_flow(tmp_path):
    db, tg, client = Storage(str(tmp_path / "db.sqlite")), FakeTG(), FakeClient()
    s = {**DEFAULTS, "name": "test", "url": "u", "discount": 20, "min_samples": 5,
         "include": [], "exclude": ["разбит"]}
    client.items = [Item(str(i), "iphone", 50000 + i * 100, f"u{i}") for i in range(10)]
    process_search(client, db, tg, s)
    assert tg.msgs == []                         # первый запуск: только запоминаем

    client.items += [Item("new", "iphone дешево", 35000, "unew"),
                     Item("bad", "iphone разбит", 20000, "ubad"),
                     Item("meh", "iphone", 49000, "umeh")]
    process_search(client, db, tg, s)
    assert len(tg.msgs) == 1 and "unew" in tg.msgs[0]

    process_search(client, db, tg, s)
    assert len(tg.msgs) == 1                     # повторно не шлём

    client.items[0] = Item("0", "iphone", 36000, "u0")   # старое подешевело
    process_search(client, db, tg, s)
    assert len(tg.msgs) == 2 and "цена снижена" in tg.msgs[1]


# ---------- анализ объявления ----------
from avito_monitor.analysis import Details, analyze, find_flags
from avito_monitor.avito import parse_item_page
from avito_monitor.telegram import format_item

ITEM_HTML = """
<div data-marker="item-view/item-description"><p>Телефон в идеальном состоянии, без царапин и сколов.</p>
<p>Полный комплект, есть чек. Трещин нет.</p></div>
<div data-marker="item-view/item-params"><ul>
  <li>Состояние: Б/у</li><li>Встроенная память: 128 ГБ</li><li>Цвет: синий</li>
</ul></div>
<div data-marker="seller-info">
  <div data-marker="seller-info/name">Алексей</div>
  <div data-marker="seller-info/label">Частное лицо</div>
  <span data-marker="seller-info/score">4,9</span>
  <a data-marker="rating-caption/rating">137 отзывов</a>
  <div>На Авито с марта 2019</div>
</div>
"""


def test_parse_item_page():
    d = parse_item_page(ITEM_HTML)
    assert d.condition == "Б/у"
    assert d.params["Встроенная память"] == "128 ГБ"
    assert d.seller_name == "Алексей" and d.seller_type == "Частное лицо"
    assert d.seller_rating == 4.9 and d.seller_reviews == 137
    assert d.seller_since == "марта 2019"
    assert "идеальном" in d.description


def test_flags_respect_negation():
    red, green, _ = find_flags("Без царапин и сколов, трещин нет, есть чек")
    assert red == []
    assert {"без царапин", "есть чек"} <= set(green)
    red, _, _ = find_flags("Есть скол на углу, iCloud не отвязан, только предоплата")
    assert {"сколы", "iCloud", "предоплата"} <= set(red)


def test_analyze_scores_and_rejects():
    good = parse_item_page(ITEM_HTML)
    a = analyze("iPhone 13", good, {})
    assert a.score >= 8 and a.reject is None

    bad = Details(description="разбит экран, предоплата", condition="Б/у", seller_rating=None, seller_reviews=0)
    a = analyze("iPhone", bad, {"min_seller_reviews": 3})
    assert a.score < 4 and "отзывов" in a.reject

    assert analyze("x", good, {"conditions": ["Новое"]}).reject
    assert analyze("x", good, {"min_seller_rating": 4.95}).reject
    assert analyze("x", Details(description="iCloud", seller_reviews=5), {"reject_red_flags": ["iCloud"]}).reject


def test_message_contains_seller_and_condition():
    d = parse_item_page(ITEM_HTML)
    msg = format_item("s", Item("1", "iPhone", 30000, "https://x"), 40000, "r", details=d,
                      analysis=analyze("iPhone", d, {}))
    assert "Б/у" in msg and "⭐ 4.9" in msg and "137 отзывов" in msg and "Оценка сделки" in msg


def test_flow_filters_by_seller(tmp_path):
    class DetailClient(FakeClient):
        def details(self, url):
            return Details(seller_rating=3.1, seller_reviews=2) if url == "ubad" else parse_item_page(ITEM_HTML)

    db, tg, client = Storage(str(tmp_path / "db.sqlite")), FakeTG(), DetailClient()
    s = {**DEFAULTS, "name": "t", "url": "u", "max_price": 40000, "min_seller_rating": 4.5}
    client.items = [Item("0", "iphone", 50000, "u0")]
    process_search(client, db, tg, s)
    client.items += [Item("good", "iphone", 30000, "ugood"), Item("bad", "iphone", 30000, "ubad")]
    process_search(client, db, tg, s)
    assert len(tg.msgs) == 1 and "ugood" in tg.msgs[0] and "Алексей" in tg.msgs[0]


def test_manual_market_price(tmp_path):
    db, tg, client = Storage(str(tmp_path / "db.sqlite")), FakeTG(), FakeClient()
    s = {**DEFAULTS, "name": "t", "url": "u", "discount": 20, "market_price": 20000, "details": False}
    client.items = [Item("0", "iphone", 21000, "u0")]
    process_search(client, db, tg, s)               # первый запуск
    client.items += [Item("a", "iphone", 15500, "ua"), Item("b", "iphone", 17000, "ub")]
    process_search(client, db, tg, s)
    assert len(tg.msgs) == 1 and "ua" in tg.msgs[0] and "20 000" in tg.msgs[0]
