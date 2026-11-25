import { motion, type Variants } from "framer-motion";
import {
  ArrowRight, CheckCircle2, Clapperboard, Cpu, FileText, ImageIcon, Languages, ScanLine, ShieldCheck, Sparkles, Upload, Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import HeroScene from "../components/HeroScene";
import { Logo } from "../components/Logo";
import SampleGuide from "../components/SampleGuide";
import SceneBackground from "../components/SceneBackground";

const steps = [
  { icon: Upload, title: "Bring what you have", body: "A help article, a web address, a series of screenshots or a screen recording." },
  { icon: FileText, title: "Steps, checked against the source", body: "Every step must quote the article; every button name must appear in it. Gaps are flagged, not filled in." },
  { icon: ImageIcon, title: "A picture for every step", body: "Real screenshots with the control highlighted, or a calm scene with the exact screen drawn on the phone." },
  { icon: CheckCircle2, title: "Checked, repaired, approved by you", body: "Each picture is checked; failures are repaired one step at a time. Nothing is published until you approve it." },
];

const features = [
  { icon: FileText, title: "Grounded step extraction", body: "Quotes, controls and coverage checked in code against the article." },
  { icon: Workflow, title: "Action-state graph", body: "Each step is a move between screens, so missing steps show up as breaks." },
  { icon: ScanLine, title: "Screenshot and video studios", body: "Real screens, controls found by OCR, personal data blurred automatically." },
  { icon: ShieldCheck, title: "Verification and repair", body: "Image checks, targeted regeneration, and a review queue with your judgments." },
  { icon: Languages, title: "Hindi, Telugu, Spanish, French", body: "Translated step by step, names protected, meaning checked on a round trip." },
  { icon: Clapperboard, title: "A guide your customers can use", body: "Read aloud, large-text mode, questions answered from your documents, print to PDF." },
];

const chips = [
  { icon: Cpu, text: "Open models on your own GPU, or Gemini" },
  { icon: ShieldCheck, text: "Every picture checked" },
  { icon: Sparkles, text: "Interface names never invented" },
];

const rise: Variants = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } } };
const stagger: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };

