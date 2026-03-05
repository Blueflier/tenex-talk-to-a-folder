import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getChats, type Chat } from "@/lib/db";
import { FolderOpen } from "lucide-react";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatView } from "@/components/chat/ChatView";
import { ChatHeader, buildPlaceholder } from "@/components/chat/ChatHeader";
import { IndexingModal } from "@/components/indexing/IndexingModal";

interface IndexedFile {
  file_id: string;
  file_name: string;
}

export function AppShell() {
  const [loading, setLoading] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);

  // Indexing state
  const [driveUrl, setDriveUrl] = useState("");
  const [indexingOpen, setIndexingOpen] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [indexedFiles, setIndexedFiles] = useState<IndexedFile[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);

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

  const handleDriveLink = useCallback((url: string) => {
    setDriveUrl(url);
    setIndexingOpen(true);
  }, []);

  const handleIndexComplete = useCallback(
    (result: { filesIndexed: number; totalChunks: number; indexedSources: IndexedFile[] }) => {
      setIndexingOpen(false);
      setDriveUrl("");
      setIndexedFiles(result.indexedSources);
      setTotalChunks(result.totalChunks);
    },
    []
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

  const token = sessionStorage.getItem("google_access_token") ?? "";
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
      <div className="flex-1 flex flex-col">
        {isIndexed ? (
          <>
            <ChatHeader
              filesIndexed={indexedFiles.length}
              totalChunks={totalChunks}
              fileNames={fileNames}
            />
            <ChatView
              sessionId={sessionId}
              fileList={fileList}
              indexedSources={[{
                source_id: sessionId,
                file_list: indexedFiles.map((f) => ({ name: f.file_name })),
              }]}
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
      <IndexingModal
        open={indexingOpen}
        driveUrl={driveUrl}
        sessionId={sessionId}
        token={token}
        onComplete={handleIndexComplete}
        onCancel={handleIndexCancel}
        onError={handleIndexError}
      />
    </div>
  );
}
