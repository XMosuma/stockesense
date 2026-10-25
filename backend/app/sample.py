"""Generated sample data: 3 shops with different volumes, weekday patterns and product ranges."""
import numpy as np
import pandas as pd

SHOPS = [("Downtown", 1.0, 1.0), ("Suburb Mall", 0.6, 1.4), ("Airport Kiosk", 1.8, 1.0)]
WEEK = {"Downtown": [.8, .85, .9, .95, 1.15, 1.45, 1.0],
        "Suburb Mall": [.7, .7, .8, .9, 1.2, 1.7, 1.5],
        "Airport Kiosk": [1.1, 1, 1, 1.05, 1.15, .9, .95]}
# name, base units/day, trend over the period, stock, lead time days
PRODUCTS = [("Oat milk 1L", 60, .35, 420, 5), ("Sourdough loaf", 90, .05, 260, 2),
            ("Free-range eggs x12", 120, -.1, 500, 3), ("Sparkling water 6pk", 70, .5, 1900, 7),
            ("Greek yogurt 500g", 55, .2, 160, 4), ("Bananas 1kg", 150, 0, 700, 2),
            ("Dish soap 500ml", 25, -.2, 1100, 10), ("Ice cream 1L", 40, .6, 150, 6)]


def make_sample(days=120):
    rng = np.random.default_rng(7)
    end = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    rows = []
    for si, (shop, scale, stock_mult) in enumerate(SHOPS):
        for pi, (name, base, trend, stock, lead) in enumerate(PRODUCTS[2:7] if si == 2 else PRODUCTS):
            g = -.3 if (si == 1 and pi % 3 == 0) else trend
            for d in range(days):
                day = end - pd.Timedelta(days=days - 1 - d)
                v = base * scale * (1 + g * d / days) * WEEK[shop][day.dayofweek] * (1 + (rng.random() - .5) * .3)
                if rng.random() < .04:
                    v *= 1.6
                last = d == days - 1
                rows.append({"date": day.date().isoformat(), "shop": shop, "product": name,
                             "units_sold": max(0, round(v)),
                             "stock_on_hand": round(stock * scale * stock_mult) if last else None,
                             "lead_time_days": lead if last else None})
    return pd.DataFrame(rows)
