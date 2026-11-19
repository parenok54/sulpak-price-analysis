"""Scrape product listings from the Sulpak.kg catalog into a CSV file.

Usage:
    python scraper/sulpak_scraper.py                      # all default categories
    python scraper/sulpak_scraper.py -c smartfoniy noutbuki --delay 1.5 -o data/my_run.csv

Only public catalog pages are requested, one at a time with a pause between requests.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import asdict, dataclass, fields
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.sulpak.kg"

CATEGORIES = {
    "smartfoniy": "Смартфоны",
    "noutbuki": "Ноутбуки",
    "naushniki": "Наушники",
    "planshetiy": "Планшеты",
    "smart_chasiy": "Смарт-часы",
    "holodilniki": "Холодильники",
    "stiralniye_mashiniy": "Стиральные машины",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


@dataclass
class Product:
    category: str
    code: str
    name: str
    brand: str
    price: float | None
    old_price: float | None
    discount_pct: float | None
    rating: int | None
    reviews: int
    availability: str
    specs: str
    url: str


def to_number(text: str | None) -> float | None:
    """'4 990 сом' -> 4990.0, '-28%' -> 28.0, '4890.0' -> 4890.0"""
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", text)
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def parse_page(html: str, category: str) -> list[Product]:
    """Parse one catalog page into a list of products."""
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for card in soup.select("div.product__item[data-code]"):
        name = card.get("data-name")
        if not name:
            continue
        link = card.select_one('a[href^="/g/"]')
        reviews_el = card.select_one(".product__item-reviews")
        rating = reviews = None
        if reviews_el:
            rating = sum(1 for u in reviews_el.select("use")
                         if (u.get("xlink:href") or u.get("href") or "").endswith("star_active"))
            span = reviews_el.select_one("span")
            reviews = int(to_number(span.get_text()) or 0) if span else 0
        old = card.select_one(".product__item-price-old")
        disc = card.select_one(".product__label-discount")
        desc = card.select_one(".product__item-description")
        stock = card.select_one(".product__item-showcase")
        products.append(Product(
            category=category,
            code=card.get("data-code", ""),
            name=name.strip(),
            brand=(card.get("data-brand") or "").strip(),
            price=to_number(card.get("data-price")) or None,   # out-of-stock cards carry data-price="0"
            old_price=to_number(old.get_text()) if old else None,
            discount_pct=to_number(disc.get_text()) if disc else None,
            rating=rating,
            reviews=reviews or 0,
            availability=(" ".join(stock.get_text(" ").split()) if stock
                          else "Нет в наличии" if "Нет в наличии" in card.get_text() else ""),
            specs=" ".join(desc.get_text(" ").split()) if desc else "",
            url=BASE_URL + link["href"] if link else "",
        ))
    return products


# The public category page (/f/<slug>?page=N) stops after ~8 pages and then repeats the last one.
# The site's own "show more" button loads pages from this endpoint instead; it returns JSON with the
# product cards as HTML plus a paginator that holds the real page count.
LOAD_URL = BASE_URL + "/Filter/LoadProducts"


def load_params(slug: str, page: int) -> dict:
    return {"className": slug, "selectedPropertiesTokens": "~", "selectedActionsTokens": "~",
            "sort": "popularitydesc", "listing": "default", "onPage": 22, "page": page, "price": "~"}


def pages_count(paginator_html: str) -> int:
    m = re.search(r'data-pagesCount="(\d+)"', paginator_html or "", re.I)
    return int(m.group(1)) if m else 1


def scrape_category(session: requests.Session, slug: str, title: str,
                    delay: float, max_pages: int) -> list[Product]:
    seen: set[str] = set()
    result: list[Product] = []
    page, total = 1, 1
    while page <= min(total, max_pages):
        resp = session.get(LOAD_URL, params=load_params(slug, page), timeout=20)
        if resp.status_code != 200:
            print(f"  {slug} page {page}: HTTP {resp.status_code}, stopping", file=sys.stderr)
            break
        data = resp.json()
        total = pages_count(data.get("paginator", ""))
        new = [p for p in parse_page(data.get("products", ""), title) if p.code not in seen]
        seen.update(p.code for p in new)
        result.extend(new)
        print(f"  {slug} page {page}/{total}: +{len(new)} (total {len(result)})")
        page += 1
        time.sleep(delay)
    return result


def save_csv(products: list[Product], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[fl.name for fl in fields(Product)])
        writer.writeheader()
        writer.writerows(asdict(p) for p in products)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--categories", nargs="+", default=list(CATEGORIES),
                    help="category slugs from sulpak.kg/f/<slug> (default: all)")
    ap.add_argument("-o", "--out", type=Path, default=Path(f"data/sulpak_{date.today()}.csv"))
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1.0)")
    ap.add_argument("--max-pages", type=int, default=80, help="safety cap on pages per category")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update(HEADERS)
    products: list[Product] = []
    for slug in args.categories:
        title = CATEGORIES.get(slug, slug)
        print(f"{title} ({slug})")
        products += scrape_category(session, slug, title, args.delay, args.max_pages)
    save_csv(products, args.out)
    print(f"Saved {len(products)} products to {args.out}")


if __name__ == "__main__":
    main()
