import { useMemo } from "react";

/** The public pages' visual, drawn entirely in code from the product's own motif: a phone outlined
 *  in soft glowing dots, step cards 1-2-3, and the highlighter-yellow tap ring pulsing on the row the
 *  customer should tap. Motion is CSS-only and slow; the global prefers-reduced-motion rule in
 *  index.css stops it, leaving a still picture. Always shown on a dark surface. */

// Phone outline in the 540 x 520 scene.
const PHONE = { x: 170, y: 56, w: 190, h: 400, r: 34 };

/** Evenly spaced points along a rounded rectangle's edge. */
function outlinePoints(x: number, y: number, w: number, h: number, r: number, gap: number) {
  const straight = 2 * (w - 2 * r) + 2 * (h - 2 * r);
  const total = straight + 2 * Math.PI * r;
  const n = Math.round(total / gap);
  const pts: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    let d = (i / n) * total;
    const seg = [w - 2 * r, (Math.PI * r) / 2, h - 2 * r, (Math.PI * r) / 2, w - 2 * r, (Math.PI * r) / 2, h - 2 * r, (Math.PI * r) / 2];
    let k = 0;
    while (d > seg[k]!) d -= seg[k++]!;
    const corner = (cx: number, cy: number, start: number) => {
      const a = start + d / r;
      return [cx + r * Math.cos(a), cy + r * Math.sin(a)] as [number, number];
    };
    switch (k) {
      case 0: pts.push([x + r + d, y]); break;
      case 1: pts.push(corner(x + w - r, y + r, -Math.PI / 2)); break;
      case 2: pts.push([x + w, y + r + d]); break;
      case 3: pts.push(corner(x + w - r, y + h - r, 0)); break;
      case 4: pts.push([x + w - r - d, y + h]); break;
      case 5: pts.push(corner(x + r, y + h - r, Math.PI / 2)); break;
      case 6: pts.push([x, y + h - r - d]); break;
      default: pts.push(corner(x + r, y + r, Math.PI)); break;
    }
  }
  return pts;
}

const CARDS = [
  { n: 1, text: "Open Settings", x: 18, y: 96, delay: "0s" },
  { n: 2, text: "Tap Security", x: 384, y: 262, delay: "-2s", active: true },
  { n: 3, text: "Tap Reset password", x: 28, y: 352, delay: "-4s" },
];

