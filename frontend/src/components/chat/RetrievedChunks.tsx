import { useState } from "react";
import { formatCitationLabel, type Citation } from "@/lib/citations";

const CHUNK_TRUNCATE = 200;

interface RetrievedChunksProps {
  citations: Citation[];
}

function ChunkCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(false);
  const needsTruncation = citation.chunk_text.length > CHUNK_TRUNCATE;
  const displayText =
    !expanded && needsTruncation
      ? citation.chunk_text.slice(0, CHUNK_TRUNCATE) + "..."
      : citation.chunk_text;

  const isLiveSearch = citation.source === "grep";

  return (
    <div className="border-l-2 border-blue-300 dark:border-blue-600 bg-zinc-100 dark:bg-zinc-900 rounded-r-lg px-3 py-2">
      <div className="flex items-center gap-2 flex-wrap mb-1">
        <span className="text-xs font-medium text-foreground bg-zinc-200 dark:bg-zinc-700 rounded px-1.5 py-0.5">
          [{citation.index}] {formatCitationLabel(citation)}
        </span>
        {isLiveSearch && (
          <span className="text-[10px] font-medium text-blue-700 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/40 rounded px-1.5 py-0.5">
            live search
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed font-mono mt-1">
        {displayText}
      </p>
      {needsTruncation && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline mt-1"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

export function RetrievedChunks({ citations }: RetrievedChunksProps) {
  const [open, setOpen] = useState(false);

  if (citations.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
      >
        <svg
          className={`h-3 w-3 transition-transform ${open ? "rotate-90" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        {open
          ? "Hide sources"
          : `View ${citations.length} source${citations.length !== 1 ? "s" : ""}`}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {citations.map((c) => (
            <ChunkCard key={c.index} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}
