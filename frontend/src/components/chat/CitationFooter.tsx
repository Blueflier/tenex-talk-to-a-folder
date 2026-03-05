import { formatCitationLabel, type Citation } from "@/lib/citations";

interface CitationFooterProps {
  citations: Citation[];
}

export function CitationFooter({ citations }: CitationFooterProps) {
  if (citations.length === 0) return null;

  return (
    <p className="text-xs text-muted-foreground mt-1.5">
      Sources:{" "}
      {citations.map((c, i) => (
        <span key={c.index}>
          {i > 0 && ", "}
          {formatCitationLabel(c)}
        </span>
      ))}
    </p>
  );
}
