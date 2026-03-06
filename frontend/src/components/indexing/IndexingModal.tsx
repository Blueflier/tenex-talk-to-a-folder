import { useEffect, useRef, useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { FileList, type FileStatus } from "./FileList";
import { EmbeddingProgress } from "./EmbeddingProgress";
import { streamIndex } from "@/lib/api";
import { parseSSE } from "@/lib/sse";
import { CheckCircle2, AlertCircle } from "lucide-react";

type ModalState = "extracting" | "embedding" | "success" | "error";

interface IndexingResult {
  filesIndexed: number;
  totalChunks: number;
  indexedSources: Array<{ file_id: string; file_name: string; indexed_at: string }>;
}

interface IndexingModalProps {
  open: boolean;
  driveUrl: string;
  sessionId: string;
  token: string;
  onComplete: (result: IndexingResult) => void;
  onCancel: () => void;
  onError: (message: string) => void;
}

export function IndexingModal({
  open,
  driveUrl,
  sessionId,
  token,
  onComplete,
  onCancel,
  onError,
}: IndexingModalProps) {
  const [state, setState] = useState<ModalState>("extracting");
  const [files, setFiles] = useState<FileStatus[]>([]);
  const [embedded, setEmbedded] = useState(0);
  const [totalChunks, setTotalChunks] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  const reset = useCallback(() => {
    setState("extracting");
    setFiles([]);
    setEmbedded(0);
    setTotalChunks(0);
    setErrorMessage("");
  }, []);

  useEffect(() => {
    if (!open || !driveUrl) return;

    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        if (controller.signal.aborted) return;
        const response = await streamIndex(
          driveUrl,
          sessionId,
          token,
          controller.signal
        );

        for await (const event of parseSSE(response)) {
          if (controller.signal.aborted) return;

          switch (event.event) {
            case "extraction": {
              const data = JSON.parse(event.data) as {
                file_id: string;
                file_name: string;
                status: FileStatus["status"];
                chunk_count?: number;
                reason?: string;
                error?: string;
              };
              setFiles((prev) => {
                const existing = prev.findIndex(
                  (f) => f.file_id === data.file_id
                );
                if (existing >= 0) {
                  const updated = [...prev];
                  updated[existing] = { ...updated[existing], ...data };
                  return updated;
                }
                return [...prev, data];
              });
              break;
            }

            case "warning": {
              const data = JSON.parse(event.data) as {
                file_id: string;
                file_name: string;
                message: string;
              };
              setFiles((prev) =>
                prev.map((f) =>
                  f.file_id === data.file_id
                    ? { ...f, warning: data.message }
                    : f
                )
              );
              break;
            }

            case "embedding_start": {
              const data = JSON.parse(event.data) as { total_chunks: number };
              setState("embedding");
              setTotalChunks(data.total_chunks);
              setEmbedded(0);
              break;
            }

            case "embedding_progress": {
              const data = JSON.parse(event.data) as {
                embedded: number;
                total: number;
              };
              setEmbedded(data.embedded);
              setTotalChunks(data.total);
              break;
            }

            case "complete": {
              const data = JSON.parse(event.data) as {
                files_indexed: number;
                total_chunks: number;
                indexed_at: string;
                skipped_files?: Array<{
                  file_id: string;
                  file_name: string;
                  reason: string;
                }>;
              };

              if (data.files_indexed === 0) {
                onErrorRef.current("No files were successfully indexed");
                reset();
                return;
              }

              setState("success");
              setTotalChunks(data.total_chunks);

              // Auto-dismiss after 1.5s
              setTimeout(() => {
                // Collect indexed file sources from the files state
                let indexedSources: IndexingResult["indexedSources"] = [];
                setFiles((currentFiles) => {
                  indexedSources = currentFiles
                    .filter((f) => f.status === "done")
                    .map((f) => ({
                      file_id: f.file_id,
                      file_name: f.file_name,
                      indexed_at: data.indexed_at,
                    }));
                  return currentFiles;
                });
                // Defer onComplete to avoid setState-during-render
                queueMicrotask(() => {
                  onCompleteRef.current({
                    filesIndexed: data.files_indexed,
                    totalChunks: data.total_chunks,
                    indexedSources,
                  });
                  reset();
                });
              }, 1500);
              break;
            }

            case "error": {
              const data = JSON.parse(event.data) as {
                message: string;
                code?: "empty_folder" | "no_supported_files";
              };
              setState("error");
              if (data.code === "empty_folder") {
                setErrorMessage("This folder is empty");
              } else if (data.code === "no_supported_files") {
                setErrorMessage("No supported file types found");
              } else {
                setErrorMessage(data.message);
              }
              break;
            }
          }
        }
      } catch (err: unknown) {
        if (controller.signal.aborted) return;
        setState("error");
        setErrorMessage(
          err instanceof Error ? err.message : "An unexpected error occurred"
        );
      }
    })();

    return () => {
      controller.abort();
    };
  }, [open, driveUrl, sessionId, token, reset]);

  const handleCancel = () => {
    abortRef.current?.abort();
    reset();
    onCancel();
  };

  const handleCloseError = () => {
    reset();
    onError(errorMessage);
  };

  const filesIndexedCount = files.filter((f) => f.status === "done").length;

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent showCloseButton={false} data-testid="indexing-modal">
        <DialogHeader>
          <DialogTitle>
            {state === "extracting" && "Extracting files..."}
            {state === "embedding" && "Embedding content..."}
            {state === "success" && "Indexing complete"}
            {state === "error" && "Indexing failed"}
          </DialogTitle>
          <DialogDescription>
            {state === "extracting" &&
              "Reading files from Google Drive"}
            {state === "embedding" &&
              "Creating searchable embeddings"}
            {state === "success" &&
              `Indexed ${filesIndexedCount} files (${totalChunks} chunks)`}
            {state === "error" && errorMessage}
          </DialogDescription>
        </DialogHeader>

        <div className="py-2">
          {state === "extracting" && <FileList files={files} />}

          {state === "embedding" && (
            <EmbeddingProgress embedded={embedded} total={totalChunks} />
          )}

          {state === "success" && (
            <div className="flex items-center gap-2 text-green-600 justify-center py-4">
              <CheckCircle2 className="w-6 h-6" />
              <span className="font-medium">
                Indexed {filesIndexedCount} files ({totalChunks} chunks)
              </span>
            </div>
          )}

          {state === "error" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-red-600 justify-center py-4">
                <AlertCircle className="w-6 h-6" />
                <span className="font-medium">{errorMessage}</span>
              </div>
              {/* Show skipped files if error is no_supported_files */}
              {files.filter((f) => f.status === "skipped").length > 0 && (
                <FileList files={files} />
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          {(state === "extracting" || state === "embedding") && (
            <Button variant="outline" onClick={handleCancel} data-testid="cancel-btn">
              Cancel
            </Button>
          )}
          {state === "error" && (
            <Button variant="outline" onClick={handleCloseError} data-testid="close-btn">
              Close
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
