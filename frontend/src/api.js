async function call(path, options) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch { /* keep status text */ }
    throw new Error(typeof msg === "string" ? msg : "Request failed");
  }
  return res.json();
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  shops: () => call("/shops"),
  dashboard: (shop) => call(`/shops/${shop}/dashboard`),
  product: (shop, product) => call(`/shops/${shop}/products/${product}`),
  setStock: (shop, product, on_hand) => call(`/shops/${shop}/products/${product}/stock`, json("PUT", { on_hand })),
  approve: (shop_id, product_id, qty) => call("/orders", json("POST", { shop_id, product_id, qty })),
  cancel: (orderId) => call(`/orders/${orderId}/cancel`, { method: "POST" }),
  importCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return call("/import", { method: "POST", body: form });
  },
  runForecast: () => call("/forecast/run", { method: "POST" }),
};
