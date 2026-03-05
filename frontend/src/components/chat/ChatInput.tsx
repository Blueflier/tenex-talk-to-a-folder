import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useAutoResize } from "@/hooks/useAutoResize";

interface ChatInputProps {
  isStreaming: boolean;
  onSend: (message: string) => void;
  onStop: () => void;
  /** When set, overrides the input value (for suggestion auto-fill). */
  prefill?: string;
}

export function ChatInput({ isStreaming, onSend, onStop, prefill }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync prefill into value when it changes
  useEffect(() => {
    if (prefill !== undefined && prefill !== "") {
      setValue(prefill);
      textareaRef.current?.focus();
    }
  }, [prefill]);
  const resize = useAutoResize(textareaRef);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
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
            resize();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your files..."
          disabled={isStreaming}
          rows={1}
          className="min-h-[40px] max-h-[200px] resize-none pr-12"
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
              disabled={!value.trim()}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-800 dark:bg-zinc-200 text-white dark:text-zinc-800 hover:opacity-80 transition-opacity disabled:opacity-40"
              aria-label="Send message"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
