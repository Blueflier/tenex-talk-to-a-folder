import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { IndexingModal } from "./IndexingModal";

/** Helper: build a ReadableStream that emits encoded SSE text chunks */
function makeSSEStream(events: Array<{ event: string; data: string }>) {
  const encoder = new TextEncoder();
  let chunks = events.map(
    (e) => `event: ${e.event}\ndata: ${e.data}\n\n`
  );
  let index = 0;

  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchWithEvents(events: Array<{ event: string; data: string }>) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    body: makeSSEStream(events),
  } as unknown as Response);
}

const defaultProps = {
  open: true,
  driveUrl: "https://drive.google.com/drive/folders/abc123",
  sessionId: "test-session",
  token: "test-token",
  onComplete: vi.fn(),
  onCancel: vi.fn(),
  onError: vi.fn(),
};

describe("IndexingModal", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders in extracting state and shows file list", async () => {
    globalThis.fetch = mockFetchWithEvents([
      {
        event: "extraction",
        data: JSON.stringify({
          file_id: "f1",
          file_name: "report.pdf",
          status: "extracting",
        }),
      },
      {
        event: "extraction",
        data: JSON.stringify({
          file_id: "f1",
          file_name: "report.pdf",
          status: "done",
          chunk_count: 10,
        }),
      },
      {
        event: "extraction",
        data: JSON.stringify({
          file_id: "f2",
          file_name: "image.png",
          status: "skipped",
          reason: "Image files are not supported",
        }),
      },
      {
        event: "embedding_start",
        data: JSON.stringify({ total_chunks: 10 }),
      },
    ]);

    render(<IndexingModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("embedding-progress")).toBeDefined();
    });
  });

  it("transitions to embedding state with progress bar", async () => {
    globalThis.fetch = mockFetchWithEvents([
      {
        event: "embedding_start",
        data: JSON.stringify({ total_chunks: 100 }),
      },
      {
        event: "embedding_progress",
        data: JSON.stringify({ embedded: 50, total: 100 }),
      },
    ]);

    render(<IndexingModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("embedding-progress")).toBeDefined();
      expect(screen.getByText("50/100 chunks")).toBeDefined();
    });
  });

  it("cancel triggers AbortController.abort()", async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, "abort");

    // Slow stream that never completes
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream({
        start() {
          // never enqueue or close - simulates an ongoing stream
        },
      }),
    } as unknown as Response);

    render(<IndexingModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("cancel-btn")).toBeDefined();
    });

    await act(async () => {
      screen.getByTestId("cancel-btn").click();
    });

    expect(abortSpy).toHaveBeenCalled();
    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it('error event with "empty_folder" code shows correct message', async () => {
    globalThis.fetch = mockFetchWithEvents([
      {
        event: "error",
        data: JSON.stringify({
          message: "Folder is empty",
          code: "empty_folder",
        }),
      },
    ]);

    render(<IndexingModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getAllByText("This folder is empty").length).toBeGreaterThan(0);
    });
  });

  it('error event with "no_supported_files" code shows correct message', async () => {
    globalThis.fetch = mockFetchWithEvents([
      {
        event: "extraction",
        data: JSON.stringify({
          file_id: "f1",
          file_name: "image.png",
          status: "skipped",
          reason: "Image files are not supported",
        }),
      },
      {
        event: "error",
        data: JSON.stringify({
          message: "No supported files",
          code: "no_supported_files",
        }),
      },
    ]);

    render(<IndexingModal {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getAllByText("No supported file types found").length
      ).toBeGreaterThan(0);
    });
  });

  it("calls onComplete after success auto-dismiss", async () => {
    globalThis.fetch = mockFetchWithEvents([
      {
        event: "extraction",
        data: JSON.stringify({
          file_id: "f1",
          file_name: "report.pdf",
          status: "done",
          chunk_count: 10,
        }),
      },
      {
        event: "embedding_start",
        data: JSON.stringify({ total_chunks: 10 }),
      },
      {
        event: "embedding_progress",
        data: JSON.stringify({ embedded: 10, total: 10 }),
      },
      {
        event: "complete",
        data: JSON.stringify({ files_indexed: 1, total_chunks: 10 }),
      },
    ]);

    render(<IndexingModal {...defaultProps} />);

    // Wait for success state
    await waitFor(() => {
      expect(screen.getByText("Indexing complete")).toBeDefined();
    });

    // Advance past auto-dismiss
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(defaultProps.onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        filesIndexed: 1,
        totalChunks: 10,
      })
    );
  });
});
