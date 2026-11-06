import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { TrendChart } from "../../components/charts";
import { apiAssessment } from "../../lib/api";
import AppShell from "../../components/AppShell";
import { Card, CardTitle, FactorBars, EmptyState, Gauge } from "../../components/ui";
import { useAppData } from "../../context/AppDataContext";

export default function RiskAnalysis() {
  const { latest, history } = useAppData();
  const [params] = useSearchParams();
  const id = params.get("id");
  const [picked, setPicked] = useState(null);
  useEffect(() => {
    let live = true;
    if (id) apiAssessment(id).then((r) => live && setPicked(r)).catch(() => live && setPicked(null));
    return () => { live = false; };
  }, [id]);
  const shown = id && picked ? picked : latest;
  const p = shown?.prediction;
  const up = p ? p.all_factors.filter((f) => f.direction === "increases") : [];
  const down = p ? p.all_factors.filter((f) => f.direction === "decreases") : [];
  const max = p ? Math.max(1, ...p.all_factors.map((f) => Math.abs(f.contribution_pct_points))) : 1;

  return (
    <AppShell title="Risk analysis" subtitle={shown?.created_at ? `Assessment #${shown.id} · ${new Date(shown.created_at).toLocaleString()}` : "A closer look at every input and how it shapes your estimate."}>
      {!p ? <EmptyState /> : (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-3">
            <Card><CardTitle>Overall estimate</CardTitle><Gauge pct={p.risk_pct} stratum={p.stratum} size={200} />
              <p className="mt-4 text-center text-xs text-slate-500">The average in the training data is near {p.baseline_risk_pct}%.</p></Card>
            <Card className="lg:col-span-2">
              <CardTitle>Reading your result</CardTitle>
              <ul className="space-y-3 text-sm leading-6 text-slate-300">
                <li><span className="font-semibold text-white">Risk bands:</span> Low is under 20%, Moderate is 20–50%, High is 50% or above.</li>
                <li><span className="font-semibold text-white">Points:</span> each bar shows how many percentage points the estimate differs from the training-data average because of that input.</li>
                <li><span className="font-semibold text-rose-300">Raising risk:</span> {up.length ? up.slice(0, 3).map((f) => f.label).join(", ") : "none of your inputs stand out"}.</li>
                <li><span className="font-semibold text-emerald-300">Lowering risk:</span> {down.length ? down.slice(0, 3).map((f) => f.label).join(", ") : "none of your inputs stand out"}.</li>
              </ul>
            </Card>
          </div>

          <Card>
            <CardTitle hint="Every input, ordered by influence on this assessment.">All contributing factors</CardTitle>
            <div className="grid gap-x-12 gap-y-1 lg:grid-cols-2">
              <FactorBars factors={p.all_factors.slice(0, Math.ceil(p.all_factors.length / 2))} max={max} />
              <FactorBars factors={p.all_factors.slice(Math.ceil(p.all_factors.length / 2))} max={max} />
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card><CardTitle hint="Your entries compared with how they were scored.">Your entries</CardTitle>
              <table className="w-full text-sm"><tbody>
                {p.all_factors.map((f) => (
                  <tr key={f.factor} className="border-b border-white/5 last:border-0">
                    <td className="py-2 pr-3 text-slate-400">{f.label}</td>
                    <td className="py-2 pr-3 font-medium text-white">{f.value_text}</td>
                    <td className={`py-2 text-right text-xs font-semibold ${f.direction === "increases" ? "text-rose-300" : f.direction === "decreases" ? "text-emerald-300" : "text-slate-500"}`}>
                      {f.direction === "increases" ? "Raises" : f.direction === "decreases" ? "Lowers" : "Neutral"}</td>
                  </tr>))}
              </tbody></table>
            </Card>
            <Card><CardTitle hint="Your saved assessments, oldest to newest.">Risk over time</CardTitle><TrendChart items={history} />
              <Link to="/assessment" className="mt-4 inline-block text-sm font-semibold text-violet-300 hover:text-violet-200">Run a new assessment →</Link></Card>
          </div>
        </div>
      )}
    </AppShell>
  );
}
