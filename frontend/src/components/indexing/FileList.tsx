import { useState } from "react";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  MinusCircle,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
} from "lucide-react";

export interface FileStatus {
  file_id: string;
  file_name: string;
  status: "extracting" | "done" | "skipped" | "failed";
  chunk_count?: number;
  reason?: string;
  error?: string;
  warning?: string;
}

interface FileListProps {
  files: FileStatus[];
}

const statusConfig = {
  extracting: {
    icon: Loader2,
    className: "text-blue-500 animate-spin",
    label: "Extracting",
  },
  done: {
    icon: CheckCircle2,
    className: "text-green-500",
    label: "Done",
  },
  skipped: {
    icon: MinusCircle,
    className: "text-zinc-400",
    label: "Skipped",
  },
  failed: {
    icon: XCircle,
    className: "text-red-500",
    label: "Failed",
  },
} as const;

export function FileList({ files }: FileListProps) {
  const [skippedExpanded, setSkippedExpanded] = useState(false);

  const activeFiles = files.filter(
    (f) => f.status !== "skipped"
  );
  const skippedFiles = files.filter((f) => f.status === "skipped");

  return (
    <div className="space-y-1" data-testid="file-list">
      {activeFiles.map((file) => {
        const config = statusConfig[file.status];
        const Icon = config.icon;
        return (
          <div
            key={file.file_id}
            className="flex items-center gap-2 py-1.5 px-2 rounded text-sm"
            data-testid={`file-${file.file_id}`}
          >
            <Icon className={`w-4 h-4 shrink-0 ${config.className}`} />
            <span className="truncate flex-1">{file.file_name}</span>
            {file.status === "done" && file.chunk_count != null && (
              <span className="text-xs text-muted-foreground">
                {file.chunk_count} chunks
              </span>
            )}
            {file.status === "failed" && file.error && (
              <span className="text-xs text-red-500 truncate max-w-[200px]">
                {file.error}
              </span>
            )}
            {file.warning && (
              <span className="flex items-center gap-1 text-xs text-amber-500">
                <AlertTriangle className="w-3 h-3" />
                {file.warning}
              </span>
            )}
          </div>
        );
      })}

      {skippedFiles.length > 0 && (
        <div className="mt-2 border-t pt-2">
          <button
            type="button"
            onClick={() => setSkippedExpanded(!skippedExpanded)}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-full"
            data-testid="skipped-toggle"
          >
            {skippedExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            {skippedFiles.length} file{skippedFiles.length !== 1 ? "s" : ""}{" "}
            skipped (unsupported types)
          </button>
          {skippedExpanded && (
            <div className="ml-5 mt-1 space-y-1">
              {skippedFiles.map((file) => (
                <div
                  key={file.file_id}
                  className="flex items-center gap-2 py-1 text-sm text-muted-foreground"
                >
                  <MinusCircle className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                  <span className="truncate">{file.file_name}</span>
                  {file.reason && (
                    <span className="text-xs italic">{file.reason}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
