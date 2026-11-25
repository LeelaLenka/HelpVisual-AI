/** The HelpVisual mark: a screen with one row highlighted and a tap ring, which is what the
 *  product draws on every guide. The frame follows the text colour, so it works in both themes. */
export function LogoMark({ size = 28, inverted = false }: { size?: number; inverted?: boolean }) {
  const frame = inverted ? "#FFFFFF" : "currentColor";
  const inner = inverted ? "#0A1828" : "var(--color-paper)";
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <rect x="2" y="2" width="28" height="28" rx="7" fill={frame} />
      <rect x="8" y="8.5" width="16" height="3" rx="1.5" fill={inner} opacity=".35" />
      <rect x="7" y="14" width="18" height="5" rx="2.5" fill="#BFA181" />
      <rect x="8" y="21.5" width="10" height="3" rx="1.5" fill={inner} opacity=".35" />
      <circle cx="21.5" cy="16.5" r="4.6" fill="none" stroke={inner} strokeWidth="1.6" />
    </svg>
  );
}

export function Logo({ inverted = false }: { inverted?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${inverted ? "text-white" : "text-ink"}`}>
      <LogoMark inverted={inverted} />
      <span className="whitespace-nowrap text-[16px] font-semibold tracking-tight">HelpVisual AI</span>
    </span>
  );
}
