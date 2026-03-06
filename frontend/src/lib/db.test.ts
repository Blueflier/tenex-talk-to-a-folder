import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import {
  openDB,
  saveChat,
  getChats,
  saveMessage,
  getMessages,
  loadMessages,
} from "./db";
import type { Chat, Message } from "./db";
import type { Citation } from "./citations";

describe("IndexedDB persistence layer", () => {
  beforeEach(() => {
    // Reset IndexedDB between tests
    indexedDB = new IDBFactory();
  });

  describe("openDB", () => {
    it("creates 'chats' store with session_id keyPath", async () => {
      const db = await openDB();
      expect(db.objectStoreNames.contains("chats")).toBe(true);
      const tx = db.transaction("chats", "readonly");
      const store = tx.objectStore("chats");
      expect(store.keyPath).toBe("session_id");
      db.close();
    });

    it("creates 'messages' store with autoIncrement", async () => {
      const db = await openDB();
      expect(db.objectStoreNames.contains("messages")).toBe(true);
      const tx = db.transaction("messages", "readonly");
      const store = tx.objectStore("messages");
      expect(store.autoIncrement).toBe(true);
      db.close();
    });

    it("'chats' store has last_message_at index", async () => {
      const db = await openDB();
      const tx = db.transaction("chats", "readonly");
      const store = tx.objectStore("chats");
      expect(store.indexNames.contains("last_message_at")).toBe(true);
      db.close();
    });

    it("'messages' store has session_id and created_at indexes", async () => {
      const db = await openDB();
      const tx = db.transaction("messages", "readonly");
      const store = tx.objectStore("messages");
      expect(store.indexNames.contains("session_id")).toBe(true);
      expect(store.indexNames.contains("created_at")).toBe(true);
      db.close();
    });
  });

  describe("CRUD operations", () => {
    it("saveChat + getChats roundtrip returns saved chat", async () => {
      const chat: Chat = {
        session_id: "test-session-1",
        title: "Test Chat",
        created_at: new Date().toISOString(),
        last_message_at: new Date().toISOString(),
        indexed_sources: ["file1.pdf"],
      };

      await saveChat(chat);
      const chats = await getChats();

      expect(chats).toHaveLength(1);
      expect(chats[0].session_id).toBe("test-session-1");
      expect(chats[0].title).toBe("Test Chat");
      expect(chats[0].indexed_sources).toEqual(["file1.pdf"]);
    });

    it("saveMessage + getMessages returns messages for that session only", async () => {
      const msg1: Message = {
        session_id: "session-a",
        role: "user",
        content: "Hello",
        citations: [],
        created_at: new Date().toISOString(),
      };
      const msg2: Message = {
        session_id: "session-b",
        role: "assistant",
        content: "World",
        citations: [],
        created_at: new Date().toISOString(),
      };
      const msg3: Message = {
        session_id: "session-a",
        role: "assistant",
        content: "Hi there",
        citations: [],
        created_at: new Date().toISOString(),
      };

      await saveMessage(msg1);
      await saveMessage(msg2);
      await saveMessage(msg3);

      const messagesA = await getMessages("session-a");
      expect(messagesA).toHaveLength(2);
      expect(messagesA.every((m) => m.session_id === "session-a")).toBe(true);

      const messagesB = await getMessages("session-b");
      expect(messagesB).toHaveLength(1);
      expect(messagesB[0].content).toBe("World");
    });

    it("saveMessage stores citations array as frozen snapshot", async () => {
      const citations: Citation[] = [
        {
          index: 1,
          file_name: "report.pdf",
          file_id: "f1",
          page_number: 7,
          chunk_text: "Relevant passage from page 7",
        },
        {
          index: 2,
          file_name: "data.csv",
          file_id: "f2",
          row_number: 12,
          chunk_text: "Row 12 data",
        },
      ];

      const msg: Message = {
        session_id: "cite-session",
        role: "assistant",
        content: "Here is the answer [1][2]",
        citations,
        created_at: new Date().toISOString(),
      };

      await saveMessage(msg);
      const loaded = await getMessages("cite-session");

      expect(loaded).toHaveLength(1);
      expect(loaded[0].citations).toHaveLength(2);
      expect((loaded[0].citations![0] as Record<string, unknown>).file_name).toBe("report.pdf");
      expect((loaded[0].citations![0] as Record<string, unknown>).page_number).toBe(7);
      expect((loaded[0].citations![1] as Record<string, unknown>).row_number).toBe(12);
    });

    it("loadMessages returns messages sorted by created_at ascending", async () => {
      const msgs: Message[] = [
        {
          session_id: "sorted-session",
          role: "user",
          content: "Third",
          citations: [],
          created_at: "2024-06-03T00:00:00Z",
        },
        {
          session_id: "sorted-session",
          role: "assistant",
          content: "First",
          citations: [],
          created_at: "2024-06-01T00:00:00Z",
        },
        {
          session_id: "sorted-session",
          role: "user",
          content: "Second",
          citations: [],
          created_at: "2024-06-02T00:00:00Z",
        },
      ];

      for (const m of msgs) await saveMessage(m);

      const loaded = await loadMessages("sorted-session");
      expect(loaded).toHaveLength(3);
      expect(loaded[0].content).toBe("First");
      expect(loaded[1].content).toBe("Second");
      expect(loaded[2].content).toBe("Third");
    });

    it("loadMessages works without any auth token in sessionStorage (PERS-04)", async () => {
      // Ensure no token exists
      sessionStorage.removeItem("google_access_token");

      const msg: Message = {
        session_id: "no-auth-session",
        role: "assistant",
        content: "Previous answer",
        citations: [],
        created_at: new Date().toISOString(),
      };

      await saveMessage(msg);

      // Should not throw — no auth check required
      const loaded = await loadMessages("no-auth-session");
      expect(loaded).toHaveLength(1);
      expect(loaded[0].content).toBe("Previous answer");
    });

    it("saveChat with indexed_files roundtrips correctly", async () => {
      const chat: Chat = {
        session_id: "hydrate-session",
        title: "Hydrate Test",
        created_at: "2024-01-01T00:00:00Z",
        last_message_at: "2024-01-01T00:00:00Z",
        indexed_sources: ["f1"],
        indexed_files: [
          { file_id: "f1", file_name: "Doc.gdoc", indexed_at: "2024-01-01T00:00:00Z" },
        ],
      };

      await saveChat(chat);
      const chats = await getChats();

      expect(chats).toHaveLength(1);
      expect(chats[0].indexed_files).toHaveLength(1);
      expect(chats[0].indexed_files![0].file_id).toBe("f1");
      expect(chats[0].indexed_files![0].file_name).toBe("Doc.gdoc");
      expect(chats[0].indexed_files![0].indexed_at).toBe("2024-01-01T00:00:00Z");
    });

    it("saveChat without indexed_files returns undefined for field (backward compat)", async () => {
      const chat: Chat = {
        session_id: "no-files-session",
        title: "No Files",
        created_at: "2024-01-01T00:00:00Z",
        last_message_at: "2024-01-01T00:00:00Z",
        indexed_sources: [],
      };

      await saveChat(chat);
      const chats = await getChats();

      expect(chats).toHaveLength(1);
      expect(chats[0].indexed_files).toBeUndefined();
    });

    it("getChats returns chats sorted by last_message_at descending", async () => {
      const chat1: Chat = {
        session_id: "old-chat",
        title: "Old Chat",
        created_at: "2024-01-01T00:00:00Z",
        last_message_at: "2024-01-01T00:00:00Z",
        indexed_sources: [],
      };
      const chat2: Chat = {
        session_id: "new-chat",
        title: "New Chat",
        created_at: "2024-06-01T00:00:00Z",
        last_message_at: "2024-06-01T00:00:00Z",
        indexed_sources: [],
      };
      const chat3: Chat = {
        session_id: "mid-chat",
        title: "Mid Chat",
        created_at: "2024-03-01T00:00:00Z",
        last_message_at: "2024-03-01T00:00:00Z",
        indexed_sources: [],
      };

      await saveChat(chat1);
      await saveChat(chat2);
      await saveChat(chat3);

      const chats = await getChats();
      expect(chats).toHaveLength(3);
      expect(chats[0].session_id).toBe("new-chat");
      expect(chats[1].session_id).toBe("mid-chat");
      expect(chats[2].session_id).toBe("old-chat");
    });
  });
});
