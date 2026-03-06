import { useRef, useState } from "react";
import { MoreVertical, Pencil, Trash2 } from "lucide-react";
import type { Chat } from "@/lib/db";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

interface SidebarItemProps {
  chat: Chat;
  isActive: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}

export function SidebarItem({
  chat,
  isActive,
  onSelect,
  onRename,
  onDelete,
}: SidebarItemProps) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(chat.title);
  const [menuOpen, setMenuOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function startRename() {
    setMenuOpen(false);
    setDraft(chat.title);
    setRenaming(true);
    // Focus after render
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commitRename() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== chat.title) {
      onRename(trimmed);
    }
    setRenaming(false);
  }

  function handleDelete() {
    setMenuOpen(false);
    onDelete();
  }

  if (renaming) {
    return (
      <li className="px-2 py-1">
        <input
          ref={inputRef}
          className="w-full text-sm bg-background border rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-ring"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") setRenaming(false);
          }}
          onBlur={commitRename}
          autoFocus
        />
      </li>
    );
  }

  return (
    <li
      className={`group flex items-center gap-1 truncate text-sm px-2 py-1 rounded cursor-pointer ${
        isActive ? "bg-muted" : "hover:bg-muted/60"
      }`}
      onClick={onSelect}
    >
      <span className="flex-1 truncate">{chat.title}</span>

      <Popover open={menuOpen} onOpenChange={setMenuOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 opacity-0 group-hover:opacity-100 shrink-0"
            onClick={(e) => e.stopPropagation()}
            aria-label="Chat options"
          >
            <MoreVertical className="h-3 w-3" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-36 p-1"
          align="start"
          side="right"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted"
            onClick={startRename}
          >
            <Pencil className="h-3 w-3" /> Rename
          </button>
          <button
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-red-600 hover:bg-muted"
            onClick={handleDelete}
          >
            <Trash2 className="h-3 w-3" /> Delete
          </button>
        </PopoverContent>
      </Popover>
    </li>
  );
}
