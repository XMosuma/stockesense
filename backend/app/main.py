from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import connect
from .forecast import run as run_forecast_job
from .importer import import_csv_text
from .reorder import suggest

app = FastAPI(title="StockSense API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# An order counts as "approved" only until the next forecast run.
OPEN_ORDER = """(SELECT o.id FROM orders o WHERE o.shop_id = s.shop_id AND o.product_id = s.product_id
  AND o.status = 'approved'
  AND o.created_at >= COALESCE((SELECT max(trained_at) FROM model_runs), '-infinity'::timestamptz)
  ORDER BY o.id DESC LIMIT 1)"""

DASHBOARD_SQL = f"""
SELECT p.id AS product_id, p.name, s.on_hand, s.lead_time_days AS lead,
  (SELECT array_agg(f.yhat ORDER BY f.day) FROM forecasts f
     WHERE f.shop_id = s.shop_id AND f.product_id = s.product_id) AS fc,
  (SELECT max(f.sd) FROM forecasts f
     WHERE f.shop_id = s.shop_id AND f.product_id = s.product_id) AS sd,
  {OPEN_ORDER} AS order_id
FROM stock_levels s JOIN products p ON p.id = s.product_id
WHERE s.shop_id = %s ORDER BY p.name"""

EMPTY = {"avg": None, "cover": None, "order": None, "status": None}


def _suggest(fc, sd, on_hand, lead):
    return suggest(fc, sd or 0, on_hand, lead) if fc and len(fc) >= 28 else EMPTY


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/shops")
def shops():
    with connect() as c:
        return c.execute("SELECT id, name FROM shops ORDER BY name").fetchall()


@app.get("/api/shops/{shop_id}/dashboard")
def dashboard(shop_id: int):
    with connect() as c:
        rows = c.execute(DASHBOARD_SQL, (shop_id,)).fetchall()
    return [{"product_id": r["product_id"], "name": r["name"], "on_hand": r["on_hand"], "lead": r["lead"],
             "order_id": r["order_id"], **_suggest(r["fc"], r["sd"], r["on_hand"], r["lead"])} for r in rows]


@app.get("/api/shops/{shop_id}/products/{product_id}")
def product(shop_id: int, product_id: int):
    args = (shop_id, product_id)
    with connect() as c:
        st = c.execute(
            f"SELECT p.name, s.on_hand, s.lead_time_days AS lead, s.shop_id, {OPEN_ORDER} AS order_id "
            "FROM stock_levels s JOIN products p ON p.id = s.product_id "
            "WHERE s.shop_id = %s AND s.product_id = %s", args).fetchone()
        if not st:
            raise HTTPException(404, "Unknown shop or product.")
        hist = c.execute("SELECT day::text AS day, units FROM daily_sales WHERE shop_id = %s AND product_id = %s "
                         "ORDER BY day DESC LIMIT 42", args).fetchall()[::-1]
        fc = c.execute("SELECT day::text AS day, yhat, sd FROM forecasts WHERE shop_id = %s AND product_id = %s "
                       "ORDER BY day", args).fetchall()
    s = _suggest([f["yhat"] for f in fc], fc[0]["sd"] if fc else 0, st["on_hand"], st["lead"])
    return {"name": st["name"], "on_hand": st["on_hand"], "lead": st["lead"], "order_id": st["order_id"],
            "history": hist, "forecast": fc, **s}


class StockIn(BaseModel):
    on_hand: int = Field(ge=0)


@app.put("/api/shops/{shop_id}/products/{product_id}/stock")
def set_stock(shop_id: int, product_id: int, body: StockIn):
    with connect() as c:
        r = c.execute("UPDATE stock_levels SET on_hand = %s, updated_at = now() "
                      "WHERE shop_id = %s AND product_id = %s RETURNING on_hand",
                      (body.on_hand, shop_id, product_id)).fetchone()
    if not r:
        raise HTTPException(404, "Unknown shop or product.")
    return r


class OrderIn(BaseModel):
    shop_id: int
    product_id: int
    qty: int = Field(gt=0)


@app.post("/api/orders")
def create_order(body: OrderIn):
    with connect() as c:
        if not c.execute("SELECT 1 FROM stock_levels WHERE shop_id = %s AND product_id = %s",
                         (body.shop_id, body.product_id)).fetchone():
            raise HTTPException(404, "Unknown shop or product.")
        return c.execute("INSERT INTO orders (shop_id, product_id, qty) VALUES (%s, %s, %s) RETURNING id",
                         (body.shop_id, body.product_id, body.qty)).fetchone()


@app.post("/api/orders/{order_id}/cancel")
def cancel_order(order_id: int):
    with connect() as c:
        r = c.execute("UPDATE orders SET status = 'cancelled' WHERE id = %s AND status = 'approved' RETURNING id",
                      (order_id,)).fetchone()
    if not r:
        raise HTTPException(404, "No approved order with that id.")
    return r


@app.post("/api/import")
async def import_file(file: UploadFile = File(...), run_forecast: bool = True):
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        with connect() as c:
            res = import_csv_text(c, text)
            if run_forecast:
                res["forecast"] = run_forecast_job(c)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return res


@app.post("/api/forecast/run")
def forecast_now():
    try:
        with connect() as c:
            return run_forecast_job(c)
    except ValueError as e:
        raise HTTPException(400, str(e))
