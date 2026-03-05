import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "./ChatInput";
import { buildPlaceholder } from "./ChatHeader";

// Mock useAutoResize since it depends on DOM measurement
vi.mock("@/hooks/useAutoResize", () => ({
  useAutoResize: () => () => {},
}));

const defaultProps = {
  isStreaming: false,
  onSend: vi.fn(),
  onStop: vi.fn(),
  onDriveLink: vi.fn(),
};

describe("ChatInput Drive link detection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls onDriveLink for valid Drive folder URL on submit", () => {
    render(<ChatInput {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, {
      target: { value: "https://drive.google.com/drive/folders/abc123def" },
    });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(defaultProps.onDriveLink).toHaveBeenCalledWith(
      "https://drive.google.com/drive/folders/abc123def"
    );
    expect(defaultProps.onSend).not.toHaveBeenCalled();
  });

  it("calls onDriveLink for valid Drive file URL on submit", () => {
    render(<ChatInput {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, {
      target: { value: "https://drive.google.com/file/d/xyz789abc" },
    });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(defaultProps.onDriveLink).toHaveBeenCalledWith(
      "https://drive.google.com/file/d/xyz789abc"
    );
  });

  it("shows error for invalid Drive-like URL", () => {
    render(<ChatInput {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, {
      target: { value: "https://drive.google.com/invalid" },
    });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByTestId("drive-error")).toBeDefined();
    expect(screen.getByTestId("drive-error").textContent).toContain(
      "Invalid Google Drive link"
    );
    expect(defaultProps.onDriveLink).not.toHaveBeenCalled();
  });

  it("calls onDriveLink on paste of valid Drive URL", () => {
    render(<ChatInput {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.paste(input, {
      clipboardData: {
        getData: () => "https://drive.google.com/drive/folders/testFolder123",
      },
    });

    expect(defaultProps.onDriveLink).toHaveBeenCalledWith(
      "https://drive.google.com/drive/folders/testFolder123"
    );
  });

  it("sends regular text to onSend (not onDriveLink)", () => {
    render(<ChatInput {...defaultProps} />);
    const input = screen.getByTestId("chat-input");

    fireEvent.change(input, {
      target: { value: "What is the quarterly revenue?" },
    });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(defaultProps.onSend).toHaveBeenCalledWith(
      "What is the quarterly revenue?"
    );
    expect(defaultProps.onDriveLink).not.toHaveBeenCalled();
  });

  it("disables input when disabled prop is true", () => {
    render(<ChatInput {...defaultProps} disabled={true} />);
    const input = screen.getByTestId("chat-input");
    expect(input).toHaveProperty("disabled", true);
  });

  it("uses custom placeholder text", () => {
    render(
      <ChatInput {...defaultProps} placeholder="Ask about report.pdf..." />
    );
    const input = screen.getByTestId("chat-input");
    expect(input.getAttribute("placeholder")).toBe("Ask about report.pdf...");
  });
});

describe("buildPlaceholder", () => {
  it("returns default for empty array", () => {
    expect(buildPlaceholder([])).toBe("Ask about your files...");
  });

  it("returns single file name", () => {
    expect(buildPlaceholder(["report.pdf"])).toBe("Ask about report.pdf...");
  });

  it("returns two file names with 'and'", () => {
    expect(buildPlaceholder(["report.pdf", "budget.xlsx"])).toBe(
      "Ask about report.pdf and budget.xlsx..."
    );
  });

  it("returns first two names plus count for 3+ files", () => {
    expect(
      buildPlaceholder(["report.pdf", "budget.xlsx", "notes.md", "data.csv"])
    ).toBe("Ask about report.pdf, budget.xlsx, and 2 more...");
  });
});
