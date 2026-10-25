# StockSense

Demand forecasting and smart reordering for retail shops. Each shop has its own sales history,
stock levels and lead times, so you can load data for one shop or many.

| Layer | Tool | Where |
|---|---|---|
| Data storage | PostgreSQL 16 | `db/schema.sql` |
| Pipelines | Python import job + daily scheduler | `backend/app/importer.py`, `backend/app/daily.py` |
| Modelling | LightGBM | `backend/app/forecast.py` |
| Application | FastAPI + React (Vite) | `backend/app/main.py`, `frontend/` |

## Run it

You need Docker with Compose.

```bash
docker compose up --build -d
docker compose exec api python -m app.seed     # loads 3 sample shops and runs the first forecast
```

Open http://localhost:5173. API docs are at http://localhost:8000/docs.

To stop: `docker compose down` (add `-v` to also delete the database).

## Use your own data

CSV columns:

| Column | Required | Notes |
|---|---|---|
| `date` | yes | `YYYY-MM-DD` |
| `product` | yes | Product name |
| `units_sold` | yes | Units sold that day |
| `shop` | no | Shop name. Missing means one shop called "My shop" |
| `stock_on_hand` | no | Current stock. The last value per product is used. Missing means one week of recent sales |
| `lead_time_days` | no | Days from order to delivery (1-21). Default 5 |

Rules: one row per product per day, at least 28 days of history (about 6 weeks or more gives the best
forecasts). Days with no row count as zero sales. Re-importing a day replaces it, so files can overlap.
`data/example_upload.csv` shows the format.

Three ways to load it:
1. **In the app:** "Load your own data (CSV)" at the bottom of the page.
2. **Daily, automatically:** drop CSV exports into `data/inbox/`. The `scheduler` container imports them every
   24 hours, then re-forecasts. Imported files move to `data/processed/`; bad files become `*.failed` and the
   reason is in `docker compose logs scheduler`.
3. **Command line:** `docker compose exec api python -m app.daily`

## How the forecast works

One LightGBM model is trained across all shops and products together, using lagged sales (1, 7, 14, 28
days), rolling averages, weekday, day of month and the shop/product series. It predicts 28 days ahead,
one day at a time. The likely range comes from the model's errors on the most recent 14 days. Series with
fewer than 42 days of history use a weekday average instead.

Suggested order = forecast demand over (lead time + 7 days) + safety stock - stock on hand, rounded up to
the next 10. Safety stock = 1.28 x forecast spread x sqrt(lead time), about a 90% service level.
Change `Z` and the rounding in `backend/app/reorder.py`.

The model retrains from scratch on every forecast run (seconds at this scale). The status rules
(`risk` if days of cover < lead time + 2, `over` if more than 40 days) are also in `reorder.py`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/shops` | List shops |
| GET | `/api/shops/{shop}/dashboard` | Products with stock, forecast, status, suggested order |
| GET | `/api/shops/{shop}/products/{product}` | History, forecast and suggestion for one product |
| PUT | `/api/shops/{shop}/products/{product}/stock` | Update stock on hand |
| POST | `/api/orders` / `/api/orders/{id}/cancel` | Approve or undo an order |
| POST | `/api/import` | Upload a CSV (re-forecasts unless `?run_forecast=false`) |
| POST | `/api/forecast/run` | Re-run the forecast now |

## Run without Docker

```bash
# 1. Postgres with the schema
createdb stocksense && psql stocksense -f db/schema.sql
# 2. Backend
cd backend && pip install -r requirements.txt
export DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/stocksense
python -m app.seed && uvicorn app.main:app --port 8000
# 3. Front end (new terminal)
cd frontend && npm install && npm run dev
```

## Before using real shop data in production

This is a working first version, not a hardened one. Still to add:
- **Login and permissions.** Anyone who can reach the API can read and change everything.
- **Secrets.** The database password in `docker-compose.yml` is an example; use your own and keep it out of git.
- **Orders go nowhere yet.** Approving an order records it in the `orders` table. Sending it to a supplier or
  ERP is a separate integration.
- **A production web server.** The `web` container runs the Vite dev server. For production, run
  `npm run build` and serve `frontend/dist` behind HTTPS.
- **Backups and monitoring** for Postgres, and a check on `model_runs.mae` to spot forecasts getting worse.
- **Larger volumes.** The importer uses plain batched inserts, fine for hundreds of thousands of rows.
  Millions would want `COPY` and incremental training.

## Tested

Checked in a development sandbox: schema, seed, forecast (LightGBM beat a simple 28-day-average baseline on a
14-day holdout), every API route including error cases, CSV import of a new shop, the daily job with good and
bad files, and the front end production build plus the dev proxy to the API. Not tested: the Docker images
themselves, or the UI in a real browser.
