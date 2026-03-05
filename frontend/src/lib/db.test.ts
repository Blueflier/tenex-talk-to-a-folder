import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import { openDB, saveChat, getChats, saveMessage, getMessages } from "./db";
import type { Chat, Message } from "./db";

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
