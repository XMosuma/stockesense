import { useState } from "react";
import { api } from "./api";

export default function DataLoader({ onLoaded }) {
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(job, ok) {
    setBusy(true);
    setMsg(null);
    try {
      const res = await job();
      setMsg({ ok: true, text: ok(res) });
      await onLoaded();
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="card">
      <summary>Load your own data (CSV)</summary>
      <p className="leg">
        Required columns: <b>date, product, units_sold</b>. Optional: <b>shop, stock_on_hand, lead_time_days</b>.
        One row per product per day, at least 28 days. Each shop in the file appears in the shop menu.
        Re-uploading a day replaces it.
      </p>
      <pre className="leg">{`date,shop,product,units_sold,stock_on_hand,lead_time_days
2026-09-01,Downtown,Oat milk 1L,58,420,5`}</pre>
      <div className="row">
        <input
          type="file" accept=".csv,text/csv" disabled={busy} aria-label="Choose a CSV file"
          onChange={(e) => e.target.files[0] && run(
            () => api.importCsv(e.target.files[0]),
            (r) => `Loaded ${r.rows} rows: ${r.shops} shop(s), ${r.products} product(s), ${r.days} days. Forecast updated.`,
          )}
        />
        <button className="quiet" disabled={busy} onClick={() => run(api.runForecast, (r) => `Forecast updated for ${r.series} series.`)}>
          Update forecast
        </button>
      </div>
      {msg && <p className={msg.ok ? "okk" : "risk"} role="status">{msg.text}</p>}
    </details>
  );
}
