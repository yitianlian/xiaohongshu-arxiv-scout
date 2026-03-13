#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import zipfile
from pathlib import Path
from typing import Dict, List

import aiohttp

from xhs_arxiv_common import ensure_dir, load_json, sanitize_filename, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download resolved arXiv papers and package them.")
    parser.add_argument("workdir", help="Workdir containing resolved-papers.json")
    parser.add_argument(
        "--allow-ambiguous-downloads",
        action="store_true",
        help="Download even if manual review is still needed",
    )
    return parser.parse_args()


async def download_one(session: aiohttp.ClientSession, paper: Dict[str, object], out_dir: Path) -> Dict[str, object]:
    arxiv_id = str(paper["arxiv_id"])
    title = sanitize_filename(str(paper["title"]), fallback=arxiv_id)
    filename = ensure_unique_path(out_dir / f"{title}.pdf")
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    async with session.get(url) as response:
        response.raise_for_status()
        filename.write_bytes(await response.read())
    return {"arxiv_id": arxiv_id, "title": paper["title"], "path": str(filename), "url": url}


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


async def download_all(papers: List[Dict[str, object]], out_dir: Path) -> List[Dict[str, object]]:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [download_one(session, paper, out_dir) for paper in papers]
        return await asyncio.gather(*tasks)


def create_zip(files: List[Dict[str, object]], zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_info in files:
            file_path = Path(str(file_info["path"]))
            archive.write(file_path, arcname=file_path.name)
    return str(zip_path)


def main() -> None:
    args = parse_args()
    workdir = Path(args.workdir).expanduser().resolve()
    resolved = load_json(workdir / "resolved-papers.json")
    if resolved.get("needs_manual_review") and not args.allow_ambiguous_downloads:
        raise SystemExit("Manual review is still required. Re-run with --allow-ambiguous-downloads if intentional.")

    papers = resolved.get("papers", [])
    if not papers:
        raise SystemExit("No resolved papers available for download.")

    downloads_dir = ensure_dir(workdir / "downloads")
    downloaded = asyncio.run(download_all(papers, downloads_dir))

    bundle_path = None
    if len(downloaded) > 1:
        bundle_path = create_zip(downloaded, downloads_dir / "papers.zip")

    payload = {
        "downloaded": downloaded,
        "bundle_path": bundle_path,
        "delivery_path": bundle_path or downloaded[0]["path"],
    }
    save_json(workdir / "download-manifest.json", payload)
    print(payload["delivery_path"])


if __name__ == "__main__":
    main()
