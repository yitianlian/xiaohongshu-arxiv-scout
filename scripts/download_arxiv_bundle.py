#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

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


async def download_one(
    session: aiohttp.ClientSession, paper: Dict[str, object], out_dir: Path
) -> Tuple[bool, Dict[str, object]]:
    arxiv_id = str(paper["arxiv_id"])
    title = sanitize_filename(str(paper["title"]), fallback=arxiv_id)
    filename = ensure_unique_path(out_dir / f"{title}.pdf")
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    last_error = None
    for attempt in range(3):
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                filename.write_bytes(await response.read())
            return True, {"arxiv_id": arxiv_id, "title": paper["title"], "path": str(filename), "url": url}
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(2**attempt)
    return False, {"arxiv_id": arxiv_id, "title": paper["title"], "url": url, "error": str(last_error)}


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


async def download_all(
    papers: List[Dict[str, object]], out_dir: Path
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    timeout = aiohttp.ClientTimeout(total=180)
    connector = aiohttp.TCPConnector(limit=3)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, trust_env=False) as session:
        tasks = [download_one(session, paper, out_dir) for paper in papers]
        results = await asyncio.gather(*tasks)
    downloaded: List[Dict[str, object]] = []
    failed: List[Dict[str, object]] = []
    for ok, payload in results:
        if ok:
            downloaded.append(payload)
        else:
            failed.append(payload)
    return downloaded, failed


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
    downloaded, failed = asyncio.run(download_all(papers, downloads_dir))
    if not downloaded:
        raise SystemExit(f"All downloads failed: {failed}")

    bundle_path = None
    if len(downloaded) > 1:
        bundle_path = create_zip(downloaded, downloads_dir / "papers.zip")

    payload = {
        "downloaded": downloaded,
        "failed": failed,
        "bundle_path": bundle_path,
        "delivery_path": bundle_path or downloaded[0]["path"],
    }
    save_json(workdir / "download-manifest.json", payload)
    print(payload["delivery_path"])


if __name__ == "__main__":
    main()
