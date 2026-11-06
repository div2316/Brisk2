import { useState } from "react";
import { bandOf, fmtDate } from "./ui";

// Line chart of real saved assessments (oldest -> newest) with hover tooltips and band guides.
export function TrendChart({ items }) {
  const [hover, setHover] = useState(null);
  const pts = [...items].reverse().slice(-20);
  if (pts.length < 2) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-white/10 px-4 text-center text-sm text-slate-500">
        {pts.length === 0 ? "No assessments yet." : "Complete one more assessment to see how your risk changes over time."}
      </div>
    );
  }
  const W = 640, H = 300, L = 44, R = 14, T = 14, B = 38;
  const x = (i) => L + (i * (W - L - R)) / (pts.length - 1);
  const y = (v) => T + (1 - v / 100) * (H - T - B);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.risk_pct).toFixed(1)}`).join(" ");
  const h = hover != null ? pts[hover] : null;
  const prev = hover > 0 ? pts[hover - 1] : null;
  const labelEvery = Math.ceil(pts.length / 6);
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Predicted risk over time">
        <rect x={L} y={y(100)} width={W - L - R} height={y(50) - y(100)} fill="rgba(251,113,133,.06)" />
        <rect x={L} y={y(50)} width={W - L - R} height={y(20) - y(50)} fill="rgba(251,191,36,.05)" />
        <rect x={L} y={y(20)} width={W - L - R} height={y(0) - y(20)} fill="rgba(52,211,153,.05)" />
        {[0, 20, 50, 100].map((t) => (
          <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="rgba(255,255,255,.1)" strokeDasharray={t === 0 || t === 100 ? "" : "4 4"} />
            <text x={L - 6} y={y(t) + 3} textAnchor="end" fontSize="13" fill="#64748b">{t}%</text></g>
        ))}
        <path d={path} fill="none" stroke="#a78bfa" strokeWidth="2.5" strokeLinejoin="round" />
        {pts.map((p, i) => (
          <g key={p.id}>
            {i % labelEvery === 0 && <text x={x(i)} y={H - 14} textAnchor="middle" fontSize="13" fill="#64748b">{new Date(p.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</text>}
            <circle cx={x(i)} cy={y(p.risk_pct)} r={hover === i ? 7 : 5} fill={bandOf(p.stratum).hex} stroke="#12101f" strokeWidth="2" />
            <circle cx={x(i)} cy={y(p.risk_pct)} r="16" fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onClick={() => setHover(i)} />
          </g>
        ))}
      </svg>
      {h && (
        <div className="pointer-events-none absolute z-10 rounded-xl border border-violet-300/20 bg-[#1a1530] px-3 py-2 text-xs shadow-xl"
          style={{ left: `${(x(hover) / W) * 100}%`, top: `${(y(h.risk_pct) / H) * 100}%`, transform: "translate(-50%, -125%)" }}>
          <p className="font-semibold text-white">{h.risk_pct}% · {h.stratum}</p>
          <p className="text-slate-400">{fmtDate(h.created_at)}</p>
          {prev && <p className={h.risk_pct >= prev.risk_pct ? "text-rose-300" : "text-emerald-300"}>
            {h.risk_pct >= prev.risk_pct ? "▲" : "▼"} {Math.abs(h.risk_pct - prev.risk_pct).toFixed(1)} pts vs previous</p>}
        </div>
      )}
    </div>
  );
}
