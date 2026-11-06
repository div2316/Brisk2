import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, AlertTriangle } from "lucide-react";
import AppShell from "../../components/AppShell";
import { Card } from "../../components/ui";
import { apiSchema } from "../../lib/api";
import { useAppData } from "../../context/AppDataContext";

const input = "w-full rounded-xl border border-slate-700 bg-[#0B0D10] px-3.5 py-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20";

export default function Assessment() {
  const navigate = useNavigate();
  const { runAssessment, latest } = useAppData();
  const [fields, setFields] = useState(null);
  const [values, setValues] = useState(() =>
    latest?.patient ? Object.fromEntries(Object.entries(latest.patient).map(([k, v]) => [k, String(v)])) : {});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiSchema().then((s) => setFields(s.fields)).catch((e) => setError(e.message));
  }, []);

  const groups = useMemo(() => {
    const g = new Map();
    (fields || []).forEach((f) => { if (!g.has(f.group)) g.set(f.group, []); g.get(f.group).push(f); });
    return [...g.entries()];
  }, [fields]);

  const set = (n, v) => setValues((s) => ({ ...s, [n]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    const record = {};
    for (const f of fields) {
      const raw = values[f.name];
      if (raw === undefined || raw === "") { setError(`Please fill in “${f.label}”.`); return; }
      if (f.type === "number") {
        const n = Number(raw);
        if (!Number.isFinite(n)) { setError(`“${f.label}” must be a number.`); return; }
        record[f.name] = n;
      } else {
        const opt = f.options.find((o) => String(o.value) === raw);
        record[f.name] = opt ? opt.value : raw;
      }
    }
    setBusy(true);
    try {
      await runAssessment(record);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally { setBusy(false); }
  };

  return (
    <AppShell title="New assessment" subtitle="Enter your details to get an estimated cardiovascular risk and see what drives it.">
      {!fields && !error && <div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="animate-spin" size={16} /> Loading form…</div>}
      {fields && (
        <form onSubmit={submit} className="space-y-5">
          {groups.map(([name, list]) => (
            <Card key={name}>
              <h2 className="mb-4 text-base font-semibold text-white">{name}</h2>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {list.map((f) => (
                  <label key={f.name} className="block">
                    <span className="mb-1.5 block text-xs font-medium text-slate-400">{f.label}{f.unit ? ` (${f.unit})` : ""}</span>
                    {f.type === "select" ? (
                      <select className={input} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)}>
                        <option value="" disabled>Select…</option>
                        {f.options.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}
                      </select>
                    ) : (
                      <input className={input} type="number" step="any" inputMode="decimal"
                        placeholder={f.baseline != null ? `e.g. ${Math.round(f.baseline)}` : ""}
                        value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} />
                    )}
                  </label>
                ))}
              </div>
            </Card>
          ))}
          {error && <div className="flex items-start gap-2 rounded-xl border border-rose-400/30 bg-rose-500/10 p-3.5 text-sm text-rose-200"><AlertTriangle size={16} className="mt-0.5 shrink-0" />{error}</div>}
          <button disabled={busy} className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 py-3.5 text-sm font-bold text-white disabled:opacity-60">
            {busy && <Loader2 className="animate-spin" size={16} />} {busy ? "Calculating…" : "Calculate my risk"}
          </button>
        </form>
      )}
      {!fields && error && <p className="text-sm text-rose-300">{error}</p>}
    </AppShell>
  );
}
