"""
List-run position normalization.

After classification, validation, marker overrides, and box normalization,
the tag sequence may still have broken position continuity within list runs.
This pass walks classifications in document order, identifies contiguous runs
of same-family list tags, and rewrites their position suffixes to form correct
FIRST / MID / LAST sequences.

Runs after ``normalize_box_styles`` and before ``emit_style_tag_trace``.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

_POSITION_RE = re.compile(r"^(.+)-(FIRST|MID|LAST)$")


def _list_family(tag: str) -> str | None:
    """Extract the family prefix from a position-suffixed tag.

    Returns the family string (e.g. ``"BL"``, ``"BX1-BL"``) or *None* if
    *tag* does not carry a ``-FIRST``, ``-MID``, or ``-LAST`` suffix.

    >>> _list_family("BL-FIRST")
    'BL'
    >>> _list_family("BX1-BL-MID")
    'BX1-BL'
    >>> _list_family("TXT")
    """
    m = _POSITION_RE.match(tag or "")
    return m.group(1) if m else None


def normalize_list_runs(
    blocks: Sequence[dict],
    classifications: list[dict],
    allowed_styles: Iterable[str] | None = None,
) -> list[dict]:
    """Rewrite list-position suffixes so contiguous same-family runs
    have correct FIRST / MID / LAST continuity.

    Parameters
    ----------
    blocks : sequence of dict
        Block list (unused for data, but maintains document ordering
        contract with the rest of the pipeline).
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

    allowed: set[str] | None = (
        set(allowed_styles) if allowed_styles is not None else None
    )

    # Build result list — start as references to originals
    result: list[dict] = list(classifications)

    # Extract family for every entry
    families: list[str | None] = [
        _list_family(c.get("tag", "")) for c in classifications
    ]

    # Walk and process runs
    i = 0
    n = len(classifications)

    while i < n:
        family = families[i]
        if family is None:
            i += 1
            continue

        # Collect contiguous entries with the same family
        j = i + 1
        while j < n and families[j] == family:
            j += 1

        run_len = j - i

        # Assign correct positions
        for k in range(i, j):
            if run_len == 1:
                desired = "FIRST"
            elif k == i:
                desired = "FIRST"
            elif k == j - 1:
                desired = "LAST"
            else:
                desired = "MID"

            new_tag = f"{family}-{desired}"
            old_tag = classifications[k].get("tag", "")

            if new_tag == old_tag:
                continue  # already correct

            if allowed is not None and new_tag not in allowed:
                logger.debug(
                    "list-run-norm: skip para %s  %s -> %s (not in allowed_styles)",
                    classifications[k].get("id"),
                    old_tag,
                    new_tag,
                )
                continue  # safety: don't produce invalid tags

            result[k] = {
                **classifications[k],
                "tag": new_tag,
                "repaired": True,
                "repair_reason": (
                    (classifications[k].get("repair_reason") or "")
                    + ",list-run-norm"
                ).lstrip(","),
            }
            logger.debug(
                "list-run-norm: para %s  %s -> %s",
                result[k].get("id"),
                old_tag,
                new_tag,
            )

        i = j  # advance past this run

    return result
