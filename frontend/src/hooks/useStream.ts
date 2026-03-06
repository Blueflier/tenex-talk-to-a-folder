import { useCallback, useRef, useState } from "react";
import type { Citation } from "@/lib/citations";
import type { StalenessInfo } from "@/components/chat/StalenessBanner";

const API_BASE = import.meta.env.VITE_API_URL;

export interface UseStreamCallbacks {
  onToken: (content: string) => void;
  onCitations: (citations: Citation[]) => void;
  onStaleness?: (files: StalenessInfo[]) => void;
  onNoResults: () => void;
  onError: (message: string) => void;
  onDone: () => void;
}

export function useStream(callbacks: UseStreamCallbacks) {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;
  const currentStaleFilesRef = useRef<StalenessInfo[]>([]);

  const abort = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (
      sessionId: string,
      query: string,
      fileList: string[],
      accessToken: string
    ) => {
      // Abort any in-flight request
      abortControllerRef.current?.abort();
      currentStaleFilesRef.current = [];

      const controller = new AbortController();
      abortControllerRef.current = controller;
      setIsStreaming(true);

      try {
        const response = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            session_id: sessionId,
            query,
            file_list: fileList,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          if (response.status === 429) {
            callbacksRef.current.onError("rate_limited");
            setIsStreaming(false);
            return;
          }
          if (response.status === 401 || response.status === 403) {
            callbacksRef.current.onError("auth_expired");
            setIsStreaming(false);
            return;
          }
          if (response.status === 404) {
            callbacksRef.current.onError("session_not_found");
            setIsStreaming(false);
            return;
          }
          callbacksRef.current.onError(`server_error_${response.status}`);
          setIsStreaming(false);
          return;
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || ""; // keep incomplete line in buffer

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (raw === "[DONE]") {
              callbacksRef.current.onDone();
              setIsStreaming(false);
              return;
            }

            try {
              const event = JSON.parse(raw) as {
                type: string;
                content?: string;
                citations?: Citation[];
                files?: StalenessInfo[];
                message?: string;
              };

              switch (event.type) {
                case "token":
                  if (event.content) callbacksRef.current.onToken(event.content);
                  break;
                case "citations":
                  if (event.citations)
                    callbacksRef.current.onCitations(event.citations);
                  break;
                case "staleness":
                  if (event.files) {
                    currentStaleFilesRef.current = event.files;
                    callbacksRef.current.onStaleness?.(event.files);
                  }
                  break;
                case "no_results":
                  callbacksRef.current.onNoResults();
                  break;
                case "error":
                  callbacksRef.current.onError(event.message ?? "Unknown error");
                  break;
              }
            } catch {
              // Skip malformed JSON lines
            }
          }
        }

        // Stream ended without [DONE] — treat as done
        callbacksRef.current.onDone();
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // User aborted — not an error
        } else {
          callbacksRef.current.onError("connection_lost");
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    []
  );

  return { sendMessage, isStreaming, abort, currentStaleFilesRef };
}
