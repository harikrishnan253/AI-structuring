"""
Reference zone detection.
"""

from __future__ import annotations

import re
import logging


logger = logging.getLogger(__name__)


HEADING_MATCHES = {
    "references",
    "bibliography",
    "suggested readings",
    "further reading",
}

CITATION_PATTERNS = [
    r"^\d+\.\s",
    r"^\[\d+\]",
    r"\(\d{4}\)",
]


def _is_citation_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    t_low = t.lower()
    if "doi" in t_low or "et al." in t_low or "et al" in t_low:
        return True
    for pat in CITATION_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def _is_heading_start(text: str) -> bool:
    return text.strip().lower() in HEADING_MATCHES


def detect_reference_zone(blocks: list[dict]) -> tuple[set[int], str, int | None]:
    """
    Return set of block ids in reference zone, trigger reason, and start index.
    """
    ref_ids = set()
    trigger_reason = "none"
    start_idx = None
    total = len(blocks)

    # Prefer explicit heading match
    for idx, b in enumerate(blocks):
        text = b.get("text", "")
        if _is_heading_start(text):
            start_idx = idx
            trigger_reason = "heading_match"
            break

    # Citation-density fallback
    if start_idx is None and total > 0:
        window_size = 30
        min_start = int(total * 0.70)
        for center in range(total):
            start = max(0, center - (window_size // 2))
            end = min(total, start + window_size)
            window = blocks[start:end]
            hits = sum(1 for w in window if _is_citation_line(w.get("text", "")))
            if hits >= 10 and start >= min_start:
                start_idx = start
                trigger_reason = "citation_density"
                break

    if start_idx is not None:
        for b in blocks[start_idx:]:
            ref_ids.add(b.get("id"))

    logger.info(
        "Reference zone detection: %s blocks (trigger=%s, start_idx=%s)",
        len(ref_ids),
        trigger_reason,
        start_idx,
    )
    return ref_ids, trigger_reason, start_idx
