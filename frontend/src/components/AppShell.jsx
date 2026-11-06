import BrandLogo from "./BrandLogo";
import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, ClipboardList, Activity, FileText, LogOut } from "lucide-react";
import { useAppData } from "../context/AppDataContext";

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/assessment", label: "New assessment", icon: ClipboardList },
  { to: "/risk-analysis", label: "Risk analysis", icon: Activity },
  { to: "/report", label: "Report", icon: FileText },
];

const link = ({ isActive }) =>
  `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition ${
    isActive ? "bg-violet-500/15 text-violet-200 ring-1 ring-violet-400/30" : "text-slate-400 hover:bg-white/5 hover:text-white"
  }`;

export default function AppShell({ title, subtitle, actions, children }) {
  const { user, signOut } = useAppData();
  const navigate = useNavigate();
  const out = async () => { await signOut(); navigate("/signin"); };

  return (
    <div className="min-h-screen w-full bg-[#090914] text-slate-100 lg:flex">
      {/* Sidebar (desktop) */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-white/10 bg-[#0c0b19] p-5 lg:sticky lg:top-0 lg:flex lg:h-screen">
        <BrandLogo size={36} className="px-1" />
        <nav className="mt-8 flex flex-col gap-1.5">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={link}><Icon size={18} />{label}</NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
          <p className="truncate text-sm font-semibold text-white">{user?.name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <button onClick={out} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 py-2 text-xs font-semibold text-slate-300 transition hover:bg-white/5">
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        {/* Top bar (mobile) */}
        <header className="sticky top-0 z-30 border-b border-white/10 bg-[#0c0b19]/90 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <BrandLogo size={32} />
            <button onClick={out} aria-label="Sign out" className="rounded-lg border border-white/10 p-2 text-slate-300"><LogOut size={16} /></button>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-2">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} className={({ isActive }) =>
                `flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${isActive ? "bg-violet-500/15 text-violet-200" : "text-slate-400"}`}>
                <Icon size={15} />{label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto w-full max-w-[96rem] px-4 py-6 sm:px-6 lg:px-10 lg:py-9">
          <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{title}</h1>
              {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-slate-400">{subtitle}</p>}
            </div>
            {actions}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
