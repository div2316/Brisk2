import { motion } from "framer-motion";
import {
  Activity, ArrowDown, ArrowRight, BarChart3, BrainCircuit,
  ClipboardList, Database, Dna, Layers3, ShieldCheck,
  Users, Workflow, Gauge, Code2, Server, Container,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

const features = [
  { icon: Activity, title: "CVD Risk Percentage", text: "Enter your health details and get an estimated percentage risk of cardiovascular disease with a clear Low, Moderate or High band." },
  { icon: BarChart3, title: "Explainable Results", text: "See which inputs raise or lower your estimate, in plain language and in percentage points." },
  { icon: Layers3, title: "Saved History", text: "Every assessment is stored securely in your account so you can follow changes over time." },
  { icon: ShieldCheck, title: "Downloadable Report", text: "Download a PDF summary of any assessment to keep or share with your doctor." },
];

const workflow = [
  { icon: Users, title: "Patient input", text: "Enter the health and demographic information requested by the assessment." },
  { icon: Workflow, title: "Data validation", text: "Validate the supplied values and prepare the exact feature set expected by the selected model." },
  { icon: BrainCircuit, title: "ML inference", text: "Run the saved model pipeline to obtain its positive-class prediction probability." },
  { icon: ShieldCheck, title: "Explanation", text: "See which inputs contributed most to the estimate." },
  { icon: BarChart3, title: "Results and history", text: "View the prediction result and retain assessment history for later review." },
];

const technologies = [
  { icon: Code2, name: "React", detail: "Frontend" },
  { icon: Server, name: "FastAPI", detail: "Backend API" },
  { icon: BrainCircuit, name: "Python", detail: "ML services" },
  { icon: Gauge, name: "scikit-learn", detail: "Prediction" },
  { icon: Database, name: "PostgreSQL", detail: "Application data" },
  { icon: Container, name: "Docker", detail: "Deployment" },
];

function BrandMark({ compact = false }) {
  return (
    <div className={`flex items-center ${compact ? "gap-2" : "gap-3"}`}>
      <img src="/brisk2-logo.jpg" alt="" className={`rounded-xl ${compact ? "h-9 w-9" : "h-14 w-14"}`} />
      <span className={`${compact ? "text-xl" : "text-3xl"} font-bold tracking-tight text-white`}>
        BRISK<span className="text-violet-400">2</span>
      </span>
    </div>
  );
}

function SectionHeading({ eyebrow, title, accent, description }) {
  return (
    <div className="max-w-3xl">
      <p className="text-xs font-bold uppercase tracking-[0.24em] text-violet-300">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
        {title} <span className="bg-gradient-to-r from-violet-300 to-fuchsia-400 bg-clip-text text-transparent">{accent}</span>
      </h2>
      {description && <p className="mt-4 max-w-2xl text-base leading-7 text-slate-400">{description}</p>}
      <div className="mt-5 h-1 w-16 rounded-full bg-gradient-to-r from-violet-400 to-fuchsia-500" />
    </div>
  );
}

function Welcome() {
  const navigate = useNavigate();
  const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

  return (
    <main className="min-h-screen w-full overflow-x-hidden bg-[#090914] text-slate-100 selection:bg-violet-500/30">
      {/* Navigation */}
      <header className="fixed inset-x-0 top-0 z-50 border-b border-white/10 bg-[#0b0a18]/85 shadow-[0_8px_40px_rgba(0,0,0,0.25)] backdrop-blur-xl">
        <div className="mx-auto flex max-w-[110rem] items-center justify-between px-5 py-3 sm:px-8 lg:px-12">
          <a href="#home" aria-label="BRISK2 home"><BrandMark compact /></a>
          <nav className="hidden items-center gap-7 lg:flex">
            {[ ["Home", "home"], ["About", "about"], ["Methodology", "methodology"], ["Features", "features"] ].map(([label, id]) => (
              <button key={id} onClick={() => scrollTo(id)} className="text-sm font-medium text-slate-300 transition hover:text-violet-300">{label}</button>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/signin")} className="hidden px-3 py-2 text-sm font-medium text-slate-300 transition hover:text-white sm:inline-flex">Sign in</button>
            <button onClick={() => navigate("/signup")} className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-900/30 transition hover:-translate-y-0.5 hover:brightness-110">Get started <ArrowRight size={16} /></button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section id="home" className="relative isolate flex min-h-[min(760px,calc(100svh-72px))] items-center overflow-hidden pb-20 pt-32 lg:min-h-[min(820px,calc(100svh-72px))] lg:pt-28">
        <div className="pointer-events-none absolute -left-48 top-24 h-[520px] w-[520px] rounded-full bg-violet-700/20 blur-[130px]" />
        <div className="pointer-events-none absolute -right-40 top-20 h-[600px] w-[600px] rounded-full bg-fuchsia-700/10 blur-[150px]" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-violet-500/30 to-transparent" />
        <div className="relative mx-auto grid w-full max-w-[110rem] items-center gap-12 px-5 sm:px-8 lg:grid-cols-[1.1fr_0.9fr] lg:px-20 2xl:px-24">
          <div className="relative z-10">
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-400/25 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 shadow-[0_0_30px_rgba(139,92,246,0.12)]">
              <Activity size={15} /> CVD Risk Prediction & Reliability Platform
            </motion.div>
            <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.1 }} className="text-5xl font-extrabold leading-[1.02] tracking-[-0.045em] text-white sm:text-6xl lg:text-7xl">
              BRISK<span className="bg-gradient-to-r from-violet-300 via-fuchsia-400 to-purple-500 bg-clip-text text-transparent">2</span>
              <span className="mt-3 block text-3xl font-bold leading-tight tracking-tight sm:text-4xl lg:text-[2.8rem]">Cardiovascular Disease<br />Risk Prediction <span className="text-violet-400">& Reliability Analysis</span></span>
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.25 }} className="mt-7 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
              An intelligent machine-learning research system designed to estimate cardiovascular risk, present model outputs, and monitor reliability as incoming data changes.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.4 }} className="mt-9 flex flex-wrap gap-4">
              <button onClick={() => navigate("/signup")} className="group inline-flex items-center gap-3 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-7 py-4 text-sm font-bold text-white shadow-[0_12px_40px_rgba(124,58,237,0.3)] transition hover:-translate-y-1 hover:shadow-[0_16px_50px_rgba(124,58,237,0.4)]">Start an assessment <ArrowRight size={18} className="transition group-hover:translate-x-1" /></button>
              <button onClick={() => scrollTo("about")} className="inline-flex items-center gap-2 rounded-xl border border-violet-300/30 bg-white/[0.03] px-7 py-4 text-sm font-semibold text-white transition hover:border-violet-300/70 hover:bg-violet-500/10">Explore BRISK2 <ArrowDown size={16} /></button>
            </motion.div>
            <p className="mt-6 text-xs leading-5 text-slate-500">Research prototype · Not intended for clinical diagnosis or treatment decisions</p>
          </div>

          <motion.div initial={{ opacity: 0, scale: 0.88, x: 20 }} animate={{ opacity: 1, scale: 1, x: 0 }} transition={{ duration: 0.9, delay: 0.25 }} className="relative mx-auto flex w-full max-w-[540px] items-center justify-center py-8">
            <div className="absolute h-[390px] w-[390px] rounded-full bg-violet-600/20 blur-[95px]" />
            <div className="absolute bottom-10 h-24 w-[82%] rounded-[50%] border border-violet-400/30 bg-violet-600/10 shadow-[0_0_55px_rgba(139,92,246,0.35)]" />
            <div className="absolute bottom-6 h-20 w-[94%] rounded-[50%] border border-violet-500/20" />
            <div className="relative z-10 rounded-[3rem] border border-violet-300/15 bg-gradient-to-br from-violet-500/[0.10] to-fuchsia-500/[0.04] p-8 shadow-[0_0_100px_rgba(124,58,237,0.16)] backdrop-blur-sm sm:p-12">
              <img src="/brisk2-mark.svg" alt="BRISK2 heart ECG symbol" className="relative z-10 w-[260px] drop-shadow-[0_0_35px_rgba(167,139,250,0.65)] sm:w-[330px]" />
              <div className="absolute -right-3 top-8 h-3 w-3 rounded-full bg-violet-200 shadow-[0_0_20px_5px_rgba(196,181,253,0.7)]" />
              <div className="absolute -right-10 top-16 h-2 w-2 rounded-full bg-fuchsia-300 shadow-[0_0_15px_4px_rgba(232,121,249,0.6)]" />
            </div>
            <div className="absolute -bottom-1 left-1/2 z-20 -translate-x-1/2 rounded-full border border-violet-300/20 bg-[#17112a]/90 px-5 py-2 text-xs font-semibold tracking-wide text-violet-200 shadow-lg">Machine Learning · Reliability · Monitoring</div>
          </motion.div>
        </div>
      </section>

      {/* Feature cards */}
      <section id="features" className="relative mx-auto -mt-8 max-w-[110rem] px-5 pb-20 sm:px-8 lg:px-20 2xl:px-24">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {features.map(({ icon: Icon, title, text }, i) => (
            <motion.article key={title} initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} whileHover={{ y: -5 }} className="rounded-2xl border border-violet-300/15 bg-gradient-to-br from-[#1a1530] to-[#11101e] p-6 shadow-[0_12px_35px_rgba(0,0,0,0.18)]">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/15 text-violet-300 shadow-[0_0_25px_rgba(139,92,246,0.15)]"><Icon size={24} /></div>
              <h3 className="text-lg font-bold text-white">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{text}</p>
            </motion.article>
          ))}
        </div>
      </section>

      {/* About */}
      <section id="about" className="border-y border-white/[0.06] bg-[#0e0d1b] py-24">
        <div className="mx-auto grid max-w-[110rem] gap-12 px-5 sm:px-8 lg:grid-cols-[1.1fr_1fr] lg:items-center lg:px-20 2xl:px-24">
          <div>
            <SectionHeading eyebrow="About BRISK2" title="Turning health data into" accent="understandable insights." description="BRISK2 is a research-based cardiovascular risk prediction platform that combines a trained machine-learning model with a web application for assessment, explanation, history and reports." />
            <p className="mt-6 max-w-2xl text-sm leading-7 text-slate-400">The system is intended to make the model workflow accessible: users provide supported health inputs, the backend validates them, the model estimates your risk, and the application explains the result and records it for review.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { icon: ClipboardList, title: "Problem", text: "Cardiovascular risk factors need structured assessment and careful interpretation." },
              { icon: Dna, title: "Objective", text: "Build an integrated prediction system with clear explanations." },
              { icon: Users, title: "Intended value", text: "Make model outputs and assessment history easier to access and review." },
            ].map(({ icon: Icon, title, text }) => <div key={title} className="rounded-2xl border border-white/10 bg-white/[0.025] p-5"><Icon className="mb-5 text-violet-300" size={28} /><h3 className="font-bold text-white">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{text}</p></div>)}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section id="methodology" className="py-24">
        <div className="mx-auto max-w-[110rem] px-5 sm:px-8 lg:px-20 2xl:px-24">
          <SectionHeading eyebrow="System workflow" title="How" accent="BRISK2 works" description="From the assessment form to a saved prediction, each stage has a defined role in the application pipeline." />
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {workflow.map(({ icon: Icon, title, text }, i) => <motion.div key={title} initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.07 }} className="relative rounded-2xl border border-violet-300/15 bg-[#151226] p-5">
              <span className="absolute right-4 top-4 text-xs font-bold text-violet-400/70">0{i + 1}</span>
              <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-violet-500/15 text-violet-300"><Icon size={22} /></div>
              <h3 className="font-bold text-white">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{text}</p>
            </motion.div>)}
          </div>
        </div>
      </section>

      {/* Technology */}
      <section className="py-24">
        <div className="mx-auto max-w-[110rem] px-5 sm:px-8 lg:px-20 2xl:px-24">
          <SectionHeading eyebrow="Technology" title="Built with a modern" accent="full-stack architecture." description="The application separates the user interface, API and model-inference responsibilities, with persistent application data managed by the database service." />
          <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {technologies.map(({ icon: Icon, name, detail }) => <div key={name} className="rounded-2xl border border-white/10 bg-[#141225] p-5 text-center transition hover:-translate-y-1 hover:border-violet-400/40"><Icon className="mx-auto mb-4 text-violet-300" size={30} /><p className="font-bold text-white">{name}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></div>)}
          </div>
        </div>
      </section>

      {/* CTA and disclaimer */}
      <section className="relative overflow-hidden border-t border-violet-300/10 bg-[#100d20] py-24">
        <div className="absolute left-1/2 top-0 h-72 w-96 -translate-x-1/2 rounded-full bg-violet-600/15 blur-[100px]" />
        <div className="relative mx-auto max-w-4xl px-5 text-center">
          <BrandMark />
          <h2 className="mt-8 text-3xl font-extrabold tracking-tight text-white sm:text-5xl">Explore cardiovascular risk prediction with <span className="text-violet-400">BRISK2.</span></h2>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-400">Create an account to access the assessment workflow, prediction history and available analysis features.</p>
          <button onClick={() => navigate("/signup")} className="mt-8 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-8 py-4 text-sm font-bold text-white shadow-lg shadow-violet-900/30 transition hover:-translate-y-1">Get started <ArrowRight size={17} /></button>
          <p className="mx-auto mt-8 max-w-3xl text-xs leading-6 text-slate-500">Important: BRISK2 is a research prototype. It predicts the outcome represented in its training dataset. Its output is not a medical diagnosis, a guaranteed future-event probability, or a substitute for advice from a qualified healthcare professional.</p>
        </div>
      </section>

      <footer className="border-t border-white/10 bg-[#090914]">
        <div className="mx-auto flex max-w-[110rem] flex-col items-center justify-between gap-4 px-5 py-7 sm:flex-row sm:px-8 lg:px-20 2xl:px-24">
          <BrandMark compact />
          <p className="text-xs text-slate-500">Cardiovascular Disease Risk Prediction & Reliability Analysis</p>
          <p className="text-xs text-slate-600">© 2026 BRISK2 · Research prototype</p>
        </div>
      </footer>
    </main>
  );
}

export default Welcome;
