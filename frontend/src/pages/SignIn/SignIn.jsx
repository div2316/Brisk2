import BrandLogo from "../../components/BrandLogo";
import { motion } from "framer-motion";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useAppData } from "../../context/AppDataContext";

function SignIn() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn } = useAppData();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const justRegistered = Boolean(location.state?.justRegistered);
  const passwordReset = Boolean(location.state?.passwordReset);
  const prefillEmail = location.state?.email || "";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const email = e.target.email.value.trim();
    const password = e.target.password.value;
    const result = await signIn({ email, password });

    setSubmitting(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    navigate("/dashboard");
  };
  return (
    <main className="min-h-screen bg-[#0B0D10] text-white">

      {/* Background glow */}
      <div className="pointer-events-none fixed left-1/2 top-1/2 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-600/10 blur-[140px]" />

      {/* Navbar */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="relative z-10"
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-10">

          {/* BRISK Logo */}
          <BrandLogo />

          {/* Back button */}
          <button
            onClick={() => window.history.back()}
            className="text-sm text-slate-400 transition hover:text-white"
          >
            ← Back
          </button>

        </div>
      </motion.header>


      {/* Main */}
      <section className="relative z-10 flex min-h-[calc(100vh-88px)] items-center justify-center px-6 py-12">

        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="w-full max-w-md"
        >

          {/* Heading */}
          <div className="mb-8 text-center">

            <h1 className="text-4xl font-semibold tracking-tight">
              Welcome back
            </h1>

            <p className="mt-3 text-sm leading-6 text-slate-400">
              Sign in to continue to your BRISK2 account.
            </p>

          </div>


          {/* Sign In Card */}
          <div className="rounded-3xl border border-white/10 bg-[#11151C]/90 p-7 shadow-2xl backdrop-blur-xl sm:p-9">

            {justRegistered && (
              <div className="mb-6 flex items-start gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-3.5 text-xs text-emerald-300">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
                <span>Account created — sign in with your new credentials to continue.</span>
              </div>
            )}

            {passwordReset && (
              <div className="mb-6 flex items-start gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-3.5 text-xs text-emerald-300">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
                <span>Password updated — sign in with your new password.</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">

              {/* Email */}
              <div>

                <label
                  htmlFor="email"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Email address
                </label>

                <input
                  id="email"
                  name="email"
                  type="email"
                  defaultValue={prefillEmail}
                  placeholder="you@example.com"
                  required
                  className="
                    w-full
                    rounded-xl
                    border
                    border-slate-700
                    bg-[#0B0D10]
                    px-4
                    py-3.5
                    text-sm
                    text-white
                    outline-none
                    placeholder:text-slate-600
                    transition
                    focus:border-violet-400
                    focus:ring-2
                    focus:ring-violet-500/20
                  "
                />

              </div>


              {/* Password */}
              <div>

                <div className="mb-2 flex items-center justify-between">

                  <label
                    htmlFor="password"
                    className="block text-sm font-medium text-slate-300"
                  >
                    Password
                  </label>

                  <button
                    type="button"
                    onClick={() => navigate("/forgot-password")}
                    className="text-xs text-violet-400 transition hover:text-violet-300"
                  >
                    Forgot password?
                  </button>

                </div>

                <div className="relative">

                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    required
                    className="
                      w-full
                      rounded-xl
                      border
                      border-slate-700
                      bg-[#0B0D10]
                      px-4
                      py-3.5
                      pr-16
                      text-sm
                      text-white
                      outline-none
                      placeholder:text-slate-600
                      transition
                      focus:border-violet-400
                      focus:ring-2
                      focus:ring-violet-500/20
                    "
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="
                      absolute
                      right-4
                      top-1/2
                      -translate-y-1/2
                      text-xs
                      text-slate-500
                      transition
                      hover:text-white
                    "
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>

                </div>

              </div>


              {/* Remember me */}
              <div className="flex items-center gap-3">

                <input
                  id="remember"
                  type="checkbox"
                  className="
                    h-4
                    w-4
                    rounded
                    border-slate-700
                    bg-[#0B0D10]
                    accent-violet-500
                  "
                />

                <label
                  htmlFor="remember"
                  className="text-sm text-slate-400"
                >
                  Remember me
                </label>

              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-xl border border-red-400/20 bg-red-400/[0.06] p-3.5 text-xs text-red-300">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={submitting}
                className="
                  w-full
                  rounded-xl
                  bg-violet-500
                  px-5
                  py-3.5
                  text-sm
                  font-semibold
                  text-white
                  shadow-[0_0_30px_rgba(139,92,246,0.2)]
                  transition
                  hover:bg-violet-400
                  hover:shadow-[0_0_40px_rgba(139,92,246,0.3)]
                  disabled:cursor-not-allowed disabled:opacity-60
                "
              >
                {submitting ? "Signing in…" : "Sign In"}
              </button>

            </form>


            {/* Divider */}
            <div className="my-7 flex items-center gap-4">

              <div className="h-px flex-1 bg-slate-800" />

              <span className="text-xs text-slate-600">
                OR
              </span>

              <div className="h-px flex-1 bg-slate-800" />

            </div>


            {/* Create account */}
            <div className="text-center">

              <p className="text-sm text-slate-500">
                Don't have an account?
              </p>

              <button
                type="button"
                onClick={() => navigate("/signup")}
                className="mt-2 text-sm font-medium text-violet-400 transition hover:text-violet-300"
              >
                Create an account
              </button>              

            </div>

          </div>


          {/* Footer note */}
          <p className="mt-6 text-center text-xs leading-5 text-slate-600">
            Your healthcare information should be handled securely.
          </p>

        </motion.div>

      </section>

    </main>
  );
}

export default SignIn;