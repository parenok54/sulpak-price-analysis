"""Turn the raw scrape into an analysis-ready table.

    python src/clean.py data/raw/sulpak_2026-11-19.json data/sulpak_clean.csv

Adds: in_stock flag, normalised availability, discount fields, product type, and numeric
features parsed from the short spec line on each card (RAM, storage, battery, screen, ...).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

AVAILABILITY = {
    "Есть в наличии": "In stock (shop)",
    "На витрине": "Display unit",
    "Нет в наличии": "Out of stock",
    "": "Available to order",
}

CATEGORY_EN = {
    "Смартфоны": "Smartphones", "Ноутбуки": "Laptops", "Наушники": "Headphones",
    "Планшеты": "Tablets", "Смарт-часы": "Smartwatches", "Холодильники": "Fridges",
    "Стиральные машины": "Washing machines",
}


def parse_specs(text: str) -> dict[str, str]:
    """'RAM: 8 GB / Storage: 256 GB' -> {'RAM': '8 GB', 'Storage': '256 GB'}"""
    out = {}
    for part in (text or "").split(" / "):
        if ":" in part:
            key, value = part.split(":", 1)
            value = value.strip()
            if value and not value.startswith("-"):      # '- GB' means the field is empty
                out[key.strip()] = value
    return out


def to_gb(value: str | None) -> float | None:
    """'256 GB' -> 256, '2 TB' -> 2048, 'SSD 512GB' -> 512, 'SSD 1TB' -> 1024"""
    if not isinstance(value, str) or not value:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(TB|GB|ТБ|ГБ)", value, re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    return n * 1024 if m.group(2).upper() in ("TB", "ТБ") else n


def first_number(value: str | None) -> float | None:
    """'7000 мАч' -> 7000, '11,5″ - 29,21 см' -> 11.5, '1200 Об/мин' -> 1200"""
    if not isinstance(value, str) or not value:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", value)
    return float(m.group(0).replace(",", ".")) if m else None


def hours(value: str | None) -> float | None:
    """Headphone battery: 'До 30 часов' -> 30, '8 часов (36 часов с кейсом)' -> 8"""
    return first_number(value)


def product_type(name: str, category: str) -> str:
    """Shop bundles ('Комплект ...') are listed next to single products; flag them."""
    return "Bundle" if name.lower().startswith("комплект") else "Single"


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["category_en"] = df["category"].map(CATEGORY_EN).fillna(df["category"])
    df["brand"] = df["brand"].fillna("").str.strip()
    # some cards have no brand attribute: use a known brand found in the name, else the first Latin word
    known = {b.lower(): b for b in df["brand"].unique() if b}
    def guess(name: str) -> str:
        words = re.findall(r"[A-Za-z][A-Za-z0-9&+.-]*", name)
        for w in words:
            if w.lower() in known:
                return known[w.lower()]
        return words[0] if words else "Other"
    missing = df["brand"].eq("")
    df.loc[missing, "brand"] = df.loc[missing, "name"].map(guess)
    df["brand"] = df["brand"].replace({"Redmi": "Xiaomi", "Tecno": "TECNO"})
    df.loc[df["brand"].str.startswith("YNDX"), "brand"] = "Yandex"

    df["price"] = pd.to_numeric(df["price"], errors="coerce").where(lambda s: s > 0)
    df["in_stock"] = df["price"].notna()
    df["availability"] = df["availability"].fillna("")
    df.loc[~df["in_stock"], "availability"] = "Нет в наличии"
    df["availability_en"] = df["availability"].map(AVAILABILITY).fillna(df["availability"])

    df["on_sale"] = df["old_price"].notna() & df["in_stock"]
    df["discount_kgs"] = (df["old_price"] - df["price"]).where(df["on_sale"])
    df["discount_pct"] = (100 * df["discount_kgs"] / df["old_price"]).round(1)

    df["rating"] = df["rating"].where(df["reviews"] > 0)      # 0 stars on the card = no reviews yet
    df["product_type"] = [product_type(n, c) for n, c in zip(df["name"], df["category"])]

    sp = df["specs"].map(parse_specs)
    get = lambda key: sp.map(lambda d: d.get(key))  # noqa: E731
    df["ram_gb"] = get("Объем оперативной памяти").map(to_gb)
    df["storage_gb"] = get("Объем встроенной памяти").map(to_gb).fillna(get("Тип и объем накопителя").map(to_gb))
    df["battery_mah"] = get("Емкость аккумулятора").map(first_number)
    df["screen_in"] = get("Диагональ экрана").map(first_number)
    df["matrix"] = get("Тип матрицы")
    df["cpu"] = get("Модель процессора")
    df["gpu"] = get("Модель видеоадаптера")
    df["os"] = get("Операционная система")
    df["laptop_class"] = get("Категория")
    df["volume_l"] = get("Общий объем").map(first_number)
    df["energy_class"] = get("Класс энергопотребления")
    df["no_frost"] = get("Система разморозки No Frost")
    df["load_kg"] = get("Максимальная загрузка белья (стирка)").map(first_number)
    df["spin_rpm"] = get("Макс. скорость отжима").map(first_number)
    df["playtime_h"] = get("Время автономной работы").map(hours)

    cols = ["category", "category_en", "code", "name", "brand", "product_type", "price", "old_price",
            "on_sale", "discount_kgs", "discount_pct", "in_stock", "availability", "availability_en",
            "rating", "reviews", "ram_gb", "storage_gb", "battery_mah", "screen_in", "matrix", "cpu", "gpu",
            "os", "laptop_class", "volume_l", "energy_class", "no_frost", "load_kg", "spin_rpm",
            "playtime_h", "specs", "url"]
    return df[cols]


def load_raw(path: Path) -> pd.DataFrame:
    if path.suffix == ".json":
        return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))["products"])
    return pd.read_csv(path, dtype={"code": str})


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    out = clean(load_raw(src))
    out.to_csv(dst, index=False, encoding="utf-8")
    print(f"{len(out)} rows -> {dst}")
