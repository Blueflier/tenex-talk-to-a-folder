const DB_NAME = "talk-to-a-folder";
const DB_VERSION = 1;

export interface Chat {
  session_id: string;
  title: string;
  created_at: string;
  last_message_at: string;
  indexed_sources: string[];
  indexed_files?: Array<{ file_id: string; file_name: string; indexed_at: string }>;
}

export interface Message {
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citations: unknown[];
  stale_files?: { file_name: string; file_id: string; error?: "not_found" | "access_denied" | null }[];
  created_at: string;
}

export function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;

      // Drop old stores on upgrade
      for (const name of Array.from(db.objectStoreNames)) {
        db.deleteObjectStore(name);
      }

      const chatsStore = db.createObjectStore("chats", {
        keyPath: "session_id",
      });
      chatsStore.createIndex("last_message_at", "last_message_at", {
        unique: false,
      });

      const messagesStore = db.createObjectStore("messages", {
        autoIncrement: true,
      });
      messagesStore.createIndex("session_id", "session_id", {
        unique: false,
      });
      messagesStore.createIndex("created_at", "created_at", {
        unique: false,
      });
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveChat(chat: Chat): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chats", "readwrite");
    tx.objectStore("chats").put(chat);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

export async function getChats(): Promise<Chat[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chats", "readonly");
    const index = tx.objectStore("chats").index("last_message_at");
    const request = index.openCursor(null, "prev");
    const results: Chat[] = [];

    request.onsuccess = () => {
      const cursor = request.result;
      if (cursor) {
        results.push(cursor.value as Chat);
        cursor.continue();
      } else {
        db.close();
        resolve(results);
      }
    };

    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

export async function saveMessage(msg: Message): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("messages", "readwrite");
    tx.objectStore("messages").add(msg);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

export async function getMessages(sessionId: string): Promise<Message[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("messages", "readonly");
    const index = tx.objectStore("messages").index("session_id");
    const request = index.getAll(sessionId);

    request.onsuccess = () => {
      db.close();
      resolve(request.result as Message[]);
    };

    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

/**
 * Load messages for a session, sorted by created_at ascending.
 * No auth check -- old chats are viewable without authentication (PERS-04).
 */
export async function loadMessages(sessionId: string): Promise<Message[]> {
  const messages = await getMessages(sessionId);
  return messages.sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
}

export async function getChat(sessionId: string): Promise<Chat | undefined> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chats", "readonly");
    const request = tx.objectStore("chats").get(sessionId);

    request.onsuccess = () => {
      db.close();
      resolve(request.result as Chat | undefined);
    };

    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

export async function updateChatTitle(
  sessionId: string,
  title: string
): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chats", "readwrite");
    const store = tx.objectStore("chats");
    const getReq = store.get(sessionId);

    getReq.onsuccess = () => {
      const chat = getReq.result as Chat | undefined;
      if (chat) {
        chat.title = title;
        store.put(chat);
      }
    };

    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

export async function deleteChat(sessionId: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("chats", "readwrite");
    tx.objectStore("chats").delete(sessionId);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

export async function deleteMessages(sessionId: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("messages", "readwrite");
    const index = tx.objectStore("messages").index("session_id");
    const request = index.openCursor(IDBKeyRange.only(sessionId));

    request.onsuccess = () => {
      const cursor = request.result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };

    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
