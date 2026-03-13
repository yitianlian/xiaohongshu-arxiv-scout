#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from PIL import Image

from xhs_arxiv_common import dedupe_keep_order, ensure_dir, load_json, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OCR on saved Xiaohongshu screenshots and images.")
    parser.add_argument("workdir", help="Workdir created by fetch_xiaohongshu_note.py")
    parser.add_argument("--lang", default="ch", help="OCR language for PaddleOCR")
    return parser.parse_args()


def discover_images(workdir: Path) -> List[Path]:
    note = load_json(workdir / "note.json")
    paths = []
    for item in note.get("screenshots", []):
        paths.append(Path(item))
    for item in note.get("downloaded_images", []):
        paths.append(Path(item))
    return [path for path in paths if path.exists()]


def run_paddleocr(images: List[Path], lang: str) -> Dict[str, List[str]]:
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    results: Dict[str, List[str]] = {}
    for image in images:
        raw = ocr.ocr(str(image), cls=True)
        lines: List[str] = []
        for block in raw or []:
            for item in block or []:
                if not item or len(item) < 2:
                    continue
                text_info = item[1]
                if isinstance(text_info, (list, tuple)) and text_info:
                    text = str(text_info[0]).strip()
                    if text:
                        lines.append(text)
        results[str(image)] = dedupe_keep_order(lines)
    return results


def run_tesseract(images: List[Path]) -> Dict[str, List[str]]:
    import pytesseract

    results: Dict[str, List[str]] = {}
    for image in images:
        text = pytesseract.image_to_string(Image.open(image))
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        results[str(image)] = dedupe_keep_order(lines)
    return results


def main() -> None:
    args = parse_args()
    workdir = Path(args.workdir).expanduser().resolve()
    ensure_dir(workdir)
    images = discover_images(workdir)
    if not images:
        raise SystemExit("No screenshots or note images found for OCR.")

    engine = "paddleocr"
    try:
        per_file = run_paddleocr(images, args.lang)
    except Exception:
        engine = "tesseract"
        per_file = run_tesseract(images)

    merged_lines: List[str] = []
    for lines in per_file.values():
        merged_lines.extend(lines)

    payload = {
        "engine": engine,
        "files": per_file,
        "merged_lines": dedupe_keep_order(merged_lines),
    }
    save_json(workdir / "ocr.json", payload)
    print(workdir / "ocr.json")


if __name__ == "__main__":
    main()
