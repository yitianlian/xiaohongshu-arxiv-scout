---
name: xiaohongshu-arxiv-scout
description: Use when a user sends a public Xiaohongshu, RedNote, or xhslink note URL and wants the papers inside identified and downloaded. This skill captures the note, runs OCR on screenshots and images, uses Claude Code web search to disambiguate paper titles, resolves matching arXiv papers, downloads the PDFs, renames them to the paper titles, and zips multi-paper deliveries.
---

# Xiaohongshu Arxiv Scout

## Overview

This skill turns a Xiaohongshu note link into downloadable arXiv PDFs. It is designed for "find the papers in this note and send them to me" requests, especially when paper titles only appear inside note images.

## Use This Skill When

- The user shares a `xiaohongshu.com`, `xhslink.com`, or RedNote link.
- The user wants papers, PDFs, arXiv IDs, or a paper bundle from that link.
- The note contains screenshots, image cards, or mixed Chinese and English text that require OCR.

## Guardrails

- Only work with public note links and content that can be opened normally in a browser.
- Do not claim a paper match unless there is an arXiv ID or a strong title match.
- Prefer primary sources during verification: arXiv abstract pages first, then official project or author pages when needed.
- If a note points to non-arXiv papers only, report that clearly instead of fabricating arXiv matches.

## Quick Start

1. Install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

2. Create a working folder and capture the note:

   ```bash
   python3 scripts/fetch_xiaohongshu_note.py "https://www.xiaohongshu.com/..." --out workdir/demo
   ```

3. Run OCR on the saved screenshot and downloaded note images:

   ```bash
   python3 scripts/ocr_xhs_note.py workdir/demo
   ```

4. Resolve paper candidates against arXiv:

   ```bash
   python3 scripts/resolve_arxiv_candidates.py workdir/demo
   ```

5. If `resolved-papers.json` contains ambiguous or unmatched items, use Claude Code web search to verify them before downloading.

6. Download and package the confirmed papers:

   ```bash
   python3 scripts/download_arxiv_bundle.py workdir/demo
   ```

## Preferred Workflow

### 1. Capture the note

Run `scripts/fetch_xiaohongshu_note.py` first. It resolves short links, opens the page with Playwright, saves:

- `note.json`: page URL, title, description, visible text, image URLs
- `screenshots/page.png`: full-page screenshot
- `images/`: best-effort downloads of note images

If the page blocks automation or requires login, use Claude Code's browser tools to capture screenshots manually and put them under `images/` or `screenshots/`, then continue with OCR.

### 2. OCR everything that may contain titles

Run `scripts/ocr_xhs_note.py <workdir>`.

- Default OCR engine: PaddleOCR
- Fallback OCR engine: Tesseract if PaddleOCR is unavailable

This produces `ocr.json` with per-file text and merged lines.

### 3. Resolve paper candidates

Run `scripts/resolve_arxiv_candidates.py <workdir>`.

Resolution priority:

1. Direct arXiv IDs found in page text or OCR text
2. High-confidence title matches from the arXiv API
3. Manual verification with Claude Code web search for ambiguous candidates

When manual search is needed:

- Search quoted title fragments from OCR.
- Open the best arXiv abstract page candidates.
- Confirm by title, authors, and topic before accepting the match.
- Record the final accepted titles in `resolved-papers.json`.

### 4. Download, rename, and deliver

Run `scripts/download_arxiv_bundle.py <workdir>`.

- Each PDF is renamed to the paper title.
- If there is more than one PDF, the script also creates `papers.zip`.
- Deliver the single PDF or the ZIP path back to the user.

## One-Command Runner

Use this when you want the whole pipeline with a single command:

```bash
python3 scripts/run_pipeline.py "https://www.xiaohongshu.com/..." --out workdir/run-001
```

Default behavior stops after resolution if manual review is needed. Add `--allow-ambiguous-downloads` only when you intentionally want best-effort automatic downloads.

## Files Produced

- `note.json`
- `ocr.json`
- `resolved-papers.json`
- `downloads/*.pdf`
- `downloads/papers.zip` when multiple papers are downloaded

## References

Read `references/sources.md` when you need the rationale behind the implementation choices, upstream docs, or external project references.
