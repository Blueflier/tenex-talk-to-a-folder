export interface IndexedSource {
  source_id: string;
  file_list: { name: string }[];
}

const TEMPLATES = [
  (name: string) => `Summarize ${name}`,
  (name: string) => `What are the key points in ${name}?`,
  (name: string) => `What does ${name} say about...`,
  (name: string) => `Explain the main ideas in ${name}`,
];

/**
 * Generate suggestion queries from indexed file names.
 * Purely template-based -- no LLM call.
 * Returns up to 4 suggestions from different files.
 */
export function generateSuggestions(indexedSources: IndexedSource[]): string[] {
  const fileNames: string[] = [];
  for (const source of indexedSources) {
    for (const file of source.file_list) {
      if (file.name && !fileNames.includes(file.name)) {
        fileNames.push(file.name);
      }
    }
  }

  if (fileNames.length === 0) return [];

  const suggestions: string[] = [];
  for (let i = 0; i < Math.min(4, fileNames.length); i++) {
    const template = TEMPLATES[i % TEMPLATES.length];
    suggestions.push(template(fileNames[i]));
  }

  return suggestions;
}
