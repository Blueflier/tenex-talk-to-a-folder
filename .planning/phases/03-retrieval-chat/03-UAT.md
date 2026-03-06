---
status: testing
phase: 03-retrieval-chat
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md]
started: 2026-03-05T22:30:00Z
updated: 2026-03-05T22:30:00Z
---

## Current Test

number: 1
name: Cold Start Smoke Test
expected: |
  Kill any running server/service. Start the backend from scratch. Server boots without errors. A health check or basic API call returns successfully.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Start the backend from scratch. Server boots without errors. A health check or basic API call returns successfully.
result: [pending]

### 2. Ask a Question and Get Streamed Response
expected: Type a question in the chat input and press Enter. The assistant response streams in token by token with a blinking cursor. After streaming completes, citation badges appear as clickable blue pills inline with the text.
result: [pending]

### 3. Citation Popover Details
expected: Click a citation badge [N] on an assistant message. A popover opens showing the source file name, page/sheet info, and a passage excerpt. Popover stays visible while hovering and dismisses on click outside.
result: [pending]

### 4. No Results Fallback
expected: Ask a question that has no matching documents in the indexed folder. Instead of hallucinating, the assistant shows a muted italic message indicating no relevant results were found.
result: [pending]

### 5. Chat History Persists Across Refresh
expected: Send a message and get a response. Refresh the page. The previous messages (both user and assistant) reload from IndexedDB with citations intact.
result: [pending]

### 6. Auth Guard Blocks Unauthenticated Sends
expected: Without being logged in (no google_access_token), attempt to send a message. The send is blocked and a re-authentication banner appears instead of sending the request.
result: [pending]

### 7. Empty State with Suggestion Cards
expected: Open a fresh chat with no messages. An empty state appears showing the count of indexed files and up to 4 clickable suggestion cards generated from file names.
result: [pending]

### 8. Suggestion Card Prefills Input
expected: Click a suggestion card in the empty state. The suggestion text auto-fills into the chat input textarea, ready to send.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0

## Gaps

[none yet]
