"""Load a CSV of daily sales into Postgres. Works for any shops and products.

Columns: date, product, units_sold (required); shop, stock_on_hand, lead_time_days (optional).
Re-importing the same days overwrites them, so files can overlap safely.
"""
import io

import pandas as pd

REQUIRED = {"date", "product", "units_sold"}


def _upsert_names(cur, table, names):
    ids = {}
    for n in names:
        cur.execute(
            f"INSERT INTO {table} (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (n,))
        ids[n] = cur.fetchone()["id"]
    return ids


def import_df(conn, df):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(sorted(missing))}.")
    if df.empty:
        raise ValueError("The file has no data rows.")
    if "shop" not in df:
        df["shop"] = "My shop"
    df["shop"] = df["shop"].fillna("My shop").astype(str).str.strip()
    df["product"] = df["product"].astype(str).str.strip()
    try:
        df["day"] = pd.to_datetime(df["date"]).dt.date
    except Exception:
        raise ValueError("Some dates could not be read. Use YYYY-MM-DD.")
    df["units"] = pd.to_numeric(df["units_sold"], errors="coerce")
    if df["units"].isna().any():
        raise ValueError("Some units_sold values are not numbers.")
    df["units"] = df["units"].clip(lower=0).round().astype(int)
    span = (df["day"].max() - df["day"].min()).days + 1
    if span < 28:
        raise ValueError(f"Need at least 28 days of history (found {span}).")

    sales = df.groupby(["shop", "product", "day"], as_index=False)["units"].sum()
    with conn.cursor() as cur:
        shops = _upsert_names(cur, "shops", sales["shop"].unique())
        prods = _upsert_names(cur, "products", sales["product"].unique())
        cur.executemany(
            "INSERT INTO daily_sales (shop_id, product_id, day, units) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (shop_id, product_id, day) DO UPDATE SET units = EXCLUDED.units",
            [(shops[r.shop], prods[r.product], r.day, int(r.units)) for r in sales.itertuples()])

        for (shop, prod), g in df.sort_values("day").groupby(["shop", "product"]):
            stock = g["stock_on_hand"].dropna() if "stock_on_hand" in g else pd.Series(dtype=float)
            lead = g["lead_time_days"].dropna() if "lead_time_days" in g else pd.Series(dtype=float)
            key = (shops[shop], prods[prod])
            if len(stock):
                cur.execute(
                    "INSERT INTO stock_levels (shop_id, product_id, on_hand, lead_time_days) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (shop_id, product_id) DO UPDATE SET on_hand = EXCLUDED.on_hand, "
                    "lead_time_days = EXCLUDED.lead_time_days, updated_at = now()",
                    (*key, max(0, int(stock.iloc[-1])), max(1, min(21, int(lead.iloc[-1]))) if len(lead) else 5))
            else:  # no stock info: start from one week of recent sales, keep existing rows untouched
                cur.execute(
                    "INSERT INTO stock_levels (shop_id, product_id, on_hand) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (*key, int(g["units"].tail(7).sum())))
    conn.commit()
    return {"rows": int(len(df)), "shops": int(len(shops)), "products": int(len(prods)), "days": int(span)}


def import_csv_text(conn, text):
    return import_df(conn, pd.read_csv(io.StringIO(text)))
