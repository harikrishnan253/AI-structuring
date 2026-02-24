"""
Block extraction for DOCX documents.
Builds block-level records with structural features for lists, tables, captions, and boxes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .ingestion import extract_document, BOX_TYPE_MAPPING, BOX_START_PATTERNS, BOX_END_PATTERNS


FIGURE_CAPTION_PATTERNS = [
    r"^figure\s*\d",
    r"^fig\.\s*\d",
    r"^<fn>",
    r"^<ft>",
]

TABLE_CAPTION_PATTERNS = [
    r"^table\s*\d",
    r"^tab\.\s*\d",
    r"^<tab",
    r"^<tn>",
    r"^<tt>",
]

SOURCE_LINE_PATTERNS = [
    r"^source:",
    r"^adapted from",
    r"^reproduced from",
    r"^data from",
    r"^courtesy of",
    r"^<cl>",
]

BOX_TITLE_PATTERNS = [
    r"^<bt>",
    r"^<bn>",
    r"^box\s*\d",
]


def _is_box_marker(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for pattern in BOX_START_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return "start"
    for pattern in BOX_END_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return "end"
    return None


def _detect_caption_type(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for pattern in FIGURE_CAPTION_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return "figure"
    for pattern in TABLE_CAPTION_PATTERNS:
        if re.match(pattern, text_lower, re.IGNORECASE):
            return "table"
    return None


def _detect_source_line(text: str) -> bool:
    text_lower = text.lower().strip()
    return any(re.match(p, text_lower, re.IGNORECASE) for p in SOURCE_LINE_PATTERNS)


def _detect_box_label(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for box_type in BOX_TYPE_MAPPING.keys():
        if text_lower == box_type:
            return box_type
    return None


def _detect_box_title(text: str) -> bool:
    text_lower = text.lower().strip()
    return any(re.match(p, text_lower, re.IGNORECASE) for p in BOX_TITLE_PATTERNS)


def _is_list_item(metadata: dict, text: str) -> bool:
    if metadata.get("has_bullet") or metadata.get("has_numbering") or metadata.get("has_xml_list"):
        return True
    # Mnemonic / lettered list heuristic: single capital letter + tab/space + text
    if re.match(r"^[A-Z]\s+.+", text.strip()):
        return True
    return False


def _list_kind(metadata: dict, text: str) -> Optional[str]:
    if metadata.get("has_bullet"):
        return "bullet"
    if metadata.get("has_numbering"):
        return "numbered"
    if metadata.get("has_xml_list"):
        # Ambiguous XML list; treat as unordered
        return "unordered"
    if re.match(r"^[A-Z]\s+.+", text.strip()):
        return "unordered"
    return None


def _compute_list_positions(paragraphs: list[dict]) -> dict[int, dict]:
    """
    Determine list positions (FIRST/MID/LAST) for list items.
    Uses consecutive list items with the same list key.
    """
    positions: dict[int, dict] = {}
    list_indices = []

    for idx, para in enumerate(paragraphs):
        text = para["text"]
        meta = para.get("metadata", {})
        if _is_list_item(meta, text):
            kind = _list_kind(meta, text)
            key = (
                kind,
                meta.get("indent_level", 0),
                meta.get("context_zone", "BODY"),
                bool(meta.get("is_table")),
                meta.get("table_index"),
                meta.get("box_type"),
            )
            list_indices.append((idx, para["id"], key))
        else:
            list_indices.append((idx, para["id"], None))

    # Walk through and identify runs of list items with same key
    i = 0
    while i < len(list_indices):
        idx, para_id, key = list_indices[i]
        if key is None:
            i += 1
            continue
        run = [para_id]
        j = i + 1
        while j < len(list_indices) and list_indices[j][2] == key:
            run.append(list_indices[j][1])
            j += 1

        if len(run) == 1:
            pos = "FIRST"
            positions[run[0]] = {"list_position": pos, "list_kind": key[0], "list_level": key[1]}
        else:
            positions[run[0]] = {"list_position": "FIRST", "list_kind": key[0], "list_level": key[1]}
            for mid_id in run[1:-1]:
                positions[mid_id] = {"list_position": "MID", "list_kind": key[0], "list_level": key[1]}
            positions[run[-1]] = {"list_position": "LAST", "list_kind": key[0], "list_level": key[1]}

        i = j

    return positions


def extract_blocks(docx_path: str | Path) -> tuple[list[dict], list[dict], dict]:
    """
    Extract blocks with structural features.
    Returns blocks, original paragraphs, and stats.
    """
    paragraphs, stats = extract_document(docx_path)
    list_positions = _compute_list_positions(paragraphs)

    blocks: list[dict] = []

    for para in paragraphs:
        para_id = para["id"]
        text = para["text"]
        meta = dict(para.get("metadata", {}))

        caption_type = _detect_caption_type(text)
        source_line = _detect_source_line(text)
        box_marker = _is_box_marker(text)
        box_label = _detect_box_label(text)
        box_title = _detect_box_title(text)

        list_info = list_positions.get(para_id, {})

        meta.update(
            {
                "caption_type": caption_type,
                "source_line": source_line,
                "box_marker": box_marker,
                "box_label": box_label,
                "box_title": box_title,
                "list_kind": list_info.get("list_kind"),
                "list_position": list_info.get("list_position"),
                "list_level": list_info.get("list_level"),
            }
        )

        blocks.append(
            {
                "id": para_id,
                "para_ids": [para_id],
                "text": text,
                "text_truncated": para["text_truncated"],
                "metadata": meta,
            }
        )

    return blocks, paragraphs, stats
