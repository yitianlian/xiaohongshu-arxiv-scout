# Sources

This skill combines browser capture, OCR, arXiv API matching, and final file packaging. These sources informed the design:

## Claude Code

- Anthropic Claude Code docs: https://docs.anthropic.com/en/docs/claude-code/overview
- Anthropic Claude Code settings and permissions: https://docs.anthropic.com/en/docs/claude-code/settings

Why it matters:

- The skill expects Claude Code to do the final web verification step for ambiguous titles.
- Browser, web search, and bash execution are left to Claude Code instead of hard-coding every search branch inside Python.

## arXiv

- arXiv API overview: https://info.arxiv.org/help/api/index.html
- arXiv API user manual: https://info.arxiv.org/help/api/user-manual.html

Why it matters:

- arXiv is the primary source of truth for final paper identity and PDF download URLs.
- Title queries and direct `id_list` queries are both supported by the API.

## OCR

- PaddleOCR official docs: https://www.paddleocr.ai/latest/en/index.html
- PaddleOCR quick start and usage docs: https://www.paddleocr.ai/latest/en/version2.x/ppocr/quick_start.html

Why it matters:

- Xiaohongshu paper notes often place titles in image cards, not in selectable HTML text.
- PaddleOCR handles mixed Chinese and English better than basic OCR-only fallbacks.

## Xiaohongshu / note extraction references

- MediaCrawler: https://github.com/NanmiCoder/MediaCrawler
- xhs downloader examples on GitHub search: https://github.com/search?q=xiaohongshu+downloader&type=repositories

Why it matters:

- Xiaohongshu has no stable public developer API for this workflow.
- In practice, a browser-rendered capture plus OCR is more robust than relying on brittle page HTML alone.

## Design choices

- Capture first, OCR second, arXiv resolve third.
- Use direct arXiv IDs whenever possible.
- Keep ambiguous matches for Claude Code web verification instead of forcing weak fuzzy matches.
- Rename files to paper titles because that is what the user asked to receive.
