import { X } from "lucide-react";
import type { Chat } from "@/lib/db";

interface DuplicateNoticeProps {
  matchingChat: Chat;
  onOpenChat: () => void;
  onReindexHere: () => void;
  onDismiss: () => void;
}

export function DuplicateNotice({
  matchingChat,
  onOpenChat,
  onReindexHere,
  onDismiss,
}: DuplicateNoticeProps) {
  return (
    <div className="relative mx-4 mb-3 rounded-lg border border-amber-300 bg-amber-50 dark:border-amber-600 dark:bg-amber-950/40 p-3">
      <button
        type="button"
        onClick={onDismiss}
        className="absolute top-2 right-2 text-amber-600 dark:text-amber-400 hover:opacity-70"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>

      <p className="text-sm text-amber-800 dark:text-amber-200 pr-6">
        These files are already indexed in &lsquo;{matchingChat.title}&rsquo;
      </p>

      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={onOpenChat}
          className="rounded-md border border-amber-400 dark:border-amber-600 px-3 py-1 text-xs font-medium text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors"
        >
          Open that chat
        </button>
        <button
          type="button"
          onClick={onReindexHere}
          className="rounded-md bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700 transition-colors"
        >
          Re-index here
        </button>
      </div>
    </div>
  );
}
