import BrandLogo from "../../components/BrandLogo";
import { motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { apiForgotPassword } from "../../lib/api";

const inputCls =
  "w-full rounded-xl border border-slate-700 bg-[#0B0D10] px-4 py-3.5 text-sm text-white outline-none placeholder:text-slate-600 transition focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20";

function ForgotPassword() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [sentMessage, setSentMessage] = useState("");
  const [devLink, setDevLink] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const email = e.target.email.value.trim();
      const res = await apiForgotPassword(email);
      setSentMessage(res?.message || "If an account exists for that email, a password reset link has been sent.");
      // Only present when the backend runs with RESET_LINK_IN_RESPONSE=true (dev).
      if (res?.dev_reset_link) setDevLink(res.dev_reset_link);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#0B0D10] text-white">
      <div className="pointer-events-none fixed left-1/2 top-1/2 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-600/10 blur-[140px]" />

      <header className="relative z-10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-10">
          <BrandLogo />
          <button onClick={() => navigate("/signin")} className="text-sm text-slate-400 transition hover:text-white">
            ← Back to sign in
          </button>
        </div>
      </header>

      <section className="relative z-10 flex items-center justify-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="w-full max-w-md"
        >
          <div className="mb-8 text-center">
            <h1 className="text-4xl font-semibold tracking-tight">Forgot password?</h1>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              Enter your account email and we'll send you a link to reset your password.
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-[#11151C]/90 p-7 shadow-2xl backdrop-blur-xl sm:p-9">
            {sentMessage ? (
              <div className="space-y-4">
                <div className="flex items-start gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-3.5 text-sm text-emerald-300">
                  <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                  <span>{sentMessage} The link is valid for 30 minutes.</span>
                </div>
                {devLink && (
                  <p className="break-all rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-3.5 text-xs text-amber-300">
                    Dev mode — reset link:{" "}
                    <a className="underline" href={devLink}>
                      {devLink}
                    </a>
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => navigate("/signin")}
                  className="w-full rounded-xl bg-violet-500 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-violet-400"
                >
                  Back to sign in
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-300">
                    Email address
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    placeholder="you@example.com"
                    className={inputCls}
                  />
                </div>

                {error && (
                  <div className="flex items-start gap-2 rounded-xl border border-red-400/20 bg-red-400/[0.06] p-3.5 text-xs text-red-300">
                    <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-xl bg-violet-500 px-5 py-3.5 text-sm font-semibold text-white shadow-[0_0_30px_rgba(139,92,246,0.2)] transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Sending…" : "Send reset link"}
                </button>
              </form>
            )}
          </div>
        </motion.div>
      </section>
    </main>
  );
}

export default ForgotPassword;
