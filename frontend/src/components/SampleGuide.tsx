import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";

/** A sample guide on the landing page, laid out like the app's help-center card (one calm scene,
 *  a large phone screen of the step's state with the control highlighted, and a magnified callout).
 *  Drawn here in HTML for illustration, and labelled as an example: it is not output from the
 *  models. In the app, the scene comes from SDXL and the screen is drawn from the article. */

type Row = { label: string; hot?: boolean; toggle?: boolean };
type Slide = { action: string; screen: string; kind: "home" | "list"; rows: Row[]; control: string };

const SLIDES: Slide[] = [
  {
    action: "Open Settings",
    screen: "Home",
    kind: "home",
    control: "Settings",
    rows: [{ label: "Phone" }, { label: "Camera" }, { label: "Photos" }, { label: "Settings", hot: true }, { label: "Clock" }, { label: "Maps" }],
  },
  {
    action: "Tap Display",
    screen: "Settings",
    kind: "list",
    control: "Display",
    rows: [{ label: "Account" }, { label: "Notifications" }, { label: "Display", hot: true }, { label: "Privacy" }, { label: "Storage" }],
  },
  {
    action: "Turn on Dark mode",
    screen: "Display",
    kind: "list",
    control: "Dark mode",
    rows: [{ label: "Brightness" }, { label: "Dark mode", hot: true, toggle: true }, { label: "Text size" }, { label: "Screen timeout" }],
  },
];

const Tap = () => (
  <span aria-hidden="true" className="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full ring-4 ring-mark/60">
    <span className="h-3.5 w-3.5 rounded-full border-2 border-brand bg-mark" />
  </span>
);

function Toggle({ on }: { on?: boolean }) {
  return (
    <span aria-hidden="true" className={`ml-auto mr-8 inline-flex h-4 w-7 items-center rounded-full p-0.5 ${on ? "bg-[#178582]" : "bg-[#cfd5df]"}`}>
      <span className={`h-3 w-3 rounded-full bg-white ${on ? "ml-auto" : ""}`} />
    </span>
  );
}

function RowView({ row, big = false }: { row: Row; big?: boolean }) {
  return (
    <div className={`relative flex items-center gap-2 rounded-md bg-white ${big ? "h-14 pl-3 pr-2 text-[15px]" : "h-[26px] px-2 text-[10px]"} ${
      row.hot ? "ring-[3px] ring-mark" : ""}`}>
      <span className={`shrink-0 rounded-full bg-[#dfe4ec] ${big ? "h-6 w-6" : "h-3 w-3"}`} />
      <span className={`font-medium text-[#0a1828] ${big ? "whitespace-nowrap" : "truncate"}`}>{row.label}</span>
      {row.toggle && <Toggle />}
      {row.hot && <Tap />}
    </div>
  );
}

