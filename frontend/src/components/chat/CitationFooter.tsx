import { type Citation } from "@/lib/citations";

interface CitationFooterProps {
  citations: Citation[];
  content: string;
}

export function CitationFooter({ citations, content }: CitationFooterProps) {
  if (citations.length === 0) return null;

  // Only show sources that the LLM actually cited in its response
  const citedIndices = new Set<number>();
  const matches = content.matchAll(/\[(\d+)\]/g);
  for (const m of matches) {
    citedIndices.add(parseInt(m[1], 10));
  }

  const cited = citations.filter((c) => citedIndices.has(c.index));
  if (cited.length === 0) return null;

  // Deduplicate by file_name
  const seen = new Set<string>();
  const unique = cited.filter((c) => {
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
