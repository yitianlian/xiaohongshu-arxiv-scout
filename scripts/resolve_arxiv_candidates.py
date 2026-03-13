#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import arxiv
from rapidfuzz import fuzz

from xhs_arxiv_common import dedupe_keep_order, extract_arxiv_ids, load_json, normalize_line, save_json

NOISE_RE = re.compile(
    r"(小红书|rednote|点赞|收藏|关注|评论|转发|私信|合集|必看|推荐|AI工具|网址|链接|作者|封面|教程)",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve extracted note text into arXiv papers.")
    parser.add_argument("workdir", help="Workdir containing note.json and ocr.json")
    parser.add_argument("--confidence", type=int, default=85, help="Threshold for confident title matches")
    parser.add_argument("--ambiguous", type=int, default=72, help="Threshold for ambiguous title matches")
    return parser.parse_args()


def collect_text_blobs(note: Dict, ocr: Dict) -> List[str]:
    blobs = [
        note.get("title", ""),
        note.get("description", ""),
        note.get("og_title", ""),
        note.get("og_description", ""),
        note.get("body_text", ""),
    ]
    blobs.extend(ocr.get("merged_lines", []))
    return [blob for blob in blobs if blob]


def split_candidate_lines(blobs: Iterable[str]) -> List[str]:
    pieces: List[str] = []
    for blob in blobs:
        for line in re.split(r"[\n\r]|[|]|[;]|[。！？!?]", blob):
            normalized = normalize_line(line)
            if len(normalized) < 18 or len(normalized) > 220:
                continue
            if NOISE_RE.search(normalized):
                continue
            pieces.append(normalized)
    return dedupe_keep_order(pieces)


def to_paper_dict(result: arxiv.Result) -> Dict[str, object]:
    return {
        "arxiv_id": result.get_short_id(),
        "title": normalize_line(result.title),
        "authors": [author.name for author in result.authors],
        "pdf_url": result.pdf_url,
        "summary": normalize_line(result.summary),
        "published": result.published.isoformat() if result.published else None,
    }


def query_by_id(client: arxiv.Client, arxiv_id: str) -> Optional[Dict[str, object]]:
    search = arxiv.Search(id_list=[arxiv_id])
    for result in client.results(search):
        return to_paper_dict(result)
    return None


def query_by_title(client: arxiv.Client, title: str, max_results: int = 5) -> List[Dict[str, object]]:
    queries = [
        f'ti:"{title}"',
        title,
    ]
    seen = set()
    candidates: List[Dict[str, object]] = []
    for query in queries:
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
        )
        for result in client.results(search):
            paper = to_paper_dict(result)
            if paper["arxiv_id"] in seen:
                continue
            seen.add(paper["arxiv_id"])
            candidates.append(paper)
    return candidates


def best_match(title: str, candidates: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    best: Optional[Dict[str, object]] = None
    best_score = -1
    for candidate in candidates:
        score = fuzz.token_set_ratio(title.lower(), str(candidate["title"]).lower())
        if score > best_score:
            best = dict(candidate)
            best["score"] = score
            best_score = score
    return best


def main() -> None:
    args = parse_args()
    workdir = Path(args.workdir).expanduser().resolve()
    note = load_json(workdir / "note.json")
    ocr = load_json(workdir / "ocr.json")
    blobs = collect_text_blobs(note, ocr)
    arxiv_ids = extract_arxiv_ids(blobs)
    candidate_lines = split_candidate_lines(blobs)

    client = arxiv.Client()
    direct_matches: List[Dict[str, object]] = []
    confirmed_by_id = set()
    for arxiv_id in arxiv_ids:
        paper = query_by_id(client, arxiv_id)
        if paper:
            direct_matches.append(paper)
            confirmed_by_id.add(paper["arxiv_id"])

    confident_matches: List[Dict[str, object]] = []
    ambiguous_matches: List[Dict[str, object]] = []
    unmatched_lines: List[str] = []

    for line in candidate_lines:
        candidates = query_by_title(client, line)
        best = best_match(line, candidates)
        if not best:
            unmatched_lines.append(line)
            continue
        best["query_line"] = line
        if best["arxiv_id"] in confirmed_by_id:
            continue
        if best["score"] >= args.confidence:
            confident_matches.append(best)
            confirmed_by_id.add(best["arxiv_id"])
        elif best["score"] >= args.ambiguous:
            ambiguous_matches.append(best)
        else:
            unmatched_lines.append(line)

    final_papers = dedupe_papers(direct_matches + confident_matches)
    payload = {
        "direct_matches": direct_matches,
        "confident_matches": confident_matches,
        "ambiguous_matches": ambiguous_matches,
        "unmatched_lines": dedupe_keep_order(unmatched_lines),
        "papers": final_papers,
        "needs_manual_review": bool(ambiguous_matches or unmatched_lines),
    }
    save_json(workdir / "resolved-papers.json", payload)
    print(workdir / "resolved-papers.json")


def dedupe_papers(papers: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    deduped = []
    for paper in papers:
        paper_id = paper["arxiv_id"]
        if paper_id in seen:
            continue
        seen.add(paper_id)
        deduped.append(paper)
    return deduped


if __name__ == "__main__":
    main()
