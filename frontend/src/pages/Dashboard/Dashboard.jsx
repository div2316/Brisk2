import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, AlertTriangle, CheckCircle2, ShieldCheck, Info, TrendingUp, TrendingDown, CircleSlash } from "lucide-react";
import AppShell from "../../components/AppShell";
import { TrendChart } from "../../components/charts";
import { Card, CardTitle, Gauge, FactorBars, EmptyState, bandOf, fmtDate, DISCLAIMER } from "../../components/ui";
import { useAppData } from "../../context/AppDataContext";

const SEV = {
  none: { t: "Normal", c: "text-emerald-300", b: "bg-emerald-500/15" },
  moderate: { t: "Warning", c: "text-amber-300", b: "bg-amber-500/15" },
  major: { t: "Significant shift", c: "text-rose-300", b: "bg-rose-500/15" },
};
const fmt = (v, d = 3) => (v == null ? "—" : Number(v).toFixed(d));

function Stat({ label, value, sub, tone = "text-white" }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#12101f] p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1.5 text-2xl font-bold tracking-tight ${tone}`}>{value}</p>
      {sub && <p className="mt-0.5 truncate text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function Row({ ok, children }) {
  return (
    <li className="flex items-start gap-2.5 text-sm">
      {ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-300" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-300" />}
      <span className={ok ? "text-slate-300" : "text-amber-100"}>{children}</span>
    </li>
  );
}

function ReliabilityCard({ rel, latest }) {
  const rc = rel?.record_checks;
  const shift = rel?.shift;
  const issues = rc ? [...rc.out_of_range, ...rc.unseen_values, ...rc.missing_or_invalid] : [];
  const rows = (shift?.features || []).filter((f) => f.psi != null || f.p_value != null);
  return (
    <Card>
      <CardTitle hint="A model can still produce a number when new data looks different from the data it learned from. These checks help show when that happens.">Reliability monitoring</CardTitle>
      {!rc ? <p className="text-sm text-slate-500">Reliability information is unavailable.</p> : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <div className={`mb-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold ${rc.passed ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
              <ShieldCheck size={14} /> {rc.passed ? "Latest inputs passed all checks" : "Latest inputs need review"}
            </div>
            <ul className="space-y-2.5">
              <Row ok={rc.out_of_range.length === 0}>Within the range seen in training data{rc.out_of_range.length ? `: ${rc.out_of_range.join("; ")}` : ""}</Row>
              <Row ok={rc.unseen_values.length === 0}>No unseen categories or values{rc.unseen_values.length ? `: ${rc.unseen_values.join("; ")}` : ""}</Row>
              <Row ok={rc.missing_or_invalid.length === 0}>No missing or unreadable inputs{rc.missing_or_invalid.length ? `: ${rc.missing_or_invalid.join("; ")}` : ""}</Row>
            </ul>
            <p className="mt-4 text-xs leading-5 text-slate-500">{rc.features_checked} inputs checked against the training reference{issues.length ? "" : "; none were flagged"}.</p>
          </div>
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">Distribution shift (PSI and KS) <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-400">across your saved assessments</span></h3>
            {shift?.status === "INSUFFICIENT_DATA" || !rows.length ? (
              <div className="flex gap-3 rounded-xl border border-dashed border-white/10 p-4 text-sm text-slate-400">
                <CircleSlash size={18} className="mt-0.5 shrink-0 text-slate-500" />
                <p>Not available yet. Shift tests need at least {shift?.min_batch ?? 300} saved assessments to be meaningful; you have {shift?.n_rows ?? 0}. Individual input checks on the left still apply.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <p className="mb-2 text-xs text-slate-500">Overall: <span className="font-semibold text-white">{shift.status.replaceAll("_", " ").toLowerCase()}</span> · {shift.n_rows} assessments</p>
                <table className="w-full min-w-[420px] text-xs"><thead><tr className="border-b border-white/10 text-left text-slate-500"><th className="py-1.5">Input</th><th>PSI</th><th>KS / test p</th><th>Status</th></tr></thead>
                  <tbody>{rows.map((f) => { const s = SEV[f.severity] || SEV.none; return (
                    <tr key={f.feature} className="border-b border-white/5"><td className="py-1.5 text-slate-300">{f.label}</td><td className="tabular-nums text-slate-300">{fmt(f.psi)}</td><td className="tabular-nums text-slate-300">{fmt(f.p_value, 4)}</td>
                      <td><span className={`rounded-full px-2 py-0.5 font-semibold ${s.b} ${s.c}`}>{s.t}</span></td></tr>); })}</tbody></table>
              </div>
            )}
          </div>
        </div>
      )}
      <div className="mt-5 grid gap-3 border-t border-white/10 pt-4 text-xs leading-5 text-slate-500 sm:grid-cols-2">
        <p><span className="font-semibold text-slate-300">PSI</span> (Population Stability Index) measures how much an input’s spread differs from the training data. Under 0.2 is usually stable; 0.5 or more is a large change.</p>
        <p><span className="font-semibold text-slate-300">KS test</span> compares the shape of a numeric input against the training data. A very small p-value suggests the two differ.</p>
      </div>
      {!latest && null}
    </Card>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, latest, history, reliability } = useAppData();
  const p = latest?.prediction;
  const first = (user?.name || "").split(" ")[0];
  const b = p && bandOf(p.stratum);
  const model = reliability?.model;
  const rc = reliability?.record_checks;
  const up = p ? p.all_factors.filter((f) => f.direction === "increases") : [];
  const down = p ? p.all_factors.filter((f) => f.direction === "decreases") : [];
  const relLabel = !rc ? "Unavailable" : rc.passed ? "Passed" : "Review inputs";

  return (
    <AppShell
      title={first ? `Welcome back, ${first}` : "Dashboard"}
      subtitle={p ? `Latest assessment · ${fmtDate(latest.created_at)}` : "Your cardiovascular risk overview"}
      actions={<Link to="/assessment" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-violet-900/30 transition hover:-translate-y-0.5">New assessment <ArrowRight size={16} /></Link>}
    >
      {!p ? <EmptyState /> : (
        <div className="space-y-5">
          {/* 1. Overview */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Current estimate" value={`${p.risk_pct}%`} sub="Latest assessment" tone={b.text} />
            <Stat label="Classification" value={`${p.stratum} risk`} sub={b.note} tone={b.text} />
            <Stat label="Assessments" value={history.length} sub="Completed in total" />
            <Stat label="Reliability" value={relLabel} sub="Latest input checks" tone={rc?.passed ? "text-emerald-300" : "text-amber-300"} />
          </div>

          {/* 2. Summary + 3. Explanation */}
          <div className="grid gap-5 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
            <Card>
              <CardTitle hint="Estimated probability of cardiovascular disease from the details you entered.">Your CVD risk</CardTitle>
              <div className="py-2"><Gauge pct={p.risk_pct} stratum={p.stratum} /></div>
              <p className="mt-4 text-center text-sm leading-6 text-slate-300">Among people with inputs like yours, the model estimates about <span className="font-semibold text-white">{p.risk_pct} in 100</span> have cardiovascular disease.</p>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center text-[11px]">
                <div className="rounded-lg bg-emerald-500/10 p-2 text-emerald-300"><b>Low</b><br />under 20%</div>
                <div className="rounded-lg bg-amber-500/10 p-2 text-amber-300"><b>Moderate</b><br />20–50%</div>
                <div className="rounded-lg bg-rose-500/10 p-2 text-rose-300"><b>High</b><br />50% or more</div>
              </div>
              <dl className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Average in training data</dt><dd className="font-semibold text-white">{p.baseline_risk_pct}%</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Difference from average</dt><dd className={`font-semibold ${p.risk_pct >= p.baseline_risk_pct ? "text-rose-300" : "text-emerald-300"}`}>{p.risk_pct >= p.baseline_risk_pct ? "+" : "−"}{Math.abs(p.risk_pct - p.baseline_risk_pct).toFixed(1)} pts</dd></div>
                {model && <div className="flex justify-between gap-3"><dt className="text-slate-500">Model version</dt><dd className="font-semibold text-white">{model.version}</dd></div>}
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Assessment date</dt><dd className="font-semibold text-white">{fmtDate(latest.created_at)}</dd></div>
              </dl>
              <p className="mt-4 flex gap-2 text-[11px] leading-5 text-slate-500"><Info size={14} className="mt-0.5 shrink-0" />This is a model estimate learned from a research dataset, not a clinically validated risk score.</p>
            </Card>

            <Card>
              <CardTitle>Understanding your CVD risk result</CardTitle>
              <div className="grid gap-x-8 gap-y-5 text-sm leading-6 text-slate-300 md:grid-cols-2">
                <div><h3 className="font-semibold text-white">What the percentage means</h3><p className="mt-1 text-slate-400">It is the model’s estimated probability that a person with these inputs has cardiovascular disease, based on patterns in its training data. It is not a prediction that something will happen to you.</p></div>
                <div><h3 className="font-semibold text-white">Why “{p.stratum}”</h3><p className="mt-1 text-slate-400">{b.note} The model estimated {p.risk_pct}%, which falls in the {p.stratum.toLowerCase()} band{model ? `; its internal decision point is ${model.decision_threshold_pct}%` : ""}.</p></div>
                <div><h3 className="flex items-center gap-1.5 font-semibold text-white"><TrendingUp size={15} className="text-rose-300" />What raised the estimate</h3><p className="mt-1 text-slate-400">{up.length ? up.slice(0, 3).map((f) => `${f.label} (${f.value_text}, +${f.contribution_pct_points.toFixed(1)} pts)`).join("; ") : "None of your inputs stood out as raising it."}</p></div>
                <div><h3 className="flex items-center gap-1.5 font-semibold text-white"><TrendingDown size={15} className="text-emerald-300" />What lowered the estimate</h3><p className="mt-1 text-slate-400">{down.length ? down.slice(0, 3).map((f) => `${f.label} (${f.value_text}, −${Math.abs(f.contribution_pct_points).toFixed(1)} pts)`).join("; ") : "None of your inputs stood out as lowering it."}</p></div>
                <div><h3 className="font-semibold text-white">Reliability</h3><p className="mt-1 text-slate-400">{rc?.passed ? "All of your inputs were within what the model saw during training, so the estimate is being used inside its comfort zone." : rc ? "Some inputs were unusual compared with the training data, so treat this estimate with extra caution." : "Reliability checks are unavailable right now."}</p></div>
                <div><h3 className="font-semibold text-white">Limitations</h3><p className="mt-1 text-slate-400">The model only sees the inputs listed here, cannot examine you, and may not represent every population. “Points” show how much each input moves the estimate compared with the average person in the training data; they describe the model, not a cause. This is not a diagnosis or treatment advice.</p></div>
              </div>
            </Card>
          </div>

          {/* 4. Contributions + 5. Trend */}
          <div className="grid gap-5 xl:grid-cols-2">
            <Card>
              <CardTitle hint="Red raises your estimate, green lowers it. Values are your entries.">What contributes to your prediction</CardTitle>
              <FactorBars factors={p.all_factors.slice(0, 8)} />
              <Link to="/risk-analysis" className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-violet-300 hover:text-violet-200">Full analysis <ArrowRight size={14} /></Link>
            </Card>
            <Card>
              <CardTitle hint="Your saved assessments over time. Hover a point for details.">Risk trend</CardTitle>
              <TrendChart items={history} />
              {history.length >= 2 && (() => { const d = history[0].risk_pct - history[1].risk_pct; return (
                <p className="mt-3 text-xs text-slate-400">Change since your previous assessment: <span className={`font-semibold ${d > 0 ? "text-rose-300" : d < 0 ? "text-emerald-300" : "text-slate-300"}`}>{d > 0 ? "+" : d < 0 ? "−" : ""}{Math.abs(d).toFixed(1)} pts</span></p>); })()}
            </Card>
          </div>

          {/* 6. Reliability */}
          <ReliabilityCard rel={reliability} latest={latest} />

          {/* 7. Recent assessments */}
          <Card>
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-white">Recent assessments</h2>
              <Link to="/report" className="inline-flex items-center gap-1 text-sm font-semibold text-violet-300 hover:text-violet-200">View all &amp; reports <ArrowRight size={14} /></Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead><tr className="border-b border-white/10 text-left text-xs uppercase tracking-wide text-slate-500"><th className="py-2 pr-3">Date</th><th className="pr-3">Probability</th><th className="pr-3">Class</th><th className="pr-3">Reliability</th><th className="text-right">Details</th></tr></thead>
                <tbody>{history.slice(0, 5).map((h) => (
                  <tr key={h.id} className="border-b border-white/5 last:border-0">
                    <td className="py-2.5 pr-3 text-slate-300">{fmtDate(h.created_at)}</td>
                    <td className="pr-3 font-semibold text-white">{h.risk_pct}%</td>
                    <td className={`pr-3 ${bandOf(h.stratum).text}`}>{h.stratum}</td>
                    <td className="pr-3 text-xs">{h.needs_review == null ? <span className="text-slate-500">Unavailable</span> : h.needs_review ? <span className="text-amber-300">Review inputs</span> : <span className="text-emerald-300">Passed</span>}</td>
                    <td className="text-right"><button onClick={() => navigate(`/risk-analysis?id=${h.id}`)} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-violet-200 hover:bg-white/5">View details</button></td>
                  </tr>))}</tbody>
              </table>
            </div>
          </Card>

          {/* 8. Guidance */}
          <Card className="bg-violet-500/[0.04]">
            <h2 className="text-base font-semibold text-white">Helpful guidance</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">Use this result as a starting point for a conversation with a qualified healthcare professional, especially if blood pressure or other values were measured a while ago. Re-run an assessment when your measurements change to see the trend.</p>
            <p className="mt-3 text-xs leading-5 text-slate-500">{DISCLAIMER}</p>
          </Card>
        </div>
      )}
    </AppShell>
  );
}
