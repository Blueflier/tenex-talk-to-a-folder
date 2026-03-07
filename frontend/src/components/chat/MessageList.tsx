import { useEffect, useRef } from "react";
import type { Citation } from "@/lib/citations";
import type { StalenessInfo } from "./StalenessBanner";
import type { GrepInfo } from "@/hooks/useStream";
import { ChatMessage } from "./ChatMessage";

export interface MessageData {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  isStreaming: boolean;
  isNoResults: boolean;
  staleFiles?: StalenessInfo[];
  grepInfo?: GrepInfo[];
}

interface MessageListProps {
  messages: MessageData[];
  sessionId: string;
  onCitationClick: (index: number, anchorEl: HTMLElement) => void;
  renderReindexButton?: (info: StalenessInfo) => React.ReactNode;
}

export function MessageList({ messages, sessionId, onCitationClick, renderReindexButton }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      {messages.map((msg, i) => (
        <ChatMessage
          key={i}
          role={msg.role}
          content={msg.content}
          citations={msg.citations}
          isStreaming={msg.isStreaming}
          isNoResults={msg.isNoResults}
          onCitationClick={onCitationClick}
          staleFiles={msg.staleFiles}
          grepInfo={msg.grepInfo}
          sessionId={sessionId}
          renderReindexButton={renderReindexButton}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
