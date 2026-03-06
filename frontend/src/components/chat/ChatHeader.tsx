import { FileText } from "lucide-react";

interface ChatHeaderProps {
  filesIndexed: number;
  totalChunks: number;
  fileNames: string[];
}

/**
 * Build a placeholder string like "Ask about Q3-Report.pdf, Budget.xlsx, and 6 more..."
 */
export function buildPlaceholder(fileNames: string[]): string {
  if (fileNames.length === 0) return "Ask about your files...";
  if (fileNames.length === 1) return `Ask about ${fileNames[0]}...`;
  if (fileNames.length === 2)
    return `Ask about ${fileNames[0]} and ${fileNames[1]}...`;
  return `Ask about ${fileNames[0]}, ${fileNames[1]}, and ${fileNames.length - 2} more...`;
}

export function ChatHeader({
  filesIndexed,
  totalChunks,
}: ChatHeaderProps) {
  if (filesIndexed === 0) return null;

  return (
    <div
      className="flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/50 text-sm text-muted-foreground"
      data-testid="chat-header"
    >
      <FileText className="w-4 h-4 shrink-0" />
      <span>
        {filesIndexed} file{filesIndexed !== 1 ? "s" : ""} indexed &mdash;{" "}
        {totalChunks} chunks
      </span>
    </div>
  );
}
