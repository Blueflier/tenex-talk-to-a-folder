import { useCallback, useRef, useState } from "react";
import type { Citation } from "@/lib/citations";
import { useStream } from "@/hooks/useStream";
import { MessageList, type MessageData } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { CitationPopover } from "./CitationPopover";

interface ChatViewProps {
  sessionId: string;
  fileList: string[];
  initialMessages?: MessageData[];
}

export function ChatView({
  sessionId,
  fileList,
  initialMessages = [],
}: ChatViewProps) {
  const [messages, setMessages] = useState<MessageData[]>(initialMessages);
  const [activeCitation, setActiveCitation] = useState<{
    citation: Citation;
    anchorEl: HTMLElement;
  } | null>(null);

  // Track current streaming message citations
  const pendingCitationsRef = useRef<Citation[]>([]);

  const { sendMessage, isStreaming, abort } = useStream({
    onToken(content) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.isStreaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, content: last.content + content },
          ];
        }
        return prev;
      });
    },
    onCitations(citations) {
      pendingCitationsRef.current = citations;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { ...last, citations }];
        }
        return prev;
      });
    },
    onNoResults() {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.isStreaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, isNoResults: true, isStreaming: false },
          ];
        }
        return prev;
      });
    },
    onError(message) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.isStreaming) {
          return [
            ...prev.slice(0, -1),
            {
              ...last,
              content: `Error: ${message}`,
              isStreaming: false,
            },
          ];
        }
        return prev;
      });
    },
    onDone() {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.isStreaming) {
          return [...prev.slice(0, -1), { ...last, isStreaming: false }];
        }
        return prev;
      });
    },
  });

  const handleSend = useCallback(
    (query: string) => {
      const token = sessionStorage.getItem("google_access_token");
      if (!token) return;

      // Add user message
      const userMsg: MessageData = {
        role: "user",
        content: query,
        citations: [],
        isStreaming: false,
        isNoResults: false,
      };

      // Add placeholder assistant message
      const assistantMsg: MessageData = {
        role: "assistant",
        content: "",
        citations: [],
        isStreaming: true,
        isNoResults: false,
      };

      pendingCitationsRef.current = [];
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      sendMessage(sessionId, query, fileList, token);
    },
    [sessionId, fileList, sendMessage]
  );

  const handleCitationClick = useCallback(
    (index: number, anchorEl: HTMLElement) => {
      // Find citation from the latest assistant message
      const lastAssistant = [...messages]
        .reverse()
        .find((m) => m.role === "assistant");
      const citation = lastAssistant?.citations.find((c) => c.index === index);
      if (citation) {
        setActiveCitation({ citation, anchorEl });
      }
    },
    [messages]
  );

  return (
    <div className="flex flex-col h-full">
      <MessageList
        messages={messages}
        onCitationClick={handleCitationClick}
      />
      <ChatInput
        isStreaming={isStreaming}
        onSend={handleSend}
        onStop={abort}
      />
      <CitationPopover
        citation={activeCitation?.citation ?? null}
        anchorEl={activeCitation?.anchorEl ?? null}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
