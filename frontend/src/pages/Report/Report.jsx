import { useState } from "react";
import { Download, Loader2, Trash2 } from "lucide-react";
import AppShell from "../../components/AppShell";
import { Card, CardTitle, EmptyState, Gauge, FactorBars, bandOf, fmtDate, DISCLAIMER } from "../../components/ui";
import { useAppData } from "../../context/AppDataContext";
import { downloadReport, apiClearPatient } from "../../lib/api";

export default function Report() {
  const { latest, history, refresh } = useAppData();
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  const get = async (id) => {
    setError(""); setBusy(id);
    try { await downloadReport(id); } catch (e) { setError(e.message); } finally { setBusy(null); }
  };
  const wipe = async () => {
    if (!window.confirm("Delete all of your saved assessments? This cannot be undone.")) return;
    await apiClearPatient(); await refresh();
  };
  const p = latest?.prediction;

  return (
    <AppShell title="Report" subtitle="Download a PDF summary of any assessment."
      actions={p && <button onClick={() => get(latest.id)} disabled={busy === latest.id} className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60">
        {busy === latest.id ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Download latest report</button>}>
      {!p ? <EmptyState /> : (
        <div className="space-y-5">
          {error && <p className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</p>}
          <Card>
            <CardTitle hint={`Assessment #${latest.id} · ${fmtDate(latest.created_at)}`}>Report preview</CardTitle>
            <div className="grid gap-8 lg:grid-cols-[260px_1fr] lg:items-center">
              <Gauge pct={p.risk_pct} stratum={p.stratum} size={230} />
              <div><h3 className="mb-3 text-sm font-semibold text-slate-300">Top contributing factors</h3><FactorBars factors={p.top_contributing_factors} /></div>
            </div>
            <p className="mt-6 border-t border-white/10 pt-4 text-xs leading-5 text-slate-500">{DISCLAIMER}</p>
          </Card>

          <Card>
            <CardTitle>All assessments</CardTitle>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[460px] text-sm">
                <thead><tr className="border-b border-white/10 text-left text-xs uppercase tracking-wide text-slate-500"><th className="py-2 pr-3">#</th><th className="py-2 pr-3">Date</th><th className="py-2 pr-3">Risk</th><th className="py-2 pr-3">Band</th><th className="py-2 text-right">PDF</th></tr></thead>
                <tbody>{history.map((h) => (
                  <tr key={h.id} className="border-b border-white/5 last:border-0">
                    <td className="py-2.5 pr-3 text-slate-400">{h.id}</td>
                    <td className="py-2.5 pr-3 text-slate-300">{fmtDate(h.created_at)}</td>
                    <td className="py-2.5 pr-3 font-semibold text-white">{h.risk_pct}%</td>
                    <td className={`py-2.5 pr-3 ${bandOf(h.stratum).text}`}>{h.stratum}</td>
                    <td className="py-2.5 text-right"><button onClick={() => get(h.id)} disabled={busy === h.id} className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-semibold text-violet-200 hover:bg-white/5">
                      {busy === h.id ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} Download</button></td>
                  </tr>))}</tbody>
              </table>
            </div>
            <button onClick={wipe} className="mt-5 inline-flex items-center gap-2 text-xs font-semibold text-rose-300 hover:text-rose-200"><Trash2 size={14} /> Delete my saved assessments</button>
          </Card>
        </div>
      )}
    </AppShell>
  );
}
