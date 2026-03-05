import { useCallback, useEffect, useRef, useState } from "react";
import type { Citation } from "@/lib/citations";
import { saveMessage, loadMessages } from "@/lib/db";
import { useStream } from "@/hooks/useStream";
import { MessageList, type MessageData } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { CitationPopover } from "./CitationPopover";

const NO_RESULTS_TEXT =
  "I couldn't find relevant information in the provided files. Try rephrasing your question or check if the right files were indexed.";

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
  const [needsAuth, setNeedsAuth] = useState(false);
  const [activeCitation, setActiveCitation] = useState<{
    citation: Citation;
    anchorEl: HTMLElement;
  } | null>(null);

  // Track current streaming message citations
  const pendingCitationsRef = useRef<Citation[]>([]);

  // Load messages from IndexedDB on mount
  useEffect(() => {
    loadMessages(sessionId).then((stored) => {
      if (stored.length > 0) {
        setMessages(
          stored.map((m) => ({
            role: m.role,
            content: m.content,
            citations: (m.citations ?? []) as Citation[],
            isStreaming: false,
            isNoResults: false,
          }))
        );
      }
    });
  }, [sessionId]);

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
            {
              ...last,
              content: NO_RESULTS_TEXT,
              isNoResults: true,
              isStreaming: false,
            },
          ];
        }
        return prev;
      });

      // Persist no_results assistant message
      saveMessage({
        session_id: sessionId,
        role: "assistant",
        content: NO_RESULTS_TEXT,
        citations: [],
        created_at: new Date().toISOString(),
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
          const finalMsg = { ...last, isStreaming: false };

          // Persist assistant message with frozen citations
          saveMessage({
            session_id: sessionId,
            role: "assistant",
            content: finalMsg.content,
            citations: pendingCitationsRef.current,
            created_at: new Date().toISOString(),
          });

          return [...prev.slice(0, -1), finalMsg];
        }
        return prev;
      });
    },
  });

  const handleSend = useCallback(
    (query: string) => {
      const token = sessionStorage.getItem("google_access_token");
      if (!token) {
        setNeedsAuth(true);
        return;
      }

      setNeedsAuth(false);

      // Save user message to IndexedDB
      saveMessage({
        session_id: sessionId,
        role: "user",
        content: query,
        citations: [],
        created_at: new Date().toISOString(),
      });

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
      {needsAuth && (
        <div className="mx-4 mt-2 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          Your session has expired. Please sign in again to send messages.
        </div>
      )}
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