function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.05 }}>
      {children}
    </motion.div>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <motion.p variants={rise} className="hv-eyebrow text-link">{children}</motion.p>;
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-surface">
      {/* Hero: always dark, the 3D neural sphere behind the headline. */}
      <div className="relative isolate overflow-hidden bg-navy text-white">
        <SceneBackground offsetX={1.7} />
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-gradient-to-r from-navy via-navy/70 to-transparent lg:via-navy/40" />

        <header className="relative z-10">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
            <Logo inverted />
            <nav className="flex items-center gap-1 whitespace-nowrap sm:gap-2">
              <Link to="/login" className="rounded-md px-2.5 py-2 font-medium text-white/80 transition-colors hover:text-white sm:px-3">Sign in</Link>
              <Link to="/register" className="hv-glass-dark rounded-md px-3 py-2 font-medium text-white transition-colors hover:border-gold/60 sm:px-4">
                Create account
              </Link>
            </nav>
          </div>
        </header>

        <section className="relative z-10 mx-auto flex min-h-[calc(92vh-4rem)] max-w-6xl items-center px-4 pb-20 pt-10 sm:px-6">
          <motion.div initial="hidden" animate="show" variants={stagger} className="max-w-2xl">
            <motion.p variants={rise} className="hv-eyebrow inline-flex items-center gap-2 rounded-full hv-glass-dark px-3 py-1.5 text-platinum">
              <span className="h-1.5 w-1.5 rounded-full bg-gold" aria-hidden="true" />
              Self-correcting visual guides
            </motion.p>
            <motion.h1 variants={rise} className="mt-7 text-[42px] font-semibold leading-[1.04] tracking-[-0.02em] sm:text-[64px]">
              <span className="hv-sheen">Help articles, turned into</span>{" "}
              <span className="text-gold">picture guides</span>{" "}
              <span className="hv-sheen">customers can follow.</span>
            </motion.h1>
            <motion.p variants={rise} className="mt-6 max-w-xl text-[17px] font-light leading-relaxed text-platinum/85">
              HelpVisual AI reads your support article, shows every step with the exact screen and the button to tap,
              checks each picture, and repairs what is wrong before anyone sees it.
            </motion.p>
            <motion.div variants={rise} className="mt-9 flex flex-wrap gap-3">
              <Link to="/register"
                className="group inline-flex items-center gap-2 rounded-md bg-gold px-5 py-3 font-semibold text-navy shadow-[0_10px_30px_-10px_rgba(191,161,129,0.7)] transition hover:bg-[#cdb497]">
                Make your first guide <ArrowRight size={18} aria-hidden="true" className="transition-transform group-hover:translate-x-0.5" />
              </Link>
              <a href="#how" className="hv-glass-dark rounded-md px-5 py-3 font-medium text-white transition-colors hover:border-platinum/40">
                See how it works
              </a>
            </motion.div>
            <motion.ul variants={rise} className="mt-12 flex flex-wrap gap-x-6 gap-y-3 text-[13px] text-platinum/75">
              {chips.map(({ icon: Icon, text }) => (
                <li key={text} className="inline-flex items-center gap-2">
                  <Icon size={15} aria-hidden="true" className="text-[#5cc8c2]" />
                  {text}
                </li>
              ))}
            </motion.ul>
          </motion.div>
        </section>
      </div>

      {/* What it makes: the product's own motif in a glass frame. */}
      <section className="relative overflow-hidden bg-navy pb-20 text-white">
        <Reveal className="mx-auto grid max-w-6xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-2">
          <div>
            <motion.p variants={rise} className="hv-eyebrow text-[#5cc8c2]">What it makes</motion.p>
            <motion.h2 variants={rise} className="mt-3 text-[32px] font-semibold leading-tight tracking-tight">
              The screen, the control, and the tap: <span className="text-gold">for every step</span>
            </motion.h2>
            <motion.p variants={rise} className="mt-4 max-w-lg text-[15px] leading-relaxed text-platinum/80">
              Steps come from your article, screens are drawn in code from the names it uses, and the gold ring marks
              exactly what to press. Nothing on the screen is invented by an image model.
            </motion.p>
          </div>
          <motion.div variants={rise} className="hv-glass-dark rounded-3xl p-6 shadow-[0_40px_80px_-40px_rgba(23,133,130,0.6)]">
            <HeroScene />
          </motion.div>
        </Reveal>
      </section>

      <section id="how" className="relative">
        <Reveal className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <Eyebrow>How it works</Eyebrow>
          <motion.h2 variants={rise} className="mt-3 max-w-2xl text-[32px] font-semibold leading-tight tracking-tight">
            From article to approved guide in four checked stages
          </motion.h2>
          <ol className="relative mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            <div aria-hidden="true" className="absolute left-0 right-0 top-[52px] hidden h-px bg-gradient-to-r from-transparent via-turquoise/50 to-transparent lg:block" />
            {steps.map(({ icon: Icon, title, body }, i) => (
              <motion.li variants={rise} key={title} className="hv-lift hv-glass relative rounded-2xl border border-line p-6">
                <div className="flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-turquoise/25 to-turquoise/5 text-link ring-1 ring-turquoise/25">
                    <Icon size={22} strokeWidth={1.6} aria-hidden="true" />
                  </span>
                  <span className="hv-eyebrow text-ink-soft">0{i + 1}</span>
                </div>
                <h3 className="mt-5 text-[16px] font-semibold">{title}</h3>
                <p className="mt-2 text-ink-soft">{body}</p>
              </motion.li>
            ))}
          </ol>
        </Reveal>
      </section>

      <section className="border-y border-line bg-paper/60">
        <Reveal className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-24 sm:px-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <div>
            <Eyebrow>Sample guide</Eyebrow>
            <motion.h2 variants={rise} className="mt-3 text-[32px] font-semibold leading-tight tracking-tight">
              One calm scene, the exact screen, the control to tap
            </motion.h2>
            <motion.p variants={rise} className="mt-4 text-[15px] leading-relaxed text-ink-soft">
              The help-center card keeps one scene for the whole guide and draws each step's screen in code, so interface
              names are always the ones in your article. A magnified callout shows the control up close.
            </motion.p>
          </div>
          <motion.div variants={rise}><SampleGuide /></motion.div>
        </Reveal>
      </section>

      <section>
        <Reveal className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
          <Eyebrow>What is inside</Eyebrow>
          <motion.h2 variants={rise} className="mt-3 text-[32px] font-semibold leading-tight tracking-tight">Every part checked, nothing invented</motion.h2>
          <ul className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, body }) => (
              <motion.li variants={rise} key={title} className="hv-lift hv-glass rounded-2xl border border-line p-6">
                <span className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-gold/30 to-gold/5 text-ink ring-1 ring-gold/30">
                  <Icon size={22} strokeWidth={1.6} aria-hidden="true" />
                </span>
                <h3 className="mt-5 text-[16px] font-semibold">{title}</h3>
                <p className="mt-2 text-ink-soft">{body}</p>
              </motion.li>
            ))}
          </ul>
        </Reveal>
      </section>

      {/* Closing call to action on the brand surface, with a light CSS orbit instead of a second 3D scene. */}
      <section className="px-4 pb-24 sm:px-6">
        <div className="relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-gradient-to-br from-[#10304a] via-navy to-navy px-8 py-16 text-white ring-1 ring-turquoise/30 sm:px-14">
          <div aria-hidden="true" className="absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full border border-turquoise/40 hv-orbit">
            <span className="absolute left-1/2 top-0 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold shadow-[0_0_16px_4px_rgba(191,161,129,0.6)]" />
          </div>
          <div aria-hidden="true" className="absolute -right-6 top-10 h-[260px] w-[260px] rounded-full border border-platinum/20" />
          <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(50%_80%_at_85%_20%,rgba(23,133,130,0.35),transparent_70%)]" />
          <div className="relative max-w-xl">
            <h2 className="text-[30px] font-semibold leading-tight tracking-tight">Turn your next help article into a guide people can follow.</h2>
            <p className="mt-3 text-platinum/80">Your guides stay private to your account until you approve them.</p>
            <Link to="/register" className="mt-8 inline-flex items-center gap-2 rounded-md bg-gold px-5 py-3 font-semibold text-navy transition hover:bg-[#cdb497]">
              Create your account <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-ink-soft sm:px-6">
          <span>HelpVisual AI: a multimodal, context-aware and self-correcting generative framework for customer support documentation.</span>
          <span>Open models on your own GPU, with optional Gemini images.</span>
        </div>
      </footer>
    </div>
  );
}
