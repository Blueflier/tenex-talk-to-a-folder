import { describe, it, expect } from "vitest";
import { formatCitationLabel, type Citation } from "./citations";

function makeCitation(overrides: Partial<Citation> = {}): Citation {
  return {
    index: 1,
    file_name: "test.pdf",
    file_id: "abc123",
    chunk_text: "sample text",
    ...overrides,
  };
}

describe("formatCitationLabel", () => {
  it("returns 'file.pdf, p.7' for PDF with page_number", () => {
    const c = makeCitation({ file_name: "report.pdf", page_number: 7 });
    expect(formatCitationLabel(c)).toBe("report.pdf, p.7");
  });

  it("returns 'data.csv, row 12' for sheet with row_number", () => {
    const c = makeCitation({ file_name: "data.csv", row_number: 12 });
    expect(formatCitationLabel(c)).toBe("data.csv, row 12");
  });

  it("returns 'deck.pptx, slide 3' for slides with slide_index", () => {
    const c = makeCitation({ file_name: "deck.pptx", slide_index: 3 });
    expect(formatCitationLabel(c)).toBe("deck.pptx, slide 3");
  });

  it("returns just file name when no page/row/slide metadata", () => {
    const c = makeCitation({ file_name: "notes.txt" });
    expect(formatCitationLabel(c)).toBe("notes.txt");
  });
});

describe("Citation schema", () => {
  it("matches expected shape with all optional fields", () => {
    const c: Citation = {
      index: 1,
      file_name: "report.pdf",
      file_id: "abc",
      page_number: 5,
      row_number: undefined,
      slide_index: undefined,
      chunk_text: "some passage",
    };
    expect(c).toHaveProperty("index");
    expect(c).toHaveProperty("file_name");
    expect(c).toHaveProperty("file_id");
    expect(c).toHaveProperty("chunk_text");
  });

  it("allows row_number without page_number", () => {
    const c: Citation = {
      index: 2,
      file_name: "data.csv",
      file_id: "def",
      row_number: 10,
      chunk_text: "row data",
    };
    expect(c.row_number).toBe(10);
    expect(c.page_number).toBeUndefined();
  });
});
