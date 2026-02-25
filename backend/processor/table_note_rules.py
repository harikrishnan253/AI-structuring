"""
Deterministic table-note / footnote classification override.

After classification, validation, marker overrides, box normalization, and
list-run normalization, paragraphs near tables that look like table footnotes
or source notes may still carry incorrect tags (e.g. REF-N, TXT).  This pass
walks classifications, identifies paragraphs near table-related tags whose
text matches table-note patterns, and rewrites them to TFN or TSN.

The validator already handles notes *inside* Word tables (zone == "TABLE"),
so this module only targets paragraphs outside the TABLE zone that are in
the proximity of table content.

Runs after ``normalize_list_runs`` and before ``emit_style_tag_trace``.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table-anchor tags — tags whose presence nearby indicates a table context.
# ---------------------------------------------------------------------------
_TABLE_ANCHOR_TAGS = frozenset({
    "T1", "T11", "T12",       # table captions
    "T", "T2", "T4", "TD",    # table cells
    "TFN", "TFN1", "TSN",     # existing table footnotes / source notes
    "TH1", "TH2", "TH3",     # table headings
})

_NEIGHBOR_RANGE = 10  # search ±10 entries for a table anchor

# ---------------------------------------------------------------------------
# Text patterns
# ---------------------------------------------------------------------------

# Source / attribution patterns — checked FIRST so that "Source: a ..." is
# classified as TSN rather than TFN.
_SOURCE_RE = re.compile(
    r"^(?:"
    r"source\s*:|sources\s*:"
    r"|adapted\s+from"
    r"|reproduced\s+from"
    r"|reprinted\s+from"
    r"|data\s+from"
    r"|courtesy\s+of"
    r"|with\s+permission"
    r")",
    re.IGNORECASE,
)

# Footnote-symbol starters
_FOOTNOTE_SYMBOLS = frozenset("*†‡§‖¶#")

# Lettered footnote: single lowercase letter + whitespace  ("a This value…")
_LETTER_NOTE_RE = re.compile(r"^[a-z]\s")

# Parenthesized letter: "a) Significance…"
_PAREN_LETTER_RE = re.compile(r"^[a-z]\)", re.IGNORECASE)

# Superscript-digit style: "1 Adjusted for…"
_DIGIT_NOTE_RE = re.compile(r"^\d+\s")

# "Note:" / "Notes:" prefix
_NOTE_PREFIX_RE = re.compile(r"^notes?\s*:", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _has_table_anchor(
    classifications: Sequence[dict],
    index: int,
    range_: int = _NEIGHBOR_RANGE,
) -> bool:
    """Return True if any classification within ±*range_* of *index* has a
    table-related tag."""
    n = len(classifications)
    lo = max(0, index - range_)
    hi = min(n, index + range_ + 1)
    for j in range(lo, hi):
        if j == index:
            continue
        tag = classifications[j].get("tag", "")
        if tag in _TABLE_ANCHOR_TAGS or tag.startswith(("TBL", "TFN")):
            return True
    return False


def is_table_note(
    text: str,
    context_zone: str,
    near_table: bool,
) -> tuple[str, str] | None:
    """Determine whether *text* looks like a table note.

    Parameters
    ----------
    text : str
        Paragraph text.
    context_zone : str
        The block's context zone (e.g. ``"BODY"``, ``"TABLE"``).
    near_table : bool
        Whether a table-anchor tag was found in the neighbor window.

    Returns
    -------
    tuple of (tag, reason) or None
        ``("TSN", "table-source-note")`` for attribution / source lines,
        ``("TFN", "table-footnote")`` for lettered / symbol footnotes,
        or *None* if the text does not match.
    """
    if context_zone == "TABLE":
        return None  # validator already handles TABLE zone

    if not near_table:
        return None

    stripped = (text or "").strip()
    if not stripped:
        return None

    # --- Source / attribution (check first) ---
    if _SOURCE_RE.match(stripped):
        return ("TSN", "table-source-note")

    # --- "Note:" / "Notes:" prefix → TFN ---
    if _NOTE_PREFIX_RE.match(stripped):
        return ("TFN", "table-footnote")

    # --- Symbol footnote (*, †, ‡, etc.) ---
    if stripped[0] in _FOOTNOTE_SYMBOLS:
        return ("TFN", "table-footnote")

    # --- Lettered footnote ("a This value…") ---
    if _LETTER_NOTE_RE.match(stripped):
        return ("TFN", "table-footnote")

    # --- Parenthesized letter ("a) Significance…") ---
    if _PAREN_LETTER_RE.match(stripped):
        return ("TFN", "table-footnote")

    # --- Superscript-digit ("1 Adjusted for…") ---
    if _DIGIT_NOTE_RE.match(stripped):
        return ("TFN", "table-footnote")

    return None


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def apply_table_note_overrides(
    blocks: Sequence[dict],
    classifications: list[dict],
    allowed_styles: Iterable[str] | None = None,
) -> list[dict]:
    """Rewrite misclassified table notes to TFN / TSN.

    Parameters
    ----------
    blocks : sequence of dict
        Block list (used for text and metadata lookup).
    classifications : list of dict
        Current classification dicts, in document order.
    allowed_styles : iterable of str, optional
        Valid style tags.  When a rewritten tag is not in this set the
        original tag is kept.  Pass *None* to skip validation.

    Returns
    -------
    list of dict
        New classification list (shallow copies for changed entries,
        originals for unchanged).
    """
    if not classifications:
        return classifications

    block_lookup = {b["id"]: b for b in blocks}
    allowed: set[str] | None = (
        set(allowed_styles) if allowed_styles is not None else None
    )
    result: list[dict] = list(classifications)

    for i, clf in enumerate(classifications):
        tag = clf.get("tag", "")

        # Already a table footnote / source note — don't double-override
        if tag in ("TFN", "TFN1", "TSN") or tag.startswith("TFN-"):
            continue

        block = block_lookup.get(clf.get("id"), {})
        meta = block.get("metadata", {})
        zone = meta.get("context_zone", "BODY")

        # Validator handles TABLE zone (lines 525-537)
        if zone == "TABLE":
            continue

        text = block.get("text", "")
        near_table = _has_table_anchor(classifications, i, _NEIGHBOR_RANGE)

        override = is_table_note(text, zone, near_table)
        if override is None:
            continue

        new_tag, reason = override

        # Safety: don't produce tags that are not in allowed_styles
        if allowed is not None and new_tag not in allowed:
            logger.debug(
                "table-note-override: skip para %s  %s -> %s (not in allowed_styles)",
                clf.get("id"),
                tag,
                new_tag,
            )
            continue

        result[i] = {
            **clf,
            "tag": new_tag,
            "repaired": True,
            "repair_reason": (
                (clf.get("repair_reason") or "") + f",{reason}"
            ).lstrip(","),
        }
        logger.debug(
            "table-note-override: para %s  %s -> %s",
            result[i].get("id"),
            tag,
            new_tag,
        )

    return result
