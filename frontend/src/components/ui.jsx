/* eslint-disable react-refresh/only-export-components */
import { Link } from "react-router-dom";
import { ClipboardList } from "lucide-react";

export const BAND = {
  Low: { text: "text-emerald-300", bg: "bg-emerald-500/15", ring: "ring-emerald-400/30", hex: "#34d399", note: "Estimated risk is below 20%." },
  Moderate: { text: "text-amber-300", bg: "bg-amber-500/15", ring: "ring-amber-400/30", hex: "#fbbf24", note: "Estimated risk is between 20% and 50%." },
  High: { text: "text-rose-300", bg: "bg-rose-500/15", ring: "ring-rose-400/30", hex: "#fb7185", note: "Estimated risk is 50% or higher." },
};
export const bandOf = (s) => BAND[s] || BAND.Moderate;

export function Card({ className = "", children }) {
  return <section className={`rounded-2xl border border-white/10 bg-[#12101f] p-5 sm:p-6 ${className}`}>{children}</section>;
}
export function CardTitle({ children, hint }) {
  return (
    <div className="mb-4">
      <h2 className="text-base font-semibold text-white">{children}</h2>
      {hint && <p className="mt-1 text-xs leading-5 text-slate-500">{hint}</p>}
    </div>
  );
}

export function Gauge({ pct, stratum, size = 220 }) {
  const b = bandOf(stratum);
  const r = 80, c = Math.PI * r; // semicircle length
  const v = Math.max(0, Math.min(100, pct));
  return (
    <div className="relative mx-auto" style={{ width: size, height: size * 0.62 }}>
      <svg viewBox="0 0 200 124" className="h-full w-full">
        <path d="M20 104 A80 80 0 0 1 180 104" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="16" strokeLinecap="round" />
        <path d="M20 104 A80 80 0 0 1 180 104" fill="none" stroke={b.hex} strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${(v / 100) * c} ${c}`} style={{ transition: "stroke-dasharray .8s ease" }} />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className="text-4xl font-extrabold leading-none tracking-tight text-white">{v.toFixed(1)}<span className="text-xl text-slate-400">%</span></div>
        <div className={`mt-2 inline-block rounded-full px-3 py-0.5 text-xs font-bold ring-1 ${b.bg} ${b.text} ${b.ring}`}>{stratum} risk</div>
      </div>
    </div>
  );
}

// Diverging bar: positive = raises risk (rose), negative = lowers (emerald)
export function FactorBars({ factors, max }) {
  const m = max || Math.max(1, ...factors.map((f) => Math.abs(f.contribution_pct_points)));
  return (
    <ul className="space-y-3.5">
      {factors.map((f) => {
        const up = f.contribution_pct_points >= 0;
        const w = Math.min(100, (Math.abs(f.contribution_pct_points) / m) * 100);
        return (
          <li key={f.factor}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate font-medium text-slate-200">{f.label} <span className="font-normal text-slate-500">· {f.value_text}</span></span>
              <span className={`shrink-0 font-semibold tabular-nums ${up ? "text-rose-300" : "text-emerald-300"}`}>
                {up ? "+" : "−"}{Math.abs(f.contribution_pct_points).toFixed(1)} pts
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-white/[0.06]">
              <div className={`h-full rounded-full ${up ? "bg-rose-400" : "bg-emerald-400"}`} style={{ width: `${Math.max(w, 2)}%`, transition: "width .6s ease" }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function EmptyState() {
  return (
    <Card className="py-14 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/15 text-violet-300"><ClipboardList size={26} /></div>
      <h2 className="text-lg font-semibold text-white">No assessment yet</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">Enter your health details to see your estimated cardiovascular risk and what contributes to it.</p>
      <Link to="/assessment" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-3 text-sm font-bold text-white">Start an assessment</Link>
    </Card>
  );
}

export const fmtDate = (iso) => {
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
};

export const DISCLAIMER = "This is a research prototype. The estimate reflects patterns in a training dataset and is not a medical diagnosis. Please consult a qualified healthcare professional.";
