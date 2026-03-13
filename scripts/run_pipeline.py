#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Xiaohongshu to arXiv pipeline.")
    parser.add_argument("url", help="Xiaohongshu URL or share text containing a URL")
    parser.add_argument("--out", required=True, help="Workdir for artifacts")
    parser.add_argument(
        "--allow-ambiguous-downloads",
        action="store_true",
        help="Continue downloading even when manual review is still recommended",
    )
    return parser.parse_args()


def run_step(script: str, *extra: str) -> None:
    cmd = [sys.executable, script, *extra]
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    workdir = Path(args.out).expanduser().resolve()
    run_step("scripts/fetch_xiaohongshu_note.py", args.url, "--out", str(workdir))
    run_step("scripts/ocr_xhs_note.py", str(workdir))
    run_step("scripts/resolve_arxiv_candidates.py", str(workdir))

    download_args = [str(workdir)]
    if args.allow_ambiguous_downloads:
        download_args.append("--allow-ambiguous-downloads")
    run_step("scripts/download_arxiv_bundle.py", *download_args)


if __name__ == "__main__":
    main()
