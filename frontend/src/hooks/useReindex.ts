import { useCallback, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL;

interface UseReindexOptions {
  onSuccess?: (fileId: string, indexedAt: string) => void;
  onError?: (error: string) => void;
}

export function useReindex({ onSuccess, onError }: UseReindexOptions = {}) {
  const [reindexingFiles, setReindexingFiles] = useState<Set<string>>(
    new Set()
  );

  const reindex = useCallback(
    async (sessionId: string, fileId: string, accessToken: string) => {
      setReindexingFiles((prev) => new Set(prev).add(fileId));

      try {
        const response = await fetch(`${API_BASE}/reindex`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            session_id: sessionId,
            file_id: fileId,
          }),
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(`Reindex failed: ${response.status} ${text}`);
        }

        const data = (await response.json()) as {
          file_id: string;
          indexed_at: string;
        };
        onSuccess?.(data.file_id, data.indexed_at);
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Reindex failed");
      } finally {
        setReindexingFiles((prev) => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      }
    },
    [onSuccess, onError]
  );

  const isReindexing = reindexingFiles.size > 0;
  const isFileReindexing = useCallback(
    (fileId: string) => reindexingFiles.has(fileId),
    [reindexingFiles]
  );

  return { reindex, isReindexing, isFileReindexing, reindexingFiles };
}