function Phone({ slide }: { slide: Slide }) {
  return (
    <div className="h-full rounded-[22px] bg-[#0a1828] p-[5px] shadow-[0_18px_40px_-12px_rgba(15,23,42,0.55)]">
      <div className="flex h-full flex-col overflow-hidden rounded-[18px] bg-[#f3f5f9]">
        <div className="flex h-4 items-center justify-between px-3 text-[7px] font-medium text-[#0a1828]/70">
          <span>9:41</span><span className="h-1.5 w-4 rounded-sm bg-[#0a1828]/50" />
        </div>
        {slide.kind === "home" ? (
          <div className="grid flex-1 grid-cols-3 content-start gap-x-2 gap-y-3 bg-gradient-to-b from-[#178582] to-[#0f4f5e] px-3 pt-4">
            {slide.rows.map((r) => (
              <div key={r.label} className="flex flex-col items-center gap-1">
                <span className={`relative h-8 w-8 rounded-[9px] bg-white/85 ${r.hot ? "ring-[3px] ring-mark" : ""}`}>
                  {r.hot && (
                    <span aria-hidden="true" className="absolute -right-1.5 -top-1.5 h-3.5 w-3.5 rounded-full border-2 border-brand bg-mark" />
                  )}
                </span>
                <span className="hidden text-[8px] font-medium text-white sm:block">{r.label}</span>
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="bg-[#178582] px-3 py-2 text-[11px] font-semibold text-white">{slide.screen}</div>
            <div className="space-y-1.5 p-2">
              {slide.rows.map((r) => <RowView key={r.label} row={r} />)}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Callout({ slide }: { slide: Slide }) {
  const hot = slide.rows.find((r) => r.hot)!;
  let body: ReactNode;
  if (slide.kind === "home") {
    body = (
      <div className="flex flex-col items-center gap-2 py-1">
        <span className="relative h-16 w-16 rounded-[18px] bg-[#e6eaf3] ring-4 ring-mark">
          <span aria-hidden="true" className="absolute -right-2 -top-2 h-6 w-6 rounded-full border-[3px] border-brand bg-mark" />
        </span>
      </div>
    );
  } else {
    body = <RowView row={{ ...hot, toggle: hot.toggle }} big />;
  }
  return (
    <div className="w-full rounded-xl bg-white p-3 shadow-[0_14px_30px_-10px_rgba(15,23,42,0.45)]">
      {body}
      {slide.kind === "home" && <p className="mt-1 text-center text-[13px] font-semibold text-[#0a1828]">{slide.control}</p>}
    </div>
  );
}

/** The scene behind the phone: a soft wall, window light, a desk edge and a plant, made of CSS shapes. */
function Scene() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden bg-gradient-to-b from-[#efe9df] to-[#e6dccd]">
      <div className="absolute right-[8%] top-[8%] h-[46%] w-[34%] rounded-md bg-gradient-to-br from-[#fdfbf6] to-[#e8eef2] opacity-90 blur-[2px]" />
      <div className="absolute inset-x-0 bottom-0 h-[22%] bg-gradient-to-b from-[#c9b291] to-[#b99f7b] blur-[1px]" />
      <div className="absolute bottom-[20%] left-[2%] h-[14%] w-[7%] rounded-b-lg bg-[#d97f5b] blur-[1px]" />
      <div className="absolute bottom-[32%] left-[0.5%] h-[18%] w-[10%] rounded-full bg-[#6f9c6a] blur-[3px]" />
      <div className="absolute bottom-[40%] left-[3%] h-[14%] w-[6%] rounded-full bg-[#82b07a] blur-[3px]" />
      <div className="absolute inset-0 bg-white/20" />
    </div>
  );
}

function Card({ slide }: { slide: Slide }) {
  return (
    <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl">
      <Scene />
      <div className="absolute bottom-[6%] left-[12%] top-[6%] aspect-[9/18.5]">
        <Phone slide={slide} />
      </div>
      <div className="absolute right-[5%] top-1/2 w-[42%] -translate-y-1/2">
        <Callout slide={slide} />
      </div>
    </div>
  );
}

export default function SampleGuide() {
  const [index, setIndex] = useState(0);
  const go = (i: number) => setIndex((i + SLIDES.length) % SLIDES.length);
  const slide = SLIDES[index]!;

  return (
    <section aria-roledescription="carousel" aria-label="Sample guide: turn on dark mode" className="rounded-2xl border border-line bg-paper p-4 shadow-sm sm:p-6">
      <div className="overflow-hidden rounded-xl">
        <div className="flex transition-transform duration-500 ease-out" style={{ transform: `translateX(-${index * 100}%)` }}>
          {SLIDES.map((s, i) => (
            <div key={s.action} className="w-full shrink-0" aria-hidden={i !== index} role="group" aria-roledescription="slide"
              aria-label={`Step ${i + 1} of ${SLIDES.length}`}>
              <Card slide={s} />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <p aria-live="polite" className="flex items-center gap-3 text-[17px] font-medium">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-mark text-sm font-semibold text-brand">{index + 1}</span>
          {slide.action}
        </p>
        <div className="flex items-center gap-2">
          {SLIDES.map((s, i) => (
            <button key={s.action} onClick={() => go(i)} aria-label={`Show step ${i + 1}`} aria-current={i === index}
              className={`h-2.5 rounded-full transition-all ${i === index ? "w-6 bg-accent" : "w-2.5 bg-line hover:bg-ink-soft"}`} />
          ))}
          <button onClick={() => go(index - 1)} aria-label="Previous step"
            className="ml-2 grid h-9 w-9 place-items-center rounded-full border border-line hover:bg-surface">
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
          <button onClick={() => go(index + 1)} aria-label="Next step"
            className="grid h-9 w-9 place-items-center rounded-full border border-line hover:bg-surface">
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        </div>
      </div>
      <p className="mt-3 text-xs text-ink-soft">
        Example drawn for this page, in the layout of the app's help-center card. In the app, the scene is painted by
        SDXL and the screen is drawn from the names in your article.
      </p>
    </section>
  );
}
