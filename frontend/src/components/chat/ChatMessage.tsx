import { type ReactNode } from "react";
import Markdown from "react-markdown";
import type { Citation } from "@/lib/citations";
import { CitationBadge } from "./CitationBadge";
import { CitationFooter } from "./CitationFooter";
import { StreamingCursor } from "./StreamingCursor";
import { NoResultsMessage } from "./NoResultsMessage";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  isStreaming: boolean;
  isNoResults: boolean;
  onCitationClick: (index: number, anchorEl: HTMLElement) => void;
}

function renderContentWithCitations(
  content: string,
  citations: Citation[],
  onCitationClick: (index: number, anchorEl: HTMLElement) => void
): ReactNode[] {
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const idx = parseInt(match[1], 10);
      const exists = citations.some((c) => c.index === idx);
      if (exists) {
        return <CitationBadge key={i} index={idx} onClick={onCitationClick} />;
      }
    }
    if (!part) return null;
    return <Markdown key={i}>{part}</Markdown>;
  });
}

export function ChatMessage({
  role,
  content,
  citations,
  isStreaming,
  isNoResults,
  onCitationClick,
}: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-zinc-200 dark:bg-zinc-700 text-foreground"
            : "bg-white dark:bg-zinc-800 text-foreground"
        }`}
      >
        {isNoResults ? (
          <NoResultsMessage />
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
            {isStreaming ? (
              <>
                <Markdown>{content}</Markdown>
                <StreamingCursor visible={true} />
              </>
            ) : (
              renderContentWithCitations(content, citations, onCitationClick)
            )}
          </div>
        )}

        {!isStreaming && !isNoResults && citations.length > 0 && (
          <CitationFooter citations={citations} />
        )}
      </div>
    </div>
  );
}
