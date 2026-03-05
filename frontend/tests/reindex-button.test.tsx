import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReindexButton } from "@/components/chat/ReindexButton";

describe("ReindexButton", () => {
  it("renders 'Re-index this file' in default state", () => {
    render(
      <ReindexButton fileId="f1" isReindexing={false} onReindex={() => {}} />
    );
    const btn = screen.getByRole("button", { name: /re-index this file/i });
    expect(btn).toBeDefined();
    expect(btn).not.toBeDisabled();
  });

  it("renders spinner + 'Re-indexing...' when isReindexing=true", () => {
    render(
      <ReindexButton fileId="f1" isReindexing={true} onReindex={() => {}} />
    );
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    expect(screen.getByText(/re-indexing\.\.\./i)).toBeDefined();
    // Spinner should be present (Loader2 renders as svg)
    expect(btn.querySelector("svg")).toBeTruthy();
  });

  it("calls onReindex when clicked", () => {
    const onReindex = vi.fn();
    render(
      <ReindexButton fileId="f1" isReindexing={false} onReindex={onReindex} />
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onReindex).toHaveBeenCalledOnce();
  });

  it("does not call onReindex when disabled", () => {
    const onReindex = vi.fn();
    render(
      <ReindexButton fileId="f1" isReindexing={true} onReindex={onReindex} />
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onReindex).not.toHaveBeenCalled();
  });
});
