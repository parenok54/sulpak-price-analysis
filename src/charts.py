"""Static charts for the notebook and README (matplotlib, light theme).

Colours: validated categorical palette (blue / orange / aqua in fixed order), a neutral grey for
"absent" states, text in ink tokens rather than series colours.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#8a8984"
GRID = "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
NEUTRAL = "#c9c8c2"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlepad": 24, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
})

som = FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k" if v >= 1000 else f"{v:,.0f}")


def _subtitle(ax, text):
    ax.text(0, 1.015, text, transform=ax.transAxes, color=INK_2, fontsize=9.5, va="bottom")


def price_ranges(df: pd.DataFrame, ax=None):
    """Median price per category with the middle 80% of prices (p10-p90)."""
    s = df[df.in_stock].groupby("category_en")["price"]
    t = pd.DataFrame({"p10": s.quantile(.1), "med": s.median(), "p90": s.quantile(.9), "n": s.size()}).sort_values("med")
    ax = ax or plt.subplots(figsize=(8.5, 4.2))[1]
    y = np.arange(len(t))
    ax.hlines(y, t.p10, t.p90, color=BLUE, alpha=.35, lw=7, capstyle="round")
    ax.plot(t.med, y, "o", ms=9, color=BLUE, mec=SURFACE, mew=2)
    for i, (_, r) in enumerate(t.iterrows()):
        ax.text(r.p90 * 1.12, i, f"{r.med:,.0f} som", va="center", color=INK, fontsize=9.5)
    ax.set_yticks(y, [f"{c}  (n={n})" for c, n in zip(t.index, t.n)])
    ax.set_xscale("log"); ax.xaxis.set_major_formatter(som)
    ax.set_xlim(t.p10.min() * .6, t.p90.max() * 3.2)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Price, som (log scale)")
    ax.set_title("What things cost at Sulpak.kg")
    _subtitle(ax, "Dot = median price of in-stock products, bar = middle 80% (10th–90th percentile)")
    return ax


AVAIL_ORDER = ["In stock (shop)", "Display unit", "Available to order", "Out of stock"]
AVAIL_COLORS = [BLUE, ORANGE, AQUA, NEUTRAL]


def availability(df: pd.DataFrame, ax=None):
    """Share of listings by availability status, per category (100% stacked bars)."""
    t = pd.crosstab(df.category_en, df.availability_en, normalize="index")[AVAIL_ORDER]
    t = t.sort_values("Out of stock")
    ax = ax or plt.subplots(figsize=(8.5, 4.2))[1]
    left = np.zeros(len(t))
    for col, color in zip(AVAIL_ORDER, AVAIL_COLORS):
        v = t[col].values
        ax.barh(t.index, v, left=left, color=color, height=.62, edgecolor=SURFACE, linewidth=2, label=col)
        for i, (l, w) in enumerate(zip(left, v)):
            if w >= .07:
                ax.text(l + w / 2, i, f"{w:.0%}", ha="center", va="center", fontsize=8.5,
                        color=INK if color in (AQUA, NEUTRAL, ORANGE) else "white")
        left += v
    ax.set_xlim(0, 1); ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.grid(visible=False)
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.08), frameon=False, fontsize=9, handlelength=1.2)
    ax.set_title("Two in five listings can't be bought right now")
    _subtitle(ax, "Share of catalog listings by availability status")
    return ax


def discounts(df: pd.DataFrame):
    """Two small charts: how often a category is discounted, and how deep the discount is."""
    s = df[df.in_stock]
    share = s.groupby("category_en")["on_sale"].mean().sort_values()
    depth = s[s.on_sale].groupby("category_en")["discount_pct"].median().reindex(share.index)
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, gridspec_kw={"wspace": .08})
    a.barh(share.index, share.values, color=BLUE, height=.6)
    for i, v in enumerate(share.values):
        a.text(v + .01, i, f"{v:.0%}", va="center", fontsize=9)
    a.set_xlim(0, share.max() * 1.25); a.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    a.grid(axis="y", visible=False); a.set_title("How often", fontsize=11)
    a.set_xlabel("Share of in-stock products on sale")
    b.barh(depth.index, depth.values, color=BLUE, height=.6)
    for i, v in enumerate(depth.values):
        b.text(v + .5, i, f"−{v:.0f}%", va="center", fontsize=9)
    b.set_xlim(0, depth.max() * 1.25); b.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    b.grid(axis="y", visible=False); b.set_title("How deep", fontsize=11)
    b.set_xlabel("Median discount of products on sale")
    fig.suptitle("Appliances go on sale most often, headphones get the deepest cuts",
                 x=0.125, ha="left", fontsize=13, fontweight="bold", y=1.03)
    return fig


def phone_brands(df: pd.DataFrame, storage_gb=256, min_n=3, ax=None):
    """Median price of in-stock smartphones with the same storage, by brand."""
    ph = df[(df.category_en == "Smartphones") & df.in_stock & (df.storage_gb == storage_gb)]
    g = ph.groupby("brand")["price"].agg(["median", "size"]).query("size >= @min_n").sort_values("median")
    ax = ax or plt.subplots(figsize=(8.5, 4.2))[1]
    ax.barh(g.index, g["median"], color=BLUE, height=.6)
    for i, (m, n) in enumerate(zip(g["median"], g["size"])):
        ax.text(m + g["median"].max() * .015, i, f"{m:,.0f} som", va="center", fontsize=9)
        ax.text(m + g["median"].max() * .2, i, f"n={n}", va="center", fontsize=8.5, color=INK_3)
    ax.set_xlim(0, g["median"].max() * 1.32); ax.xaxis.set_major_formatter(som)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Median price, som")
    ax.set_title(f"Same {storage_gb} GB of storage, 7× the price")
    _subtitle(ax, f"Median price of in-stock {storage_gb} GB smartphones by brand (brands with ≥{min_n} models)")
    return ax


def laptop_ram(df: pd.DataFrame, ax=None):
    lp = df[(df.category_en == "Laptops") & df.in_stock & df.ram_gb.isin([8, 16, 24, 32])]
    g = lp.groupby("ram_gb")["price"].agg(["median", "size"])
    ax = ax or plt.subplots(figsize=(7.5, 4.2))[1]
    labels = [f"{int(r)} GB\nn={n}" for r, n in zip(g.index, g["size"])]
    ax.bar(labels, g["median"], color=BLUE, width=.55)
    for i, m in enumerate(g["median"]):
        ax.text(i, m + g["median"].max() * .02, f"{m:,.0f}", ha="center", fontsize=9.5)
    ax.yaxis.set_major_formatter(som); ax.grid(axis="x", visible=False)
    ax.spines["bottom"].set_visible(True)
    ax.set_ylabel("Median price, som")
    ax.set_title("Laptops: twice the RAM, twice the price — up to 24 GB")
    _subtitle(ax, "Median price of in-stock laptops by RAM. RAM stands in for the class of machine, not memory alone")
    return ax
