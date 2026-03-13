#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import httpx
from playwright.sync_api import sync_playwright

from xhs_arxiv_common import ensure_dir, extract_first_url, resolve_final_url, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture a Xiaohongshu note into a local workdir.")
    parser.add_argument("url", help="Xiaohongshu URL or shared text containing a URL")
    parser.add_argument("--out", required=True, help="Output directory for note artifacts")
    parser.add_argument("--timeout-ms", type=int, default=30000, help="Navigation timeout in milliseconds")
    return parser.parse_args()


def collect_page_payload(page) -> Dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const imageUrls = Array.from(document.images)
            .map((img) => img.currentSrc || img.src || "")
            .filter(Boolean)
            .filter((src) => /^https?:/i.test(src));
          const metas = Array.from(document.querySelectorAll("meta")).reduce((acc, meta) => {
            const key = meta.getAttribute("property") || meta.getAttribute("name");
            const value = meta.getAttribute("content");
            if (key && value) acc[key] = value;
            return acc;
          }, {});
          return {
            title: document.title || "",
            url: location.href,
            bodyText: document.body ? document.body.innerText : "",
            imageUrls,
            metas
          };
        }
        """
    )


def download_images(image_urls: List[str], out_dir: Path) -> List[str]:
    ensure_dir(out_dir)
    saved: List[str] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30, trust_env=False) as client:
        for index, image_url in enumerate(image_urls[:12], start=1):
            try:
                response = client.get(image_url)
                response.raise_for_status()
            except Exception:
                continue
            suffix = ".jpg"
            content_type = response.headers.get("content-type", "")
            if "png" in content_type:
                suffix = ".png"
            path = out_dir / f"image-{index:02d}{suffix}"
            path.write_bytes(response.content)
            saved.append(str(path))
    return saved


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out).expanduser().resolve()
    screenshots_dir = ensure_dir(out_dir / "screenshots")
    images_dir = ensure_dir(out_dir / "images")

    shared_url = extract_first_url(args.url)
    final_url = resolve_final_url(shared_url)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2400})
        page.goto(final_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.wait_for_timeout(4500)
        payload = collect_page_payload(page)
        screenshot_path = screenshots_dir / "page.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    downloaded_images = download_images(payload.get("imageUrls", []), images_dir)
    note = {
        "input_url": shared_url,
        "resolved_url": final_url,
        "page_url": payload.get("url", final_url),
        "title": payload.get("title", ""),
        "description": payload.get("metas", {}).get("description", ""),
        "og_title": payload.get("metas", {}).get("og:title", ""),
        "og_description": payload.get("metas", {}).get("og:description", ""),
        "body_text": payload.get("bodyText", ""),
        "image_urls": payload.get("imageUrls", []),
        "downloaded_images": downloaded_images,
        "screenshots": [str(screenshot_path)],
    }
    save_json(out_dir / "note.json", note)
    print(out_dir)


if __name__ == "__main__":
    main()
