"""Demand forecasting: one global LightGBM model across all shop/product series.

Features: lags (1, 7, 14, 28 days), rolling means (7, 28), weekday, day of month, series id.
Forecasts are made recursively for HORIZON days. The spread (sd) comes from errors on a
14-day holdout. Series with too little history fall back to a weekday average.
"""
import lightgbm as lgb
import numpy as np
import pandas as pd

HORIZON = 28
MIN_DAYS = 42
FEATS = ["lag1", "lag7", "lag14", "lag28", "rm7", "rm28", "dow", "dom", "series"]
PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=10, verbose=-1)


def _complete(df):
    """Fill missing days with 0 units, from each series' first day to the last day in the data."""
    last = df["day"].max()
    parts = []
    for s, g in df.groupby("series"):
        idx = pd.date_range(g["day"].min(), last)
        u = g.groupby("day")["units"].sum().reindex(idx, fill_value=0)
        parts.append(pd.DataFrame({"series": s, "day": idx, "units": u.values.astype(float)}))
    return pd.concat(parts, ignore_index=True)


def _panel(df):
    df = df.sort_values(["series", "day"]).reset_index(drop=True)
    g = df.groupby("series")["units"]
    for k in (1, 7, 14, 28):
        df[f"lag{k}"] = g.shift(k)
    prev = g.shift(1)
    for w in (7, 28):
        df[f"rm{w}"] = prev.groupby(df["series"]).rolling(w).mean().reset_index(level=0, drop=True)
    df["dow"] = df["day"].dt.dayofweek
    df["dom"] = df["day"].dt.day
    return df


def _weekday_mean(g, last, horizon):
    tail = g.tail(28)
    by = tail.groupby(tail["day"].dt.dayofweek)["units"].mean()
    overall = float(tail["units"].mean())
    out = []
    for i in range(horizon):
        d = last + pd.Timedelta(days=i + 1)
        out.append((d, float(by.get(d.dayofweek, overall))))
    return out


def forecast_frame(df, horizon=HORIZON):
    """df columns: shop_id, product_id, day, units. Returns (forecast_df, meta)."""
    df = df.copy()
    df["day"] = pd.to_datetime(df["day"])
    df["series"] = df.groupby(["shop_id", "product_id"]).ngroup()
    keys = df.drop_duplicates("series").set_index("series")[["shop_id", "product_id"]]
    df = _complete(df)
    last = df["day"].max()
    counts = df.groupby("series").size()
    ok = list(counts[counts >= MIN_DAYS].index)
    recent_sd = df.groupby("series")["units"].apply(lambda u: float(u.tail(28).std(ddof=0)))
    sd = recent_sd.to_dict()
    rows, mae, method = [], None, "weekday-average"

    if ok:
        method = "lightgbm"
        pan = _panel(df[df["series"].isin(ok)]).dropna(subset=FEATS)
        cut = last - pd.Timedelta(days=14)
        trn, val = pan[pan["day"] <= cut], pan[pan["day"] > cut]
        if len(trn) > 100 and len(val) > 0:
            m = lgb.LGBMRegressor(**PARAMS).fit(trn[FEATS], trn["units"], categorical_feature=["series"])
            res = val["units"] - m.predict(val[FEATS])
            mae = float(res.abs().mean())
            for s, v in res.groupby(val["series"]).std().dropna().items():
                sd[s] = float(v)
        m = lgb.LGBMRegressor(**PARAMS).fit(pan[FEATS], pan["units"], categorical_feature=["series"])
        hist = {s: list(g["units"].values[-28:]) for s, g in df[df["series"].isin(ok)].groupby("series")}
        for i in range(horizon):
            day = last + pd.Timedelta(days=i + 1)
            X = pd.DataFrame(
                [[h[-1], h[-7], h[-14], h[-28], np.mean(h[-7:]), np.mean(h[-28:]), day.dayofweek, day.day, s]
                 for s, h in hist.items()], columns=FEATS)
            for s, v in zip(hist, np.clip(m.predict(X), 0, None)):
                hist[s].append(float(v))
                rows.append((s, day, float(v)))

    for s, g in df[~df["series"].isin(ok)].groupby("series"):
        rows += [(s, d, v) for d, v in _weekday_mean(g, last, horizon)]

    out = pd.DataFrame(rows, columns=["series", "day", "yhat"])
    out["sd"] = out["series"].map(sd).fillna(0.0)
    out["shop_id"] = out["series"].map(keys["shop_id"])
    out["product_id"] = out["series"].map(keys["product_id"])
    meta = {"method": method, "series": int(len(counts)), "mae": mae, "fallback_series": int(len(counts) - len(ok))}
    return out[["shop_id", "product_id", "day", "yhat", "sd"]], meta


def run(conn):
    """Read sales from Postgres, forecast, store forecasts and a model_runs row."""
    rows = conn.execute("SELECT shop_id, product_id, day, units FROM daily_sales").fetchall()
    if not rows:
        raise ValueError("No sales data loaded yet.")
    fc, meta = forecast_frame(pd.DataFrame(rows))
    run_id = conn.execute(
        "INSERT INTO model_runs (method, series, mae) VALUES (%s, %s, %s) RETURNING id",
        (meta["method"], meta["series"], meta["mae"])).fetchone()["id"]
    conn.execute("DELETE FROM forecasts")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO forecasts (shop_id, product_id, day, yhat, sd) VALUES (%s, %s, %s, %s, %s)",
            [(int(r.shop_id), int(r.product_id), r.day.date(), float(r.yhat), float(r.sd)) for r in fc.itertuples()])
    conn.commit()
    return {**meta, "run_id": run_id, "rows": len(fc)}
