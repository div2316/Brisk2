import BrandLogo from "../../components/BrandLogo";
import { motion } from "framer-motion";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { apiResetPassword } from "../../lib/api";

const inputCls =
  "w-full rounded-xl border border-slate-700 bg-[#0B0D10] px-4 py-3.5 pr-16 text-sm text-white outline-none placeholder:text-slate-600 transition focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20";

function ResetPassword() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";

  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const password = e.target.password.value;
    const confirmPassword = e.target.confirmPassword.value;

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters and include a letter and a number.");
      return;
    }

    setSubmitting(true);
    try {
      await apiResetPassword(token, password);
      navigate("/signin", { state: { passwordReset: true } });
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
            <h1 className="text-4xl font-semibold tracking-tight">Set a new password</h1>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              Choose a new password. You'll be signed out everywhere else.
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-[#11151C]/90 p-7 shadow-2xl backdrop-blur-xl sm:p-9">
            {!token ? (
              <div className="space-y-4">
                <div className="flex items-start gap-2 rounded-xl border border-red-400/20 bg-red-400/[0.06] p-3.5 text-sm text-red-300">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>This reset link is missing its token. Please request a new one.</span>
                </div>
                <button
                  type="button"
                  onClick={() => navigate("/forgot-password")}
                  className="w-full rounded-xl bg-violet-500 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-violet-400"
                >
                  Request a new link
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-300">
                    New password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      required
                      placeholder="At least 8 characters, a letter and a number"
                      className={inputCls}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-slate-500 hover:text-white"
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="mb-2 block text-sm font-medium text-slate-300">
                    Confirm new password
                  </label>
                  <input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="Re-enter your new password"
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
                  {submitting ? "Updating…" : "Update password"}
                </button>

                <button
                  type="button"
                  onClick={() => navigate("/forgot-password")}
                  className="w-full text-center text-sm text-violet-400 transition hover:text-violet-300"
                >
                  Request a new link
                </button>
              </form>
            )}
          </div>
        </motion.div>
      </section>
    </main>
  );
}

export default ResetPassword;
