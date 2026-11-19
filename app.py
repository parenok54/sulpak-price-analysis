"""Interactive dashboard for the Sulpak.kg catalog snapshot.

    streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data" / "sulpak_clean.csv"
BLUE, ORANGE, AQUA, NEUTRAL = "#2a78d6", "#eb6834", "#1baf7a", "#c9c8c2"
AVAIL_COLORS = {"In stock (shop)": BLUE, "Display unit": ORANGE, "Available to order": AQUA, "Out of stock": NEUTRAL}
INK_2, GRID = "#52514e", "#e6e5e0"

st.set_page_config(page_title="Sulpak.kg price explorer", page_icon="📊", layout="wide")


@st.cache_data
def load() -> pd.DataFrame:
    return pd.read_csv(DATA, dtype={"code": str})


def style(fig, height=380):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(size=13), legend_title_text="",
                      hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


df = load()

st.title("Sulpak.kg price explorer")
st.caption(f"{len(df):,} product listings from the public catalog of sulpak.kg, snapshot of 19 Nov 2026. "
           "Prices in Kyrgyz som. Source code and analysis: github.com/parenok54/sulpak-price-analysis")

# --- filters, one row above everything -------------------------------------------------------
c1, c2, c3, c4 = st.columns([2, 3, 3, 2])
categories = sorted(df.category_en.unique())
category = c1.selectbox("Category", categories, index=categories.index("Smartphones"))
cat = df[df.category_en == category]
brand_counts = cat.brand.value_counts()
brands = c2.multiselect("Brands", brand_counts.index.tolist(), placeholder="All brands")
lo, hi = int(cat.price.min(skipna=True)), int(cat.price.max(skipna=True))
price = c3.slider("Price, som", lo, hi, (lo, hi), step=max(1, (hi - lo) // 200))
only_stock = c4.toggle("Only available", value=True, help="Hide out-of-stock listings")
only_sale = c4.toggle("Only on sale", value=False)

view = cat if not brands else cat[cat.brand.isin(brands)]
priced = view[view.price.between(*price)]
shown = priced if only_stock else pd.concat([priced, view[~view.in_stock]])
if only_sale:
    shown = shown[shown.on_sale]

# --- headline numbers ----------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Listings", f"{len(shown):,}")
k2.metric("Available", f"{view.in_stock.mean():.0%}" if len(view) else "–",
          help="Share of listings in this category/brand selection that can be bought")
k3.metric("Median price", f"{shown.price.median():,.0f} som" if shown.price.notna().any() else "–")
sale = shown[shown.in_stock]
k4.metric("On sale", f"{sale.on_sale.mean():.0%}" if len(sale) else "–",
          help="Share of available products with an old (crossed-out) price")

if shown.empty:
    st.info("No products match these filters.")
    st.stop()

# --- charts ----------------------------------------------------------------------------------
left, right = st.columns(2)
top = shown[shown.in_stock].brand.value_counts().head(10).index
box = shown[shown.in_stock & shown.brand.isin(top)]
order = box.groupby("brand").price.median().sort_values().index.tolist()
fig = px.box(box, x="price", y="brand", points="all", category_orders={"brand": order},
             color_discrete_sequence=[BLUE], hover_data={"name": True, "price": ":,.0f", "brand": False},
             labels={"price": "Price, som", "brand": ""}, title="Price by brand (top 10 by listings)")
fig.update_traces(marker=dict(size=6, opacity=.55), line=dict(width=1.5))
left.plotly_chart(style(fig, 420), width="stretch")

avail = view.groupby(["brand", "availability_en"]).size().reset_index(name="n")
avail = avail[avail.brand.isin(view.brand.value_counts().head(10).index)]
fig = px.bar(avail, x="n", y="brand", color="availability_en", orientation="h",
             color_discrete_map=AVAIL_COLORS, category_orders={"availability_en": list(AVAIL_COLORS)},
             labels={"n": "Listings", "brand": "", "availability_en": ""}, title="Availability by brand")
fig.update_traces(marker_line_color="white", marker_line_width=1.5)
fig.update_layout(legend=dict(orientation="h", y=-0.15), yaxis=dict(categoryorder="total ascending"))
right.plotly_chart(style(fig, 420), width="stretch")

spec = {"Smartphones": "storage_gb", "Tablets": "storage_gb", "Laptops": "ram_gb", "Fridges": "volume_l",
        "Washing machines": "load_kg", "Headphones": "playtime_h"}.get(category)
spec_label = {"storage_gb": "Storage, GB", "ram_gb": "RAM, GB", "volume_l": "Volume, l",
              "load_kg": "Load, kg", "playtime_h": "Battery life, h"}
sc = shown[shown.in_stock & shown[spec].notna()] if spec else pd.DataFrame()
if spec and len(sc):
    fig = px.strip(sc, x=spec, y="price", hover_data={"name": True, "brand": True, "price": ":,.0f"},
                   color_discrete_sequence=[BLUE], labels={spec: spec_label[spec], "price": "Price, som"},
                   title=f"Price vs {spec_label[spec].split(',')[0].lower()}")
    fig.update_traces(marker=dict(size=8, opacity=.6, line=dict(width=1, color="white")))
    if spec in ("storage_gb", "ram_gb"):
        fig.update_xaxes(type="category", categoryorder="array",
                         categoryarray=sorted(sc[spec].unique()))
    st.plotly_chart(style(fig, 380), width="stretch")

deals = shown[shown.on_sale].nlargest(15, "discount_kgs")
if len(deals):
    st.subheader("Biggest discounts")
    st.dataframe(deals[["name", "brand", "price", "old_price", "discount_kgs", "discount_pct", "url"]],
                 hide_index=True, width="stretch",
                 column_config={"price": st.column_config.NumberColumn("Price", format="%d"),
                                "old_price": st.column_config.NumberColumn("Old price", format="%d"),
                                "discount_kgs": st.column_config.NumberColumn("Saving, som", format="%d"),
                                "discount_pct": st.column_config.NumberColumn("Discount", format="%.0f%%"),
                                "url": st.column_config.LinkColumn("Link", display_text="open")})

st.subheader("All products")
cols = ["name", "brand", "price", "old_price", "availability_en", "reviews", "specs", "url"]
st.dataframe(shown[cols].sort_values("price"), hide_index=True, width="stretch", height=420,
             column_config={"price": st.column_config.NumberColumn("Price", format="%d"),
                            "old_price": st.column_config.NumberColumn("Old price", format="%d"),
                            "availability_en": "Availability",
                            "url": st.column_config.LinkColumn("Link", display_text="open")})
st.download_button("Download this selection as CSV", shown[cols].to_csv(index=False).encode("utf-8"),
                   file_name=f"sulpak_{category.lower().replace(' ', '_')}.csv", mime="text/csv")
