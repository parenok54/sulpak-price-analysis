from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper"))
from sulpak_scraper import parse_page, to_number  # noqa: E402

HTML = (Path(__file__).parent / "fixtures" / "catalog_page.html").read_text(encoding="utf-8")


def test_to_number():
    assert to_number("4 990 сом") == 4990
    assert to_number("-28%") == 28
    assert to_number("4890.0") == 4890
    assert to_number("") is None
    assert to_number(None) is None


def test_parse_page_reads_all_cards():
    products = parse_page(HTML, "Наушники")
    assert [p.code for p in products] == ["636948", "636650", "620226", "999001"]
    assert all(p.category == "Наушники" for p in products)


def test_discounted_product():
    p = parse_page(HTML, "Наушники")[0]
    assert p.brand == "Samsung"
    assert p.price == 4890 and p.old_price == 4990 and p.discount_pct == 2
    assert p.rating == 5 and p.reviews == 508
    assert p.url == "https://www.sulpak.kg/g/naushniki-samsung-galaxy-buds-core-sm-r410nzkacis-cherniyj"
    assert p.specs.startswith("Ответить/закончить разговор: Да")
    assert p.availability == "Есть в наличии"


def test_product_without_discount_or_reviews():
    no_disc = parse_page(HTML, "Наушники")[1]
    assert no_disc.old_price is None and no_disc.discount_pct is None
    assert no_disc.rating == 4 and no_disc.reviews == 91
    no_reviews = parse_page(HTML, "Наушники")[2]
    assert no_reviews.rating is None and no_reviews.reviews == 0
    assert no_reviews.discount_pct == 28


import json  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class FakeSession:
    """Mimics /Filter/LoadProducts: 2 pages, the second repeats one product from the first."""
    def __init__(self):
        self.pages = []

    def get(self, url, params=None, timeout=None):
        self.pages.append(params["page"])
        paginator = '<div id="paginator" data-currentPage="%d" data-pagesCount="2"></div>' % params["page"]
        return FakeResponse({"paginator": paginator, "products": HTML})


def test_scrape_category_follows_page_count_and_dedupes():
    from sulpak_scraper import scrape_category, pages_count
    assert pages_count('<div data-currentPage="9" data-pagesCount="30">') == 30
    s = FakeSession()
    products = scrape_category(s, "naushniki", "Наушники", delay=0, max_pages=80)
    assert s.pages == [1, 2]
    assert len(products) == 4


def test_out_of_stock_card():
    p = parse_page(HTML, "Смартфоны")[3]
    assert p.price is None
    assert p.availability == "Нет в наличии"
