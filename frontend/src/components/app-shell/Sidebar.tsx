import { Plus } from "lucide-react";
import type { Chat } from "@/lib/db";
import { Button } from "@/components/ui/button";
import { SidebarItem } from "./SidebarItem";

interface SidebarProps {
  chats: Chat[];
  selectedSessionId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}

export function Sidebar({
  chats,
  selectedSessionId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: SidebarProps) {
  return (
    <div className="w-64 border-r bg-muted/30 p-4 flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground">
          Chat History
        </h2>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onCreate}
          aria-label="New chat"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      {chats.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Paste a Drive link to start
        </p>
      ) : (
        <ul className="space-y-1 flex-1 overflow-y-auto">
          {chats.map((chat) => (
            <SidebarItem
              key={chat.session_id}
              chat={chat}
              isActive={chat.session_id === selectedSessionId}
              onSelect={() => onSelect(chat.session_id)}
              onRename={(title) => onRename(chat.session_id, title)}
              onDelete={() => onDelete(chat.session_id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
