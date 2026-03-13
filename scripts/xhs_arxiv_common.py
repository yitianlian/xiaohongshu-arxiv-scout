#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable, List

import httpx

ARXIV_ID_RE = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def extract_first_url(raw: str) -> str:
    match = URL_RE.search(raw)
    if not match:
        raise ValueError("No URL found in the provided input.")
    return match.group(0).rstrip(").,]")


def resolve_final_url(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        return str(response.url)


def sanitize_filename(value: str, fallback: str = "paper") -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"[\\/:*?\"<>|]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:180] or fallback


def extract_arxiv_ids(texts: Iterable[str]) -> List[str]:
    found = set()
    for text in texts:
        for match in ARXIV_ID_RE.findall(text or ""):
            found.add(match)
    return sorted(found)


def normalize_line(line: str) -> str:
    line = unicodedata.normalize("NFKC", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def dedupe_keep_order(lines: Iterable[str]) -> List[str]:
    seen = set()
    items = []
    for line in lines:
        normalized = normalize_line(line)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items
