import { useEffect, useRef, useState, type KeyboardEvent, type ClipboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResize } from "@/hooks/useAutoResize";
import { isValidDriveUrl } from "@/lib/drive";

interface ChatInputProps {
  isStreaming: boolean;
  onSend: (message: string) => void;
  onStop: () => void;
  /** When set, overrides the input value (for suggestion auto-fill). */
  prefill?: string;
  /** Tooltip shown on disabled send button (e.g. during re-indexing). */
  disabledTooltip?: string;
  /** Called when a valid Drive URL is detected (paste or submit). */
  onDriveLink?: (url: string) => void;
  /** Additional disabled state (e.g. during indexing). */
  disabled?: boolean;
  /** Override the default placeholder text. */
  placeholder?: string;
}

export function ChatInput({
  isStreaming,
  onSend,
  onStop,
  prefill,
  disabledTooltip,
  onDriveLink,
  disabled = false,
  placeholder = "Ask about your files...",
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [driveError, setDriveError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync prefill into value when it changes
  useEffect(() => {
    if (prefill !== undefined && prefill !== "") {
      setValue(prefill);
      textareaRef.current?.focus();
    }
  }, [prefill]);
  const resize = useAutoResize(textareaRef);

  const isDisabled = isStreaming || disabled;

  const checkDriveLink = (text: string): boolean => {
    if (!onDriveLink) return false;
    const trimmed = text.trim();
    if (trimmed.includes("drive.google.com")) {
      if (isValidDriveUrl(trimmed)) {
        setDriveError("");
        onDriveLink(trimmed);
        setValue("");
        return true;
      } else {
        setDriveError("Invalid Google Drive link. Please paste a valid folder or file URL.");
        return true;
      }
    }
    return false;
  };

  const handlePaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const pasted = e.clipboardData.getData("text");
    if (checkDriveLink(pasted)) {
      e.preventDefault();
    }
  };

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isDisabled) return;

    // Check if it's a Drive link first
    if (checkDriveLink(trimmed)) return;

    setDriveError("");
    onSend(trimmed);
    setValue("");
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-background px-4 py-3">
      <div className="relative flex items-end gap-2 max-w-3xl mx-auto">
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setDriveError("");
            resize();
          }}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={placeholder}
          disabled={isDisabled}
          rows={1}
          className="min-h-[40px] max-h-[200px] resize-none pr-12"
          data-testid="chat-input"
        />
        <div className="absolute right-2 bottom-2">
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-800 dark:bg-zinc-200 text-white dark:text-zinc-800 hover:opacity-80 transition-opacity"
              aria-label="Stop generating"
            >
              <Square className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!value.trim() || isDisabled}
              title={isDisabled && disabledTooltip ? disabledTooltip : undefined}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-800 dark:bg-zinc-200 text-white dark:text-zinc-800 hover:opacity-80 transition-opacity disabled:opacity-40"
              aria-label="Send message"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      {driveError && (
        <p className="text-sm text-red-500 mt-1 max-w-3xl mx-auto" data-testid="drive-error">
          {driveError}
        </p>
      )}
    </div>
  );
}
