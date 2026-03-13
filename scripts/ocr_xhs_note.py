#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List

import httpx
from PIL import Image

from xhs_arxiv_common import dedupe_keep_order, ensure_dir, load_json, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OCR on saved Xiaohongshu screenshots and images.")
    parser.add_argument("workdir", help="Workdir created by fetch_xiaohongshu_note.py")
    parser.add_argument("--lang", default="ch", help="OCR language for PaddleOCR")
    parser.add_argument(
        "--provider",
        choices=["auto", "ocr-space", "paddleocr", "tesseract"],
        default="auto",
        help="OCR provider selection",
    )
    parser.add_argument(
        "--ocr-space-api-key",
        default=os.getenv("OCR_SPACE_API_KEY"),
        help="OCR.space API key. If omitted, auto mode falls back to local OCR.",
    )
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


def run_ocr_space(images: List[Path], api_key: str) -> Dict[str, List[str]]:
    results: Dict[str, List[str]] = {}
    headers = {"apikey": api_key}
    language = "chs"
    with httpx.Client(timeout=60) as client:
        for image in images:
            with image.open("rb") as handle:
                files = {"file": (image.name, handle, "application/octet-stream")}
                data = {
                    "language": language,
                    "isOverlayRequired": "false",
                    "scale": "true",
                    "OCREngine": "2",
                }
                response = client.post("https://api.ocr.space/parse/image", headers=headers, data=data, files=files)
                response.raise_for_status()
            payload = response.json()
            parsed_results = payload.get("ParsedResults", [])
            lines: List[str] = []
            for item in parsed_results:
                parsed_text = str(item.get("ParsedText", "")).strip()
                if parsed_text:
                    lines.extend(line.strip() for line in parsed_text.splitlines() if line.strip())
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

    engine = None
    per_file: Dict[str, List[str]]
    provider_order = {
        "ocr-space": ["ocr-space"],
        "paddleocr": ["paddleocr"],
        "tesseract": ["tesseract"],
        "auto": ["ocr-space", "paddleocr", "tesseract"],
    }[args.provider]

    last_error = None
    for provider in provider_order:
        try:
            if provider == "ocr-space":
                if not args.ocr_space_api_key:
                    raise RuntimeError("OCR.space API key is required for OCR API mode.")
                per_file = run_ocr_space(images, args.ocr_space_api_key)
            elif provider == "paddleocr":
                per_file = run_paddleocr(images, args.lang)
            else:
                per_file = run_tesseract(images)
            engine = provider
            break
        except Exception as exc:
            last_error = exc
    else:
        raise SystemExit(f"All OCR providers failed: {last_error}")

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
