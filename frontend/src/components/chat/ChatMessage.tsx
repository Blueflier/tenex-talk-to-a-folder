import { type ReactNode } from "react";
import Markdown from "react-markdown";
import type { Citation } from "@/lib/citations";
import { CitationBadge } from "./CitationBadge";
import { CitationFooter } from "./CitationFooter";
import { StreamingCursor } from "./StreamingCursor";
import { NoResultsMessage } from "./NoResultsMessage";
import { StalenessBannerList } from "./StalenessBannerList";
import type { StalenessInfo } from "./StalenessBanner";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  isStreaming: boolean;
  isNoResults: boolean;
  onCitationClick: (index: number, anchorEl: HTMLElement) => void;
  staleFiles?: StalenessInfo[];
  sessionId?: string;
  renderReindexButton?: (info: StalenessInfo) => React.ReactNode;
}

function renderContentWithCitations(
  content: string,
  citations: Citation[],
  onCitationClick: (index: number, anchorEl: HTMLElement) => void
): ReactNode {
  // Split content into text and citation tokens, but render markdown
  // as a single block and inject citation badges inline via custom components
  const citationIndices = new Set(citations.map((c) => c.index));

  return (
    <Markdown
      components={{
        p: ({ children }) => {
          // Process children to inject citation badges inline
          const processed = injectCitations(children, citationIndices, onCitationClick);
          return <p>{processed}</p>;
        },
        li: ({ children }) => {
          const processed = injectCitations(children, citationIndices, onCitationClick);
          return <li>{processed}</li>;
        },
      }}
    >
      {content}
    </Markdown>
  );
}

function injectCitations(
  children: ReactNode,
  citationIndices: Set<number>,
  onCitationClick: (index: number, anchorEl: HTMLElement) => void
): ReactNode {
  if (!children) return children;

  const childArray = Array.isArray(children) ? children : [children];
  const result: ReactNode[] = [];

  for (let i = 0; i < childArray.length; i++) {
    const child = childArray[i];
    if (typeof child === "string") {
      const parts = child.split(/(\[\d+\])/g);
      for (let j = 0; j < parts.length; j++) {
        const part = parts[j];
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const idx = parseInt(match[1], 10);
          if (citationIndices.has(idx)) {
            result.push(<CitationBadge key={`cite-${i}-${j}`} index={idx} onClick={onCitationClick} />);
            continue;
          }
        }
        if (part) result.push(part);
      }
    } else {
      result.push(child);
    }
  }

  return result;
}

export function ChatMessage({
  role,
  content,
  citations,
  isStreaming,
  isNoResults,
  onCitationClick,
  staleFiles,
  sessionId,
  renderReindexButton,
}: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-zinc-200 dark:bg-zinc-700 text-foreground"
            : "bg-zinc-50 dark:bg-zinc-800 text-foreground shadow-sm border border-zinc-200 dark:border-zinc-700"
        }`}
      >
        {!isUser && staleFiles && staleFiles.length > 0 && sessionId && (
          <StalenessBannerList staleFiles={staleFiles} sessionId={sessionId} renderReindexButton={renderReindexButton} />
        )}
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
