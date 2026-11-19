from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clean import clean, first_number, parse_specs, to_gb  # noqa: E402


def test_parse_specs_skips_empty_values():
    d = parse_specs("Объем оперативной памяти: 8 GB / Габариты (В х Ш х Г): - мм / Тип матрицы: AMOLED")
    assert d == {"Объем оперативной памяти": "8 GB", "Тип матрицы": "AMOLED"}


def test_units():
    assert to_gb("256 GB") == 256 and to_gb("2 TB") == 2048 and to_gb("SSD 1TB") == 1024
    assert to_gb(None) is None and to_gb(float("nan")) is None
    assert first_number("11,5″ - 29,21 см") == 11.5 and first_number("7000 мАч") == 7000


def test_clean_derives_fields():
    raw = pd.DataFrame([
        dict(category="Смартфоны", code="1", name="Смартфон Foo 8/256", brand="Foo", price=90.0, old_price=100.0,
             discount_pct=10, rating=5, reviews=3, availability="", specs="Объем оперативной памяти: 8 GB / Объем встроенной памяти: 256 GB", url=""),
        dict(category="Смартфоны", code="2", name="Комплект Смартфон Bar", brand="", price=None, old_price=None,
             discount_pct=None, rating=0, reviews=0, availability="", specs="", url=""),
    ])
    out = clean(raw)
    a, b = out.iloc[0], out.iloc[1]
    assert a.in_stock and a.on_sale and a.discount_kgs == 10 and a.discount_pct == 10
    assert a.ram_gb == 8 and a.storage_gb == 256 and a.availability_en == "Available to order"
    assert not b.in_stock and b.availability_en == "Out of stock" and b.product_type == "Bundle"
    assert pd.isna(b.rating) and b.brand == "Bar"
