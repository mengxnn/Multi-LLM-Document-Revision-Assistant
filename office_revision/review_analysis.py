from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewDecision:
    continue_revision: bool | None
    score: int | None
    writer_instructions: str = ""


def parse_review_decision(review: str) -> ReviewDecision:
    return ReviewDecision(
        continue_revision=_parse_continue_flag(review),
        score=_parse_score(review),
        writer_instructions=_extract_writer_instructions(review),
    )


def _parse_continue_flag(review: str) -> bool | None:
    match = re.search(r"是否继续修改\s*[:：]\s*(是|否)", review)
    if not match:
        return None
    return match.group(1) == "是"


def _parse_score(review: str) -> int | None:
    match = re.search(r"总体评分\s*[:：]\s*([1-5])", review)
    if not match:
        return None
    return int(match.group(1))


def _extract_writer_instructions(review: str) -> str:
    for heading in ("给 writer 的修改指令", "给Writer的修改指令", "下一轮修改清单"):
        section = _extract_section(review, heading)
        if section:
            return section
    return ""


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^\s*(?:[一二三四五六七八九十]+[、.．]\s*)?{re.escape(heading)}\s*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(
        r"^\s*[一二三四五六七八九十]+[、.．]\s*\S+",
        text[start:],
        flags=re.MULTILINE,
    )
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()