export default function HeroScene({ className = "" }: { className?: string }) {
  const dots = useMemo(() => outlinePoints(PHONE.x, PHONE.y, PHONE.w, PHONE.h, PHONE.r, 9), []);
  const inner = { x: PHONE.x + 16, w: PHONE.w - 32 };
  const rows = [0, 1, 2, 3, 4].map((i) => PHONE.y + 112 + i * 50);
  const hot = rows[1]!; // the highlighted row

  return (
    <svg
      viewBox="0 0 540 520"
      role="img"
      aria-label="Illustration: a phone outlined in glowing dots, with step cards 1, 2 and 3; step 2 marks the row to tap with a yellow ring."
      className={`hv-scene h-auto w-full ${className}`}
    >
      <defs>
        <radialGradient id="hv-glow-y" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#bfa181" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#bfa181" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="hv-glow-b" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#178582" stopOpacity="0.30" />
          <stop offset="100%" stopColor="#178582" stopOpacity="0" />
        </radialGradient>
        <filter id="hv-soft" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <pattern id="hv-grid" width="22" height="22" patternUnits="userSpaceOnUse">
          <circle cx="11" cy="11" r="0.9" fill="#ffffff" opacity="0.07" />
        </pattern>
      </defs>

      {/* ambient light and a faint dot grid */}
      <rect width="540" height="520" fill="url(#hv-grid)" />
      <circle cx="270" cy="200" r="230" fill="url(#hv-glow-b)" className="hv-breathe" />
      <circle cx="300" cy={hot + 20} r="120" fill="url(#hv-glow-y)" className="hv-breathe" style={{ animationDelay: "-3s" }} />

      {/* phone: a glass body and an outline of glowing dots */}
      <rect x={PHONE.x} y={PHONE.y} width={PHONE.w} height={PHONE.h} rx={PHONE.r} fill="#ffffff" opacity="0.035" />
      <g filter="url(#hv-soft)">
        {dots.map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r={1.9} fill="#dfe6ff" className="hv-twinkle"
            style={{ animationDelay: `${-((i * 0.37) % 5).toFixed(2)}s` }} />
        ))}
      </g>
      {/* speaker slot */}
      {[-12, -6, 0, 6, 12].map((dx) => (
        <circle key={dx} cx={PHONE.x + PHONE.w / 2 + dx} cy={PHONE.y + 20} r={1.6} fill="#dfe6ff" opacity="0.5" />
      ))}

      {/* screen title and rows, all quiet except the highlighted one */}
      <rect x={inner.x} y={PHONE.y + 48} width={inner.w} height={40} rx={10} fill="#178582" opacity="0.55" />
      <rect x={inner.x + 14} y={PHONE.y + 64} width={70} height={8} rx={4} fill="#ffffff" opacity="0.85" />
      {rows.map((y, i) =>
        y === hot ? null : (
          <g key={i} opacity="0.55">
            <rect x={inner.x} y={y} width={inner.w} height={38} rx={10} fill="#ffffff" opacity="0.07" />
            <circle cx={inner.x + 18} cy={y + 19} r={6} fill="#ffffff" opacity="0.22" />
            <rect x={inner.x + 32} y={y + 15} width={52 + ((i * 23) % 40)} height={7} rx={3.5} fill="#ffffff" opacity="0.22" />
          </g>
        ),
      )}

      {/* the row to tap */}
      <g>
        <rect x={inner.x - 3} y={hot - 3} width={inner.w + 6} height={44} rx={12} fill="#ffffff" />
        <rect x={inner.x - 3} y={hot - 3} width={inner.w + 6} height={44} rx={12} fill="none" stroke="#bfa181" strokeWidth="4" />
        <circle cx={inner.x + 18} cy={hot + 19} r={6} fill="#0a1828" opacity="0.18" />
        <rect x={inner.x + 32} y={hot + 15} width={64} height={7} rx={3.5} fill="#0a1828" opacity="0.7" />
        <circle cx={inner.x + inner.w - 22} cy={hot + 19} r={13} fill="none" stroke="#bfa181" strokeWidth="3" className="hv-ring" />
        <circle cx={inner.x + inner.w - 22} cy={hot + 19} r={13} fill="none" stroke="#bfa181" strokeWidth="3" className="hv-ring" style={{ animationDelay: "-1.2s" }} />
        <circle cx={inner.x + inner.w - 22} cy={hot + 19} r={7} fill="#bfa181" stroke="#0a1828" strokeWidth="2" />
      </g>

      {/* dotted line from the active card to the row it describes */}
      <path d={`M384 284 C 364 284, 368 ${hot + 19}, ${inner.x + inner.w + 6} ${hot + 19}`}
        fill="none" stroke="#bfa181" strokeWidth="1.6" strokeDasharray="2 6" strokeLinecap="round" opacity="0.8" className="hv-flow" />

      {/* step cards */}
      {CARDS.map((c) => {
        const w = c.text.length * 7.2 + 58;
        return (
          <g key={c.n} className="hv-float" style={{ animationDelay: c.delay }}>
            <rect x={c.x} y={c.y} width={w} height={44} rx={12}
              fill={c.active ? "#1d2a4a" : "#16203a"} stroke={c.active ? "#bfa181" : "#ffffff"}
              strokeOpacity={c.active ? 0.9 : 0.16} strokeWidth={c.active ? 1.6 : 1} />
            <circle cx={c.x + 22} cy={c.y + 22} r={11} fill="#bfa181" />
            <text x={c.x + 22} y={c.y + 26.5} textAnchor="middle" fontSize="12.5" fontWeight="600" fill="#0a1828">{c.n}</text>
            <text x={c.x + 42} y={c.y + 26.5} fontSize="13" fontWeight="500" fill="#ffffff" fillOpacity={c.active ? 1 : 0.86}>{c.text}</text>
          </g>
        );
      })}
    </svg>
  );
}
