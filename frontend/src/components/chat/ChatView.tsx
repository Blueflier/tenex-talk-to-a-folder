import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { Citation } from "@/lib/citations";
import type { StalenessInfo } from "./StalenessBanner";
import type { IndexedSource } from "@/lib/suggestions";
import { saveMessage, loadMessages } from "@/lib/db";
import { useStream } from "@/hooks/useStream";
import { useReindex } from "@/hooks/useReindex";
import { MessageList, type MessageData } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { CitationPopover } from "./CitationPopover";
import { EmptyState } from "./EmptyState";
import { ReindexButton } from "./ReindexButton";

const NO_RESULTS_TEXT =
  "I couldn't find relevant information in the provided files. Try rephrasing your question or check if the right files were indexed.";

interface ChatViewProps {
  sessionId: string;
  fileList: Array<{ file_id: string; file_name: string; indexed_at: string }>;
  folderId?: string;
  indexedSources?: IndexedSource[];
  initialMessages?: MessageData[];
  onFileReindexed?: (fileId: string, indexedAt: string) => void;
  onReindexFolder?: () => void;
}

export function ChatView({
  sessionId,
  fileList,
  folderId,
  indexedSources = [],
  initialMessages = [],
  onFileReindexed,
  onReindexFolder,
}: ChatViewProps) {
  const [prefill, setPrefill] = useState("");
  const [messages, setMessages] = useState<MessageData[]>(initialMessages);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);
  const [activeCitation, setActiveCitation] = useState<{
    citation: Citation;
    anchorEl: HTMLElement;
  } | null>(null);

  // Track current streaming message content, citations, and stale files
  const pendingContentRef = useRef("");
  const pendingCitationsRef = useRef<Citation[]>([]);
  const pendingStaleFilesRef = useRef<StalenessInfo[]>([]);

  // Load messages from IndexedDB on mount
  useEffect(() => {
    loadMessages(sessionId).then((stored) => {
      if (stored.length > 0) {
        setMessages(
          stored.map((m) => ({
            role: m.role,
            content: m.content,
            citations: (m.citations ?? []) as Citation[],
            staleFiles: m.stale_files,
            isStreaming: false,
            isNoResults: false,
          }))
        );
      }
    });
  }, [sessionId]);

  // Re-index hook
  const { reindex, isReindexing, isFileReindexing } = useReindex({
    onSuccess(fileId, indexedAt) {
      // Find the file name from stale files in messages
      const fileName = messages
        .flatMap((m) => m.staleFiles ?? [])
        .find((f) => f.file_id === fileId)?.file_name;
      toast.success(`Re-indexed ${fileName || "file"} successfully`, { duration: 3000 });
      // Remove reindexed file from staleness banners
      setMessages((prev) =>
        prev.map((m) => {
          if (!m.staleFiles?.length) return m;
          const filtered = m.staleFiles.filter((f) => f.file_id !== fileId);
          return { ...m, staleFiles: filtered };
        })
      );
      // Update indexed_at so next staleness check uses new timestamp
      onFileReindexed?.(fileId, indexedAt);
    },
    onError(error) {
      toast.error(`Re-index failed: ${error}`, { duration: 5000 });
    },
  });

  const { sendMessage, isStreaming, abort } = useStream({
    onToken(content) {
      pendingContentRef.current += content;
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
    onStaleness(files) {
      pendingStaleFilesRef.current = files;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { ...last, staleFiles: files }];
        }
        return prev;
      });
    },
    onNewFiles(files) {
      const names = files.map((f) => f.file_name).join(", ");
      toast.info(
        `${files.length} new file${files.length > 1 ? "s" : ""} in folder: ${names}`,
        {
          duration: 10000,
          action: onReindexFolder
            ? { label: "Re-index folder", onClick: onReindexFolder }
            : undefined,
        }
      );
    },
    onGrepInfo(files) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { ...last, grepInfo: files }];
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
      // Map error codes to user-friendly toasts
      if (message === "rate_limited") {
        toast.error("Too many requests. Please wait a moment.", { duration: 6000 });
        setRateLimited(true);
        setTimeout(() => setRateLimited(false), 10_000);
      } else if (message === "auth_expired") {
        toast.error("Session expired. Please sign in again.", { duration: 8000 });
        setNeedsAuth(true);
      } else if (message === "session_not_found") {
        toast.error("Chat data not found on server. Try re-indexing your files.", { duration: 6000 });
      } else if (message === "connection_lost") {
        toast.error("Connection lost. Check your network and try again.", { duration: 6000 });
      } else if (message.startsWith("server_error_")) {
        toast.error("Something went wrong. Please try again.", { duration: 5000 });
      } else {
        toast.error(message, { duration: 5000 });
      }

      // Clear streaming placeholder
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.isStreaming) {
          // Remove the empty streaming placeholder on error
          return prev.slice(0, -1);
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

      // Persist using ref — safe from StrictMode double-invocation
      const content = pendingContentRef.current;
      if (content) {
        saveMessage({
          session_id: sessionId,
          role: "assistant",
          content,
          citations: pendingCitationsRef.current,
          stale_files: pendingStaleFilesRef.current.length > 0
            ? pendingStaleFilesRef.current
            : undefined,
          created_at: new Date().toISOString(),
        });
      }
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

      pendingContentRef.current = "";
      pendingCitationsRef.current = [];
      pendingStaleFilesRef.current = [];
      // Get the last assistant message for conversation context
      const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && m.content);
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      sendMessage(sessionId, query, fileList, token, lastAssistant?.content, folderId);
    },
    [sessionId, fileList, folderId, sendMessage, messages]
  );

  const handleReindex = useCallback(
    (fileId: string) => {
      const token = sessionStorage.getItem("google_access_token");
      if (!token) {
        setNeedsAuth(true);
        return;
      }
      reindex(sessionId, fileId, token);
    },
    [sessionId, reindex]
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

  const renderReindexButton = useCallback(
    (info: StalenessInfo) => {
      // No reindex button for deleted files
      if (info.error === "not_found") return null;
      return (
        <ReindexButton
          fileId={info.file_id}
          isReindexing={isFileReindexing(info.file_id)}
          onReindex={() => handleReindex(info.file_id)}
        />
      );
    },
    [isFileReindexing, handleReindex]
  );

  const showEmptyState = messages.length === 0 && indexedSources.length > 0;

  // Send button disabled during streaming, reindexing, or rate limit
  const isSendDisabled = isStreaming || isReindexing || rateLimited;

  return (
    <div className="flex flex-col h-full">
      {needsAuth && (
        <div className="mx-4 mt-2 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          Your session has expired. Please sign in again to send messages.
        </div>
      )}
      {showEmptyState ? (
        <EmptyState
          indexedSources={indexedSources}
          onSuggestionClick={(query) => setPrefill(query)}
        />
      ) : (
        <MessageList
          messages={messages}
          sessionId={sessionId}
          onCitationClick={handleCitationClick}
          renderReindexButton={renderReindexButton}
        />
      )}
      <ChatInput
        isStreaming={isSendDisabled}
        onSend={handleSend}
        onStop={abort}
        prefill={prefill}
        disabledTooltip={
          rateLimited
            ? "Rate limited -- please wait"
            : isReindexing
              ? "Re-indexing in progress"
              : undefined
        }
      />
      <CitationPopover
        citation={activeCitation?.citation ?? null}
        anchorEl={activeCitation?.anchorEl ?? null}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
}
