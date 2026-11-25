import {
  BarChart3, BookOpen, Clapperboard, FilePlus2, Images, Languages, LayoutDashboard, Library,
  PlaySquare, ScanLine, Settings, ShieldCheck, type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link, NavLink, useLocation } from "react-router-dom";
import { AiOfflineBanner, AiStatusDot, AiStatusProvider } from "../aiStatus";
import { useAuth } from "../auth";
import { Logo } from "./Logo";

interface Item {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  planned?: string; // not built yet: shown, but not a link
}

// Sections that are not built yet are listed so the product's scope is visible, but they are not
// links and say so: no page pretends to work before it does.
const groups: { label: string; items: Item[] }[] = [
  {
    label: "Workspace",
    items: [
      { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
      { to: "/app/new", label: "Create guide", icon: FilePlus2 },
      { to: "/app/guides", label: "All guides", icon: Library },
    ],
  },
  {
    label: "Studios",
    items: [
      { to: "/app/images", label: "AI Image Studio", icon: Images },
      { to: "/app/screenshots", label: "Screenshot Studio", icon: ScanLine },
      { to: "/app/video", label: "Video Studio", icon: Clapperboard },
      { to: "/app/languages", label: "Multilingual Studio", icon: Languages },
    ],
  },
  {
    label: "Quality and publishing",
    items: [
      { to: "/app/verify", label: "Verification Center", icon: ShieldCheck },
      { to: "/app/published", label: "Interactive Guides", icon: PlaySquare },
      { to: "/app/knowledge", label: "Knowledge Base", icon: BookOpen },
      { to: "/app/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
];

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
}

function NavItem({ item, onNavigate }: { item: Item; onNavigate: () => void }) {
  const Icon = item.icon;
  if (item.planned) {
    return (
      <span
        title={item.planned}
        aria-disabled="true"
        className="flex cursor-default items-center gap-2.5 rounded-md px-2.5 py-1.5 text-ink-soft/60"
      >
        <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
        <span className="flex-1">{item.label}</span>
        <span className="rounded border border-line px-1.5 text-[10px] font-medium">Planned</span>
      </span>
    );
  }
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 font-medium transition-colors ${
          isActive ? "text-ink" : "text-ink-soft hover:bg-turquoise/5 hover:text-ink"
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="hv-nav-active"
              transition={{ type: "spring", stiffness: 420, damping: 36 }}
              className="absolute inset-0 rounded-lg bg-gradient-to-r from-turquoise/20 to-turquoise/5 ring-1 ring-inset ring-turquoise/30"
            >
              <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-gold" />
            </motion.span>
          )}
          <Icon size={16} strokeWidth={1.75} aria-hidden="true" className={`relative ${isActive ? "text-link" : ""}`} />
          <span className="relative">{item.label}</span>
        </>
      )}
    </NavLink>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  const sidebar = (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-3 py-5">
      <Link to="/app" onClick={close} className="px-2.5">
        <Logo />
      </Link>
      <nav aria-label="Main" className="flex flex-col gap-4">
        {groups.map((group) => (
          <div key={group.label}>
            <p className="hv-eyebrow mb-1.5 px-2.5 text-[10.5px] text-ink-soft/80">{group.label}</p>
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => <NavItem key={item.to} item={item} onNavigate={close} />)}
            </div>
          </div>
        ))}
      </nav>
      <div className="mt-auto space-y-1 border-t border-line pt-3">
        <AiStatusDot />
        <NavItem item={{ to: "/app/settings", label: "Settings", icon: Settings }} onNavigate={close} />
        {user && (
          <div className="flex items-center gap-3 px-2.5 pt-2">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-turquoise to-navy text-xs font-semibold text-white ring-1 ring-gold/50">
              {initials(user.name)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{user.name}</p>
              <p className="truncate text-xs text-ink-soft">{user.email}</p>
            </div>
            <button onClick={signOut} className="rounded px-2 py-1 text-xs font-medium text-ink-soft hover:bg-surface hover:text-ink">
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <AiStatusProvider>
    <div className="hv-ambient min-h-screen lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="hv-glass sticky top-0 hidden h-screen border-r border-line lg:block">{sidebar}</aside>
      <header className="hv-glass sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line px-4 lg:hidden">
        <Link to="/app"><Logo /></Link>
        <button onClick={() => setOpen(true)} aria-label="Open menu" aria-expanded={open}
          className="rounded-lg border border-line px-3 py-1.5 font-medium">Menu</button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <button aria-label="Close menu" className="absolute inset-0 bg-black/40" onClick={close} />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-paper shadow-2xl">{sidebar}</div>
        </div>
      )}
      <main className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8">
        <AiOfflineBanner />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
    </AiStatusProvider>
  );
}
