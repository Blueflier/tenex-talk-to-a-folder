import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  getChats,
  saveChat,
  updateChatTitle,
  deleteChat,
  deleteMessages,
  type Chat,
} from "@/lib/db";
import { FolderOpen } from "lucide-react";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatView } from "@/components/chat/ChatView";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { IndexingModal } from "@/components/indexing/IndexingModal";
import { Sidebar } from "./Sidebar";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import { DuplicateNotice } from "./DuplicateNotice";
import { resolveDriveFileIds } from "@/lib/drive";

interface IndexedFile {
  file_id: string;
  file_name: string;
}

interface AppShellProps {
  token: string;
}

export function AppShell({ token }: AppShellProps) {
  const [loading, setLoading] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);

  // Multi-session state
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null
  );
  const [indexedFilesMap, setIndexedFilesMap] = useState<
    Map<string, IndexedFile[]>
  >(new Map());
  const [totalChunksMap, setTotalChunksMap] = useState<Map<string, number>>(
    new Map()
  );

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<Chat | null>(null);

  // Stream abort ref -- set by ChatView via callback
  const abortRef = useRef<(() => void) | null>(null);

  // Indexing state
  const [driveUrl, setDriveUrl] = useState("");
  const [indexingOpen, setIndexingOpen] = useState(false);

  // Duplicate detection state
  const [duplicateInfo, setDuplicateInfo] = useState<{
    matchingChat: Chat;
    driveUrl: string;
  } | null>(null);

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const loaded = await getChats();
        setChats(loaded);
        if (loaded.length > 0) {
          setSelectedSessionId(loaded[0].session_id);
        }
      } catch {
        // IndexedDB may not be available, continue with empty state
      } finally {
        setLoading(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, []);

  // Session switching
  const handleSelect = useCallback((id: string) => {
    abortRef.current?.();
    setSelectedSessionId(id);
  }, []);

  // New chat
  const handleCreate = useCallback(async () => {
    const id = crypto.randomUUID();
    const newChat: Chat = {
      session_id: id,
      title: "New Chat",
      created_at: new Date().toISOString(),
      last_message_at: new Date().toISOString(),
      indexed_sources: [],
    };
    await saveChat(newChat);
    setChats((prev) => [newChat, ...prev]);
    abortRef.current?.();
    setSelectedSessionId(id);
  }, []);

  // Rename
  const handleRename = useCallback(
    async (id: string, newTitle: string) => {
      await updateChatTitle(id, newTitle);
      setChats((prev) =>
        prev.map((c) => (c.session_id === id ? { ...c, title: newTitle } : c))
      );
    },
    []
  );

  // Delete -- show dialog
  const handleDeleteRequest = useCallback(
    (id: string) => {
      const chat = chats.find((c) => c.session_id === id);
      if (chat) setDeleteTarget(chat);
    },
    [chats]
  );

  // Delete -- confirm
  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.session_id;

    // Abort stream if active on this session
    if (selectedSessionId === id) {
      abortRef.current?.();
    }

    await deleteChat(id);
    await deleteMessages(id);

    setChats((prev) => {
      const remaining = prev.filter((c) => c.session_id !== id);
      // If deleted session was selected, pick first remaining or null
      if (selectedSessionId === id) {
        setSelectedSessionId(remaining.length > 0 ? remaining[0].session_id : null);
      }
      return remaining;
    });

    // Clean up maps
    setIndexedFilesMap((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
    setTotalChunksMap((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });

    setDeleteTarget(null);
  }, [deleteTarget, selectedSessionId]);

  const handleDriveLink = useCallback(
    async (url: string) => {
      // Ensure a session exists
      let currentSessionId = selectedSessionId;
      if (!currentSessionId) {
        const id = crypto.randomUUID();
        const newChat: Chat = {
          session_id: id,
          title: "New Chat",
          created_at: new Date().toISOString(),
          last_message_at: new Date().toISOString(),
          indexed_sources: [],
        };
        await saveChat(newChat);
        setChats((prev) => [newChat, ...prev]);
        setSelectedSessionId(id);
        currentSessionId = id;
      }

      // Resolve file IDs for duplicate detection
      const resolvedIds = await resolveDriveFileIds(url, token);

      if (resolvedIds.length > 0) {
        // Check all chats for overlapping indexed_sources
        for (const chat of chats) {
          if (chat.indexed_sources.length === 0) continue;
          const overlap = resolvedIds.filter((id) =>
            chat.indexed_sources.includes(id)
          );
          if (overlap.length === 0) continue;

          const isFullOverlap = overlap.length === resolvedIds.length;

          // Same-session match
          if (chat.session_id === currentSessionId) {
            toast.warning("These files are already indexed in this chat", {
              duration: 5000,
            });
            return;
          }

          // Different-session full match
          if (isFullOverlap) {
            setDuplicateInfo({ matchingChat: chat, driveUrl: url });
            return;
          }

          // Partial overlap -- inform and proceed
          toast("Some files overlap with another chat. Indexing all files.", {
            duration: 5000,
          });
          break;
        }
      }

      // No match or partial -- proceed with indexing
      setDriveUrl(url);
      setIndexingOpen(true);
    },
    [selectedSessionId, token, chats]
  );

  const handleIndexComplete = useCallback(
    (result: {
      filesIndexed: number;
      totalChunks: number;
      indexedSources: IndexedFile[];
    }) => {
      setIndexingOpen(false);
      setDriveUrl("");

      if (!selectedSessionId) return;

      // Update maps
      setIndexedFilesMap((prev) => {
        const next = new Map(prev);
        const existing = next.get(selectedSessionId) || [];
        next.set(selectedSessionId, [...existing, ...result.indexedSources]);
        return next;
      });
      setTotalChunksMap((prev) => {
        const next = new Map(prev);
        const existing = next.get(selectedSessionId) || 0;
        next.set(selectedSessionId, existing + result.totalChunks);
        return next;
      });

      // Set title to first source name
      const firstName =
        result.indexedSources[0]?.file_name || "Untitled";
      updateChatTitle(selectedSessionId, firstName);
      setChats((prev) =>
        prev.map((c) =>
          c.session_id === selectedSessionId
            ? {
                ...c,
                title: firstName,
                indexed_sources: [
                  ...c.indexed_sources,
                  ...result.indexedSources.map((f) => f.file_id),
                ],
              }
            : c
        )
      );
    },
    [selectedSessionId]
  );

  const handleIndexCancel = useCallback(() => {
    setIndexingOpen(false);
    setDriveUrl("");
  }, []);

  const handleIndexError = useCallback((message: string) => {
    setIndexingOpen(false);
    setDriveUrl("");
    toast.error(message);
  }, []);

  // Derive per-session data
  const indexedFiles = selectedSessionId
    ? indexedFilesMap.get(selectedSessionId) || []
    : [];
  const totalChunks = selectedSessionId
    ? totalChunksMap.get(selectedSessionId) || 0
    : 0;
  const isIndexed = indexedFiles.length > 0;
  const fileNames = indexedFiles.map((f) => f.file_name);
  const fileList = indexedFiles.map((f) => f.file_id);

  if (loading) {
    return (
      <div className="flex h-screen">
        <div className="w-64 border-r bg-muted/30 p-4">
          <div className="space-y-3">
            <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
          </div>
        </div>
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
      {/* Sidebar */}
      <Sidebar
        chats={chats}
        selectedSessionId={selectedSessionId}
        onSelect={handleSelect}
        onCreate={handleCreate}
        onRename={handleRename}
        onDelete={handleDeleteRequest}
      />

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Duplicate notice */}
        {duplicateInfo && (
          <DuplicateNotice
            matchingChat={duplicateInfo.matchingChat}
            onOpenChat={() => {
              setSelectedSessionId(duplicateInfo.matchingChat.session_id);
              setDuplicateInfo(null);
            }}
            onReindexHere={() => {
              setDriveUrl(duplicateInfo.driveUrl);
              setIndexingOpen(true);
              setDuplicateInfo(null);
            }}
            onDismiss={() => setDuplicateInfo(null)}
          />
        )}

        {selectedSessionId && isIndexed ? (
          <>
            <ChatHeader
              filesIndexed={indexedFiles.length}
              totalChunks={totalChunks}
              fileNames={fileNames}
            />
            <ChatView
              key={selectedSessionId}
              sessionId={selectedSessionId}
              fileList={fileList}
              indexedSources={[
                {
                  source_id: selectedSessionId,
                  file_list: indexedFiles.map((f) => ({ name: f.file_name })),
                },
              ]}
            />
          </>
        ) : (
          <>
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <FolderOpen className="mx-auto h-12 w-12 mb-4 opacity-50" />
                <p className="text-lg font-medium">
                  Paste a Google Drive link to get started
                </p>
                <p className="text-sm mt-1">
                  We&apos;ll index your files so you can ask questions about
                  them.
                </p>
              </div>
            </div>
            <ChatInput
              isStreaming={false}
              onSend={() => {}}
              onStop={() => {}}
              onDriveLink={handleDriveLink}
              disabled={indexingOpen}
              placeholder="Paste a Google Drive folder link..."
            />
          </>
        )}
      </div>

      {/* Indexing modal */}
      {selectedSessionId && (
        <IndexingModal
          open={indexingOpen}
          driveUrl={driveUrl}
          sessionId={selectedSessionId}
          token={token}
          onComplete={handleIndexComplete}
          onCancel={handleIndexCancel}
          onError={handleIndexError}
        />
      )}

      {/* Delete confirmation */}
      <DeleteConfirmDialog
        open={deleteTarget !== null}
        chatTitle={deleteTarget?.title || ""}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
