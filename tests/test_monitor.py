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
