"""Style name normalization utilities."""

from __future__ import annotations

import re
import json
from pathlib import Path


NBSP = "\u00A0"
ALIASES_PATH = Path(__file__).resolve().parents[2] / "config" / "style_aliases.json"
VENDOR_PREFIX_RE = re.compile(r"^[A-Z]{2,}_(.+)$")
LIST_SUFFIXES = ("-FIRST", "-MID", "-LAST")
LIST_BASES = {"BL", "NL", "UL", "TBL", "TNL", "TUL"}
DEFAULT_BOX_PREFIX = "BX4"
VENDOR_BX_RE = re.compile(r"^[A-Z]{2,}[-_]?BX[-_](.+)$")


def _load_aliases() -> dict[str, str]:
    if not ALIASES_PATH.exists():
        return {}
    with ALIASES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


_ALIASES = _load_aliases()


def normalize_style(name: str, meta: dict | None = None) -> str:
    if name is None:
        return ""
    text = str(name).strip().replace(NBSP, " ")
    # Collapse internal whitespace
    text = re.sub(r"\s+", " ", text)
    # BX-style normalization (keep separate from general vendor prefixes)
    if "BX" in text:
        # Normalize underscores to dashes for BX tags
        text = text.replace("_", "-")
        bx_match = VENDOR_BX_RE.match(text)
        if bx_match:
            text = f"{DEFAULT_BOX_PREFIX}-{bx_match.group(1)}"
        elif text.startswith("BX-"):
            text = f"{DEFAULT_BOX_PREFIX}-{text[3:]}"
        text = text.upper()

    # Strip vendor prefixes like EFP_, EYU_, etc. (non-BX)
    if not re.match(r"^SK_H[1-6]$", text):
        vendor_match = VENDOR_PREFIX_RE.match(text)
        if vendor_match:
            text = vendor_match.group(1)
    # Apply explicit aliases
    text = _ALIASES.get(text, text)

    # Apply box prefix expansion if provided
    if text.startswith("BX-"):
        box_prefix = None
        if meta and isinstance(meta, dict):
            box_prefix = meta.get("box_prefix")
        if not box_prefix:
            box_prefix = DEFAULT_BOX_PREFIX
        text = f"{box_prefix}-{text[3:]}"

    # Remove illegal list-position suffixes on non-list bases
    for suffix in LIST_SUFFIXES:
        if text.endswith(suffix):
            base = text[: -len(suffix)]
            if base not in LIST_BASES and not base.endswith(("-BL", "-NL", "-UL", "-TBL", "-TNL", "-TUL")):
                text = base
            break

    return text
