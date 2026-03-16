export interface Citation {
  index: number;
  file_name: string;
  file_id: string;
  page_number?: number;
  row_number?: number;
  slide_index?: number;
  chunk_text: string;
  source?: string;
}

export function formatCitationLabel(c: Citation): string {
  if (c.page_number) return `${c.file_name}, p.${c.page_number}`;
  if (c.row_number) return `${c.file_name}, row ${c.row_number}`;
  if (c.slide_index) return `${c.file_name}, slide ${c.slide_index}`;
  return c.file_name;
}
