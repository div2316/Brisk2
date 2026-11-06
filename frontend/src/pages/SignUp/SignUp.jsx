import BrandLogo from "../../components/BrandLogo";
import { motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { useAppData } from "../../context/AppDataContext";

function SignUp() {
  const navigate = useNavigate();
  const { signUp } = useAppData();

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const name = e.target.name.value.trim();
    const email = e.target.email.value.trim();
    const password = e.target.password.value;
    const confirmPassword = e.target.confirmPassword.value;
    const acceptTerms = e.target.terms.checked;

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters and include a letter and a number.");
      return;
    }

    if (!acceptTerms) {
      setError("You must accept the terms and conditions.");
      return;
    }

    setSubmitting(true);
    const result = await signUp({ name, email, password, acceptTerms });
    setSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }
    navigate("/signin", { state: { justRegistered: true, email } });
  };

  return (
    <main className="min-h-screen bg-[#0B0D10] text-white">

      {/* Background glow */}
      <div className="pointer-events-none fixed left-1/2 top-1/2 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-600/10 blur-[140px]" />

      {/* Navbar */}
      <header className="relative z-10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-10">

          {/* BRISK Logo */}
          <BrandLogo />

          <button
            onClick={() => navigate("/")}
            className="text-sm text-slate-400 transition hover:text-white"
          >
            ← Back
          </button>

        </div>
      </header>


      {/* Main */}
      <section className="relative z-10 flex items-center justify-center px-6 py-12">

        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="w-full max-w-md"
        >

          {/* Heading */}
          <div className="mb-8 text-center">

            <h1 className="text-4xl font-semibold tracking-tight">
              Create your account
            </h1>

            <p className="mt-3 text-sm leading-6 text-slate-400">
              Get started with BRISK2 preventive healthcare.
            </p>

          </div>


          {/* Card */}
          <div className="rounded-3xl border border-white/10 bg-[#11151C]/90 p-7 shadow-2xl backdrop-blur-xl sm:p-9">

            <form onSubmit={handleSubmit} className="space-y-5">

              {/* Full Name */}
              <div>

                <label
                  htmlFor="name"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Full name
                </label>

                <input
                  id="name"
                  name="name"
                  type="text"
                  placeholder="Enter your full name"
                  required
                  className="
                    w-full rounded-xl border border-slate-700
                    bg-[#0B0D10] px-4 py-3.5 text-sm text-white
                    outline-none placeholder:text-slate-600
                    transition focus:border-violet-400
                    focus:ring-2 focus:ring-violet-500/20
                  "
                />

              </div>


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
                  placeholder="you@example.com"
                  required
                  className="
                    w-full rounded-xl border border-slate-700
                    bg-[#0B0D10] px-4 py-3.5 text-sm text-white
                    outline-none placeholder:text-slate-600
                    transition focus:border-violet-400
                    focus:ring-2 focus:ring-violet-500/20
                  "
                />

              </div>


              {/* Password */}
              <div>

                <label
                  htmlFor="password"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Password
                </label>

                <div className="relative">

                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Create a password"
                    required
                    className="
                      w-full rounded-xl border border-slate-700
                      bg-[#0B0D10] px-4 py-3.5 pr-16
                      text-sm text-white outline-none
                      placeholder:text-slate-600 transition
                      focus:border-violet-400
                      focus:ring-2 focus:ring-violet-500/20
                    "
                  />

                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="
                      absolute right-4 top-1/2
                      -translate-y-1/2 text-xs
                      text-slate-500 hover:text-white
                    "
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>

                </div>

              </div>


              {/* Confirm Password */}
              <div>

                <label
                  htmlFor="confirmPassword"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Confirm password
                </label>

                <div className="relative">

                  <input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Confirm your password"
                    required
                    className="
                      w-full rounded-xl border border-slate-700
                      bg-[#0B0D10] px-4 py-3.5 pr-16
                      text-sm text-white outline-none
                      placeholder:text-slate-600 transition
                      focus:border-violet-400
                      focus:ring-2 focus:ring-violet-500/20
                    "
                  />

                  <button
                    type="button"
                    onClick={() =>
                      setShowConfirmPassword(!showConfirmPassword)
                    }
                    className="
                      absolute right-4 top-1/2
                      -translate-y-1/2 text-xs
                      text-slate-500 hover:text-white
                    "
                  >
                    {showConfirmPassword ? "Hide" : "Show"}
                  </button>

                </div>

              </div>


              {/* Terms */}
              <div className="flex items-start gap-3 pt-1">

                <input
                  id="terms"
                  name="terms"
                  type="checkbox"
                  required
                  className="mt-1 h-4 w-4 accent-violet-500"
                />

                <label
                  htmlFor="terms"
                  className="text-xs leading-5 text-slate-500"
                >
                  I agree to the BRISK2 terms of use and privacy
                  policy.
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
                  w-full rounded-xl bg-violet-500
                  px-5 py-3.5 text-sm font-semibold text-white
                  shadow-[0_0_30px_rgba(139,92,246,0.2)]
                  transition hover:bg-violet-400
                  hover:shadow-[0_0_40px_rgba(139,92,246,0.3)]
                  disabled:cursor-not-allowed disabled:opacity-60
                "
              >
                {submitting ? "Creating account…" : "Create Account"}
              </button>

            </form>


            {/* Existing account */}
            <div className="mt-7 text-center">

              <p className="text-sm text-slate-500">
                Already have an account?
              </p>

              <button
                type="button"
                onClick={() => navigate("/signin")}
                className="
                  mt-2 text-sm font-medium
                  text-violet-400 transition
                  hover:text-violet-300
                "
              >
                Sign in
              </button>

            </div>

          </div>

        </motion.div>

      </section>

    </main>
  );
}

export default SignUp;