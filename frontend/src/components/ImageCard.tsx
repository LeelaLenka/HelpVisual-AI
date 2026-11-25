import type { ImageRow } from "../types";
import { Badge } from "../ui";

/** One generated image with its guide, step and check result. */
export default function ImageCard({ row, onOpen }: { row: ImageRow; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="group overflow-hidden rounded-lg border border-line bg-paper text-left hover:border-ink/30">
      <div className="aspect-[4/3] overflow-hidden bg-surface">
        <img src={row.image_url} alt={`Step ${row.index}: ${row.action}`} loading="lazy"
          className="h-full w-full object-cover object-top" />
      </div>
      <div className="space-y-1.5 p-3">
        <p className="line-clamp-1 text-xs text-ink-soft">{row.guide_title}</p>
        <p className="line-clamp-2 font-medium leading-snug">{row.index}. {row.action}</p>
        <div className="flex flex-wrap gap-1">
          {row.passed !== null && <Badge tone={row.passed ? "good" : "bad"}>{row.passed ? "Passed" : "Failed"} {row.score}</Badge>}
          {row.human_label === true && <Badge tone="good">Reviewed right</Badge>}
          {row.human_label === false && <Badge tone="bad">Reviewed wrong</Badge>}
          {row.human_label === null && <Badge>Not reviewed</Badge>}
        </div>
      </div>
    </button>
  );
}
