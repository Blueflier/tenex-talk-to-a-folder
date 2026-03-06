import { formatCitationLabel, type Citation } from "@/lib/citations";

interface CitationFooterProps {
  citations: Citation[];
}

export function CitationFooter({ citations }: CitationFooterProps) {
  if (citations.length === 0) return null;

  // Deduplicate by file_name
  const seen = new Set<string>();
  const unique = citations.filter((c) => {
    if (seen.has(c.file_name)) return false;
    seen.add(c.file_name);
    return true;
  });

  return (
    <p className="text-xs text-muted-foreground mt-1.5">
      Sources:{" "}
      {unique.map((c, i) => (
        <span key={c.file_name}>
          {i > 0 && ", "}
          {c.file_name}
        </span>
      ))}
    </p>
  );
}
