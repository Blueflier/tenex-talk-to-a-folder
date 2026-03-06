# Eval Harness

Eval harness for measuring RAG quality on QASPER academic papers. Scores responses with token-level F1 and classifies failures diagnostically.

## Prerequisites

- Running uvicorn locally (`uvicorn backend.app:app`)
- OpenAI API key set as `OPENAI_API_KEY` (for embeddings)

## Setup

```bash
pip install datasets
```

Only `datasets` is a new dependency. All others (httpx, numpy, pymupdf, openai) are already in requirements.txt.

## Usage

### Main Eval

```bash
# Dry run: validate dataset loading without API calls
EVAL_MODE=1 python eval/run_eval.py --dry-run

# Full eval: run against local uvicorn
EVAL_MODE=1 python eval/run_eval.py
```

`EVAL_MODE=1` bypasses Google auth so the chat endpoint accepts requests with a synthetic user ID.

### Drive Delta

Compare local PDF eval scores against Drive-fetched scores:

```bash
EVAL_MODE=1 GOOGLE_ACCESS_TOKEN=<your-token> python eval/run_drive_delta.py
```

1. Upload 5 PDFs to a Google Drive folder
2. Set `drive_delta.drive_folder_link` in `eval/config.json`
3. Run with a valid Google access token

Flags papers where local vs Drive F1 differs by more than 0.10 (configurable via `drive_delta.f1_delta_threshold`).

## Configuration

Edit `eval/config.json`:

```json
{
  "base_url": "http://localhost:8000",
  "n_papers": 5,
  "seed": 42,
  "similarity_threshold": 0.7,
  "drive_delta": {
    "drive_folder_link": "",
    "f1_delta_threshold": 0.10
  }
}
```

## Cache

First run embeds papers via OpenAI (~$0.01 for 5 papers). Embeddings are cached to `eval/cache/`. Subsequent runs load from cache without hitting OpenAI.

Delete `eval/cache/` to force re-embedding.

## QASPER Dataset

Dataset is auto-downloaded by the HuggingFace `datasets` library on first run. No manual download needed. The eval selects 5 papers by question density from the QASPER test split (416 papers total).

## Output

Results are written to `eval/results.json` with:
- Overall F1 score
- Per-paper F1 breakdown
- Diagnostic counts (CORRECT, CRAWL_MISS, RETRIEVAL_MISS, SYNTHESIS_FAIL)

A summary table is also printed to stdout.
