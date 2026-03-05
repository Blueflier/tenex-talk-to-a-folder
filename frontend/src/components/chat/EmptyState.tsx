import {
  generateSuggestions,
  type IndexedSource,
} from "@/lib/suggestions";

interface EmptyStateProps {
  indexedSources: IndexedSource[];
  onSuggestionClick: (query: string) => void;
}

export function EmptyState({
  indexedSources,
  onSuggestionClick,
}: EmptyStateProps) {
  const fileCount = indexedSources.reduce(
    (sum, s) => sum + s.file_list.length,
    0
  );
  const suggestions = generateSuggestions(indexedSources);

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
      <p className="mb-6 text-lg font-medium text-foreground">
        {fileCount} {fileCount === 1 ? "file" : "files"} indexed
      </p>

      {suggestions.length > 0 && (
        <div className="grid w-full max-w-xl grid-cols-1 gap-3 sm:grid-cols-2">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onSuggestionClick(suggestion)}
              className="rounded-lg border border-border bg-card px-4 py-3 text-left text-sm text-card-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
