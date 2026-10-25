import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Chart from "./Chart.jsx";
import DataLoader from "./DataLoader.jsx";

const LABEL = { risk: "At risk", over: "Overstocked", ok: "OK" };

export default function App() {
  const [shops, setShops] = useState(null);
  const [shopId, setShopId] = useState(null);
  const [rows, setRows] = useState([]);
  const [sel, setSel] = useState(null);
  const [error, setError] = useState("");

  const loadShops = useCallback(async () => {
    const list = await api.shops();
    setShops(list);
    setShopId((id) => (id && list.some((s) => s.id === id) ? id : list[0]?.id ?? null));
  }, []);

  const loadRows = useCallback(async () => {
    if (shopId == null) return setRows([]);
    const r = await api.dashboard(shopId);
    setRows(r);
    setSel((cur) => (cur && r.some((x) => x.product_id === cur) ? cur : r[0]?.product_id ?? null));
  }, [shopId]);

  const guard = (fn) => { fn().then(() => setError("")).catch((e) => setError(e.message)); };
  useEffect(() => { guard(loadShops); }, [loadShops]);
  useEffect(() => { guard(loadRows); }, [loadRows]);
  const refreshAll = async () => { await loadShops(); await loadRows(); };

  const count = (s) => rows.filter((r) => r.status === s).length;
  const pending = rows.filter((r) => r.order > 0 && !r.order_id).length;
  const approved = rows.filter((r) => r.order_id).length;

  return (
    <>
      <header>
        <h1>StockSense</h1>
        <p>Demand forecasts and reorder suggestions for every shop.</p>
      </header>
      <main>
        {error && <p className="risk" role="alert">Could not reach the server: {error}</p>}

        {shops && shops.length === 0 && (
          <p className="card">No data yet. Load a CSV below, or run <code>python -m app.seed</code> for sample shops.</p>
        )}

        {shops && shops.length > 0 && (
          <>
            <div className="card row" style={{ margin: 0 }}>
              <label>Shop{" "}
                <select value={shopId ?? ""} onChange={(e) => { setShopId(+e.target.value); setSel(null); }}>
                  {shops.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </label>
            </div>

            <div className="kpis">
              {[["Items at risk", count("risk")], ["Overstocked", count("over")],
                ["Orders to approve", pending], ["Orders approved", approved]].map(([label, n]) => (
                <div className="card k" key={label}><b>{n}</b><span>{label}</span></div>
              ))}
            </div>

            <div className="card wrap">
              <table>
                <thead><tr><th>Product</th><th>On hand</th><th>Forecast / day</th><th>Days of cover</th><th>Status</th><th>Suggested order</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.product_id} className={r.product_id === sel ? "sel" : ""}
                        onClick={() => setSel(r.product_id)} tabIndex={0}
                        onKeyDown={(e) => e.key === "Enter" && setSel(r.product_id)}>
                      <td>{r.name}</td><td>{r.on_hand}</td>
                      <td>{r.avg == null ? "–" : r.avg.toFixed(0)}</td>
                      <td>{r.cover == null ? "–" : r.cover.toFixed(1)}</td>
                      <td>{r.status ? <span className={`tag ${r.status}`}>{LABEL[r.status]}</span> : "No forecast yet"}</td>
                      <td>{r.order || "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {sel != null && <Detail shopId={shopId} productId={sel} version={rows} onChange={loadRows} />}
          </>
        )}

        <DataLoader onLoaded={refreshAll} />
      </main>
    </>
  );
}

function Detail({ shopId, productId, version, onChange }) {
  const [d, setD] = useState(null);
  const [stock, setStock] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    let live = true;
    api.product(shopId, productId).then((x) => { if (live) { setD(x); setStock(String(x.on_hand)); } }).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [shopId, productId, version]);

  if (!d) return <div className="card">{err || "Loading…"}</div>;

  const act = (job) => job().then(onChange).catch((e) => setErr(e.message));
  const saveStock = () => {
    const n = Math.max(0, Math.round(Number(stock)));
    if (Number.isFinite(n) && n !== d.on_hand) act(() => api.setStock(shopId, productId, n));
  };

  return (
    <div className="card">
      <h2>{d.name}: 4-week forecast</h2>
      {d.forecast.length ? <Chart history={d.history} forecast={d.forecast} /> : <p>No forecast yet. Use "Update forecast" below.</p>}
      <p className="leg">Blue: actual daily sales. Orange: forecast. Shaded: likely range.</p>
      <div className="row">
        <label>On hand{" "}
          <input type="number" min="0" value={stock} onChange={(e) => setStock(e.target.value)}
                 onBlur={saveStock} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
        </label>
        <span>Lead time: {d.lead} days</span>
        {d.order != null && <strong>Suggested order: {d.order} units</strong>}
        {d.order > 0 && (d.order_id
          ? <button className="done" onClick={() => act(() => api.cancel(d.order_id))}>Approved (undo)</button>
          : <button onClick={() => act(() => api.approve(shopId, productId, d.order))}>Approve order</button>)}
      </div>
      {err && <p className="risk" role="alert">{err}</p>}
    </div>
  );
}
