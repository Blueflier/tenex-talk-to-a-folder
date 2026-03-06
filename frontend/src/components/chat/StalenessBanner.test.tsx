import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { StalenessBanner, type StalenessInfo } from "./StalenessBanner";
import { StalenessBannerList } from "./StalenessBannerList";
import { saveMessage, loadMessages, type Message } from "@/lib/db";

describe("StalenessBanner", () => {
  it("renders yellow banner for stale file (no error)", () => {
    const info: StalenessInfo = {
      file_name: "report.pdf",
      file_id: "f1",
    };
    render(<StalenessBanner info={info} sessionId="s1" />);
    const banner = screen.getByTestId("staleness-banner");
    expect(banner.className).toContain("bg-yellow-50");
    expect(screen.getByText(/report\.pdf/)).toBeDefined();
    expect(
      screen.getByText(/was modified after indexing/)
    ).toBeDefined();
  });

  it("renders red banner for deleted file (error=not_found)", () => {
    const info: StalenessInfo = {
      file_name: "gone.pdf",
      file_id: "f2",
      error: "not_found",
    };
    render(<StalenessBanner info={info} sessionId="s1" />);
    const banner = screen.getByTestId("staleness-banner");
    expect(banner.className).toContain("bg-red-50");
    expect(
      screen.getByText(/no longer exists in Google Drive/)
    ).toBeDefined();
    // No re-index placeholder
    expect(screen.queryByText(/Re-index/i)).toBeNull();
  });

  it("renders amber banner for access revoked (error=access_denied)", () => {
    const info: StalenessInfo = {
      file_name: "secret.pdf",
      file_id: "f3",
      error: "access_denied",
    };
    render(<StalenessBanner info={info} sessionId="s1" />);
    const banner = screen.getByTestId("staleness-banner");
    expect(banner.className).toContain("bg-amber-50");
    expect(
      screen.getByText(/Access to secret\.pdf was revoked/)
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: /Re-authenticate/i })
    ).toBeDefined();
  });

  it("shows extra no-matches text when noMatches=true", () => {
    const info: StalenessInfo = {
      file_name: "empty.pdf",
      file_id: "f4",
    };
    render(<StalenessBanner info={info} sessionId="s1" noMatches />);
    expect(
      screen.getByText(/No matches found/)
    ).toBeDefined();
  });
});

describe("StalenessBannerList", () => {
  it("renders one banner per stale file", () => {
    const files: StalenessInfo[] = [
      { file_name: "a.pdf", file_id: "1" },
      { file_name: "b.pdf", file_id: "2", error: "not_found" },
      { file_name: "c.pdf", file_id: "3", error: "access_denied" },
    ];
    render(<StalenessBannerList staleFiles={files} sessionId="s1" />);
    const banners = screen.getAllByTestId("staleness-banner");
    expect(banners).toHaveLength(3);
  });
});

describe("stale_files persistence", () => {
  beforeEach(() => {
    indexedDB = new IDBFactory();
  });

  it("saves and loads stale_files on message records", async () => {
    const staleFiles: StalenessInfo[] = [
      { file_name: "stale.pdf", file_id: "sf1" },
      { file_name: "gone.pdf", file_id: "sf2", error: "not_found" },
    ];

    const msg: Message = {
      session_id: "stale-session",
      role: "assistant",
      content: "Answer with stale files",
      citations: [],
      stale_files: staleFiles,
      created_at: new Date().toISOString(),
    };

    await saveMessage(msg);
    const loaded = await loadMessages("stale-session");

    expect(loaded).toHaveLength(1);
    expect(loaded[0].stale_files).toHaveLength(2);
    expect(loaded[0].stale_files![0].file_name).toBe("stale.pdf");
    expect(loaded[0].stale_files![1].error).toBe("not_found");
  });
});
