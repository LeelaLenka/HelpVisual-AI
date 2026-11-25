import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "./Logo";
import SceneBackground from "./SceneBackground";

/** Split-screen frame for the sign-in pages: the dark 3D panel on the left (the neural sphere with
 *  a glass step card from the product's own motif), the form on the right. Below the lg breakpoint
 *  the panel is left out and the form takes the whole width. */
export default function AuthLayout({ title, intro, children, footer }: {
  title: string;
  intro?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="hv-ambient grid min-h-screen lg:grid-cols-2">
      <aside className="relative isolate hidden overflow-hidden bg-navy lg:flex lg:min-h-screen lg:flex-col lg:justify-between lg:p-12">
        <SceneBackground />
        <Link to="/" aria-label="HelpVisual AI home" className="relative z-10 self-start">
          <Logo inverted />
        </Link>

        {/* One step of a guide, floating over the sphere. */}
        <motion.div
          aria-hidden="true"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: [0, -6, 0] }}
          transition={{ opacity: { duration: 0.8 }, y: { duration: 7, repeat: Infinity, ease: "easeInOut" } }}
          className="hv-glass-dark relative z-10 ml-auto mr-6 mt-auto mb-10 flex w-[260px] items-center gap-3 rounded-2xl px-4 py-3 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]"
        >
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gold text-sm font-semibold text-navy">2</span>
          <div className="min-w-0">
            <p className="hv-eyebrow text-[10px] text-platinum/60">Step 2 of 5</p>
            <p className="truncate font-medium text-white">Tap Security</p>
          </div>
          <span className="ml-auto grid h-7 w-7 place-items-center rounded-full ring-2 ring-gold/70">
            <span className="h-3 w-3 rounded-full bg-gold" />
          </span>
        </motion.div>

        <div className="hv-glass-dark relative z-10 max-w-[460px] rounded-2xl p-6">
          <p className="text-[22px] font-semibold leading-snug tracking-tight text-white">
            A picture for every step, drawn from your article.
          </p>
          <p className="mt-3 text-[15px] leading-relaxed text-platinum/80">
            Each step shows the screen and the control to tap. Interface names come from your article, never
            invented, and every image is checked before you approve the guide.
          </p>
        </div>
      </aside>

      <div className="flex flex-col px-6 py-8 sm:px-12 lg:px-16">
        <Link to="/" aria-label="HelpVisual AI home" className="self-start lg:invisible">
          <Logo />
        </Link>
        <motion.main
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto flex w-full max-w-[420px] flex-1 flex-col justify-center py-14"
        >
          <p className="hv-eyebrow text-link">HelpVisual AI</p>
          <h1 className="mt-3 text-[32px] font-semibold leading-[1.12] tracking-[-0.02em] sm:text-[38px]">{title}</h1>
          {intro && <p className="mt-3 text-[15px] text-ink-soft">{intro}</p>}
          <div className="mt-10">{children}</div>
          {footer && <div className="mt-10 border-t border-line pt-6 text-ink-soft">{footer}</div>}
        </motion.main>
        <p className="text-xs text-ink-soft">Your guides are private to your account until you approve them.</p>
      </div>
    </div>
  );
}
