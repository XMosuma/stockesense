const Z = 1.28;
const W = 900, H = 260;

export default function Chart({ history, forecast }) {
  const nh = history.length, n = nh + forecast.length;
  const top = Math.max(1, ...history.map((d) => d.units), ...forecast.map((d) => d.yhat + Z * d.sd)) * 1.05;
  const x = (i) => 30 + (i * (W - 40)) / (n - 1);
  const y = (v) => H - 20 - (v / top) * (H - 40);
  const hist = history.map((d, i) => `${x(i)},${y(d.units)}`).join(" ");
  const line = [`${x(nh - 1)},${y(history[nh - 1].units)}`, ...forecast.map((d, i) => `${x(nh + i)},${y(d.yhat)}`)].join(" ");
  const upper = forecast.map((d, i) => `${x(nh + i)},${y(d.yhat + Z * d.sd)}`);
  const lower = forecast.map((d, i) => `${x(nh + i)},${y(Math.max(0, d.yhat - Z * d.sd))}`).reverse();
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Actual daily sales and forecast with likely range">
      {forecast.length > 0 && <polygon points={[...upper, ...lower].join(" ")} fill="var(--band)" />}
      <polyline points={hist} fill="none" stroke="var(--blue)" strokeWidth="2.5" />
      {forecast.length > 0 && (
        <polyline points={line} fill="none" stroke="var(--acc)" strokeWidth="2.5" strokeDasharray="7 5" />
      )}
      <line x1={x(nh - 0.5)} x2={x(nh - 0.5)} y1="10" y2={H - 20} stroke="var(--line)" />
    </svg>
  );
}
