import { useEffect, useState } from "react";
import { getChats, type Chat } from "@/lib/db";
import { FolderOpen } from "lucide-react";

export function AppShell() {
  const [loading, setLoading] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const loaded = await getChats();
        setChats(loaded);
      } catch {
        // IndexedDB may not be available, continue with empty state
      } finally {
        setLoading(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen">
        {/* Sidebar skeleton */}
        <div className="w-64 border-r bg-muted/30 p-4">
          <div className="space-y-3">
            <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
          </div>
        </div>
        {/* Main content skeleton */}
        <div className="flex-1 p-6">
          <div className="space-y-4">
            <div className="h-6 w-1/3 animate-pulse rounded bg-muted" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar placeholder */}
      <div className="w-64 border-r bg-muted/30 p-4">
        <h2 className="text-sm font-semibold text-muted-foreground mb-3">
          Chat History
        </h2>
        {chats.length === 0 ? (
          <p className="text-xs text-muted-foreground">No chats yet</p>
        ) : (
          <ul className="space-y-1">
            {chats.map((chat) => (
              <li
                key={chat.session_id}
                className="truncate text-sm px-2 py-1 rounded hover:bg-muted cursor-pointer"
              >
                {chat.title}
              </li>
            ))}
          </ul>
        )}
      </div>
      {/* Main content */}
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <FolderOpen className="mx-auto h-12 w-12 mb-4 opacity-50" />
          <p className="text-lg font-medium">
            Paste a Google Drive link to get started
          </p>
          <p className="text-sm mt-1">
            We'll index your files so you can ask questions about them.
          </p>
        </div>
      </div>
    </div>
  );
}
