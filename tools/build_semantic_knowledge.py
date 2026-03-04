#!/usr/bin/env python3
"""
build_semantic_knowledge.py — Offline semantic knowledge extraction from ground truth corpus.

Reads ground_truth.jsonl, allowed_styles.json, style_aliases.json and produces
generalized, data-driven semantic artifacts.  No raw training text is stored.

Outputs
-------
  backend/data/tag_semantics_knowledge.json  — zone priors, family/positional/list/PMI/table/ref
  backend/data/tag_transition_priors.json    — bigram transition matrices
  backend/data/style_alias_candidates.json  — publisher styles needing alias coverage (report only)
  outputs/corpus/tag_rationale_report.md    — human-readable synthesis

Usage
-----
  python3 tools/build_semantic_knowledge.py \\
      --ground-truth   backend/data/ground_truth.jsonl \\
      --allowed-styles backend/config/allowed_styles.json \\
      --style-aliases  backend/config/style_aliases.json \\
      --out-knowledge  backend/data/tag_semantics_knowledge.json \\
      --out-transitions backend/data/tag_transition_priors.json \\
      --out-alias-candidates backend/data/style_alias_candidates.json \\
      --out-report     outputs/corpus/tag_rationale_report.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
TOOL_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Trailing positional suffix
_POSITIONAL_RE = re.compile(r"-(FIRST|MID|LAST|ONLY)$")

# Full list-tag pattern: optional family prefix(es) + BL|NL|UL + optional depth + optional suffix
#   e.g. BL, BL-MID, BL2-FIRST, KT-BL-LAST, EOC-NL2-MID, BX1-UL-ONLY
_LIST_RE = re.compile(
    r"^((?:[A-Z][A-Z0-9]*-)+)?(BL|NL|UL)([23456])?(-(FIRST|MID|LAST|ONLY))?$"
)

# Table body row: TBL, TBL3, TBL-FIRST (suffix already stripped when used)
_TBL_RE = re.compile(r"^TBL([0-9]+)?$")

# Reference family
_REF_RE = re.compile(r"^(REF|SR)(-[A-Z0-9]+)*$")

# Clean-canonical patterns — tags that are already in our semantic tag system
_CLEAN_RES: list[re.Pattern[str]] = [
    re.compile(r"^H[1-6]$"),
    re.compile(r"^(CN|CT|PN|PT|SA|SN|ST)$"),
    re.compile(r"^TXT"),
    re.compile(r"^PMI$"),
    re.compile(r"^TBL"),
    re.compile(r"^T[0-9FHSN]?N?$"),
    re.compile(r"^(BL|NL|UL)[23456]?(-FIRST|-MID|-LAST|-ONLY)?$"),
    re.compile(r"^[A-Z][A-Z0-9]*-(BL|NL|UL)"),
    re.compile(r"^(REF|SR)"),
    re.compile(r"^EOC-"),
    re.compile(r"^KT-"),
    re.compile(r"^OBJ-"),
    re.compile(r"^RQ-"),
    re.compile(r"^ANS-"),
    re.compile(r"^(BX|BOX)"),
    re.compile(r"^(FIG|EXT|EQ|DIA|AF|ACK|EPIG|EXER|QUES|ETAB|EFIG)"),
    re.compile(r"^NBX-"),
    re.compile(r"^(CTG_|CO_|FE-|FG-)"),
    re.compile(r"^(SKILL|COMP|CRIT|REFL)"),
]

# Family prefix registry — longest match first
_FAMILY_PREFIXES: list[tuple[str, str]] = sorted(
    [
        ("KT",   "key_terms"),
        ("EOC",  "end_of_chapter"),
        ("OBJ",  "objectives"),
        ("RQ",   "requirements"),
        ("ANS",  "answers"),
        ("EXER", "exercises"),
        ("QUES", "questions"),
        ("DIA",  "dialogue"),
        ("EXT",  "extract"),
        ("EQ",   "equations"),
        ("NBX",  "numbered_box"),
        ("BX",   "box"),
        ("BOX",  "box"),
        ("ETAB", "enhanced_table"),
        ("EFIG", "enhanced_figure"),
        ("AF",   "art_forms"),
        ("ACK",  "acknowledgments"),
        ("SR",   "study_resources"),
        ("COMP", "competency"),
        ("CRIT", "critical_thinking"),
        ("REFL", "reflection"),
        ("SKILL","skill"),
    ],
    key=lambda x: -len(x[0]),  # longest first
)


# ---------------------------------------------------------------------------
# Tag utility helpers
# ---------------------------------------------------------------------------

def strip_positional(tag: str) -> tuple[str, str | None]:
    """Return (base, suffix) where suffix is FIRST/MID/LAST/ONLY or None."""
    m = _POSITIONAL_RE.search(tag)
    if m:
        return tag[: m.start()], m.group(1)
    return tag, None


def is_clean_canonical(tag: str) -> bool:
    """Return True if tag looks like a known semantic canonical (not a raw publisher style)."""
    if not tag or tag == "UNMAPPED":
        return False
    return any(r.match(tag) for r in _CLEAN_RES)


def classify_family(tag: str) -> str:
    """Map a canonical_gold_tag to a semantic family label."""
    if not tag or tag == "UNMAPPED":
        return "unmapped"

    base, _ = strip_positional(tag)

    # Exact / pattern checks (highest priority)
    if base == "PMI":
        return "marker"
    if re.match(r"^H[1-6]$", base):
        return "heading"
    if base in {"CN", "CT", "PN", "PT", "SA", "SN", "ST", "ChapterNumber", "ChapterTitle"}:
        return "chapter_front_matter"
    if base.startswith("TXT"):
        return "body_text"
    # Table body rows
    if _TBL_RE.match(base):
        return "table_body"
    # Table cell tags: T, T1…T5, TFN, TSN, THDR
    if re.match(r"^T[0-9FHSN]?N?$", base) or base == "THDR":
        return "table_cell"
    # References / back-matter
    if _REF_RE.match(base):
        return "references"
    # FIG / caption
    if re.match(r"^(FIG|EFIG|ETAB)", base):
        return "figure_caption"

    # List families — try the full list RE on the base (no suffix)
    list_m = _LIST_RE.match(base)
    if list_m:
        fp = (list_m.group(1) or "").rstrip("-")
        lt = list_m.group(2)
        type_map = {"BL": "bullet_list", "NL": "numbered_list", "UL": "unnumbered_list"}
        base_family = type_map.get(lt, "list")
        if fp:
            for prefix, fname in _FAMILY_PREFIXES:
                if fp == prefix or fp.startswith(prefix):
                    return f"{fname}_{base_family}"
        return base_family

    # Generic family-prefix check (EOC-H1, KT-TTL, OBJ-NL-FIRST, etc.)
    for prefix, fname in _FAMILY_PREFIXES:
        if base == prefix or base.startswith(prefix + "-") or base.startswith(prefix + "_"):
            return fname

    # Publisher / unknown style heuristics (for non-canonical entries)
    b_up = base.upper().replace("_", "-").replace(" ", "-")
    if re.search(r"HEAD[1-6]|HEADING", b_up):
        return "heading"
    if re.search(r"BULLET|BULLET-LIST", b_up):
        return "bullet_list"
    if re.search(r"NUMBER-?LIST|NUMBERLIST", b_up):
        return "numbered_list"
    if re.search(r"PARA|NORMAL|TXT|BODY-?TEXT", b_up):
        return "body_text"
    if re.search(r"REF|REFERENCE", b_up):
        return "references"
    if re.search(r"CHAPTER-?NUM", b_up):
        return "chapter_front_matter"
    if re.search(r"CHAPTER-?TITLE|CHAP-?TTL", b_up):
        return "chapter_front_matter"
    if re.search(r"FIGURE|FIG", b_up):
        return "figure_caption"
    if re.search(r"EOC", b_up):
        return "end_of_chapter"

    return "other"


def extract_list_info(tag: str) -> dict[str, Any] | None:
    """Parse a list tag into {list_type, depth, family_prefix, positional_suffix} or None."""
    m = _LIST_RE.match(tag)
    if not m:
        return None
    fp = (m.group(1) or "").rstrip("-") or None
    lt = m.group(2)
    depth = int(m.group(3)) if m.group(3) else 1
    suffix = m.group(5) or None
    return {"list_type": lt, "depth": depth, "family_prefix": fp, "positional_suffix": suffix}


def _heuristic_canonical(raw_tag: str) -> tuple[str | None, float]:
    """
    Suggest a canonical tag for a publisher-style tag based on name heuristics.

    Returns (suggested_canonical, confidence) where confidence ∈ [0, 1].
    """
    t = raw_tag.upper().replace("_", "-").replace(" ", "-")

    # Explicit list name with positional
    if re.search(r"BULLET", t):
        if "FIRST" in t:
            return "BL-FIRST", 0.90
        if "LAST" in t:
            return "BL-LAST", 0.90
        return "BL-MID", 0.75  # ambiguous without positional
    if re.search(r"NUMBER.?LIST|NUMBEREDLIST", t):
        if "FIRST" in t:
            return "NL-FIRST", 0.88
        if "LAST" in t:
            return "NL-LAST", 0.88
        return "NL-MID", 0.75
    if re.search(r"ALPHA.?LIST|UC.ALPHA|LC.ALPHA|LC.ROMAN|UC.ROMAN", t):
        if "FIRST" in t:
            return "UL-FIRST", 0.80
        if "LAST" in t:
            return "UL-LAST", 0.80
        return "UL-MID", 0.70
    if re.search(r"LIST-PARAGRAPH|LIST.PARA", t):
        return "BL-MID", 0.65

    # Headings
    m = re.search(r"HEAD-?([1-6])$", t)
    if m:
        return f"H{m.group(1)}", 0.92
    if t in ("CHAPTERNUMBER", "CHAPTER-NUMBER", "CHAPTER-NUM"):
        return "CN", 0.92
    if t in ("CHAPTERTITLE", "CHAPTER-TITLE", "CHAPTERTITLE"):
        return "CT", 0.92
    if t in ("CHAPTERAUTHOR",):
        return "CA", 0.85

    # Body text
    if t in ("NORMAL", "BODY-TEXT", "BODYTEXT"):
        return "TXT", 0.85
    if re.search(r"PARA-?FL|FIRST.?LINE|PARAFIRST", t):
        return "TXT-FLUSH", 0.85
    if re.search(r"PARA|PARAGRAPH|TXT", t) and "LIST" not in t and "HEAD" not in t:
        return "TXT", 0.70

    # References
    if re.search(r"REF", t):
        if "ALPHA" in t:
            return "REF-U", 0.85
        if "NUM" in t:
            return "REF-N", 0.85
        return "REF-N", 0.65
    if re.search(r"EOC.?REF|EOC.?NUMER", t):
        return "EOC-REF", 0.80
    if re.search(r"EOC.?NL", t):
        return "EOC-NL-MID", 0.78

    # Figure / caption
    if re.search(r"FIGURE-?LEGEND|FIGURE-?CAP|FIG-?LEG|FIG-?CAP", t):
        return "FIG-LEG", 0.88

    return None, 0.0


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_ground_truth(path: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    bad = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ex = json.loads(line)
                # Normalise zone to uppercase
                z = ex.get("zone", "") or ""
                ex["zone"] = z.upper() if z else "UNKNOWN"
                examples.append(ex)
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"  [warn] {bad} malformed JSONL lines skipped", file=sys.stderr)
    return examples


def load_allowed_styles(path: Path) -> set[str]:
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))


def load_style_aliases(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def build_zone_tag_priors(examples: list[dict]) -> dict[str, Any]:
    """Zone-conditioned tag frequency distributions."""
    zone_tag: dict[str, Counter[str]] = defaultdict(Counter)
    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED":
            continue
        zone_tag[ex.get("zone", "UNKNOWN")][tag] += 1

    result: dict[str, Any] = {}
    for zone, counts in sorted(zone_tag.items()):
        total = sum(counts.values())
        result[zone] = {
            "total": total,
            "unique_tags": len(counts),
            "distribution": {
                tag: {"count": cnt, "frequency": round(cnt / total, 4)}
                for tag, cnt in counts.most_common(40)
            },
        }
    return result


def build_tag_families(examples: list[dict]) -> dict[str, Any]:
    """Family-level groupings with member tag counts, split by clean vs publisher."""
    family_members: dict[str, Counter[str]] = defaultdict(Counter)
    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED":
            continue
        family_members[classify_family(tag)][tag] += 1

    result: dict[str, Any] = {}
    for fam, counts in sorted(
        family_members.items(), key=lambda x: -sum(x[1].values())
    ):
        total = sum(counts.values())
        clean_tags = {t: c for t, c in counts.items() if is_clean_canonical(t)}
        pub_tags = {t: c for t, c in counts.items() if not is_clean_canonical(t)}
        result[fam] = {
            "total_count": total,
            "unique_members": len(counts),
            "clean_canonical_count": sum(clean_tags.values()),
            "publisher_style_count": sum(pub_tags.values()),
            "members_by_count": {t: c for t, c in counts.most_common()},
        }
    return result


def build_positional_suffix_semantics(examples: list[dict]) -> dict[str, Any]:
    """FIRST/MID/LAST/ONLY distributions per base tag (clean canonical only)."""
    base_suffix: dict[str, Counter[str]] = defaultdict(Counter)
    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED" or not is_clean_canonical(tag):
            continue
        base, suffix = strip_positional(tag)
        if suffix:
            base_suffix[base][suffix] += 1

    result: dict[str, Any] = {}
    for base, counts in sorted(
        base_suffix.items(), key=lambda x: -sum(x[1].values())
    ):
        total = sum(counts.values())
        dist = {
            s: {"count": c, "ratio": round(c / total, 4)}
            for s, c in counts.most_common()
        }
        seq = [s for s in ("FIRST", "MID", "LAST", "ONLY") if s in counts]
        result[base] = {
            "total": total,
            "suffix_distribution": dist,
            "typical_sequence": " -> ".join(seq) if len(seq) > 1 else (seq[0] if seq else ""),
            "has_mid": "MID" in counts,
            "mid_dominance": round(counts.get("MID", 0) / total, 4) if total else 0.0,
        }
    return result


def build_list_depth_semantics(examples: list[dict]) -> dict[str, Any]:
    """List depth stratification across BL/NL/UL and family-prefixed variants."""
    by_depth: dict[str, Counter[str]] = defaultdict(Counter)
    family_prefixed: dict[str, Counter[str]] = defaultdict(Counter)

    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED":
            continue
        info = extract_list_info(tag)
        if not info:
            continue
        lt = info["list_type"]
        depth = info["depth"]
        fp = info["family_prefix"]
        by_depth[f"{lt}_depth_{depth}"][tag] += 1
        if fp:
            family_prefixed[f"{fp}:{lt}"][tag] += 1

    return {
        "by_depth": {
            key: {
                "total": sum(c.values()),
                "tags": dict(c.most_common()),
            }
            for key, c in sorted(by_depth.items())
        },
        "family_prefixed_variants": {
            key: {
                "total": sum(c.values()),
                "tags": dict(c.most_common()),
            }
            for key, c in sorted(
                family_prefixed.items(), key=lambda x: -sum(x[1].values())
            )
        },
    }


def build_marker_pmi_semantics(
    examples: list[dict], window: int = 2
) -> dict[str, Any]:
    """PMI context: zone distribution, typical preceding/following tags."""
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for ex in examples:
        by_doc[ex.get("doc_id", "")].append(ex)
    for doc in by_doc.values():
        doc.sort(key=lambda x: x.get("para_index", 0))

    zone_counts: Counter[str] = Counter()
    preceding: Counter[str] = Counter()
    following: Counter[str] = Counter()
    pmi_total = 0

    for doc_exs in by_doc.values():
        for i, ex in enumerate(doc_exs):
            if ex.get("canonical_gold_tag") != "PMI":
                continue
            pmi_total += 1
            zone_counts[ex.get("zone", "UNKNOWN")] += 1
            for j in range(max(0, i - window), i):
                pt = doc_exs[j].get("canonical_gold_tag", "")
                if pt and pt not in ("UNMAPPED", "PMI"):
                    preceding[pt] += 1
            for j in range(i + 1, min(len(doc_exs), i + window + 1)):
                ft = doc_exs[j].get("canonical_gold_tag", "")
                if ft and ft not in ("UNMAPPED", "PMI"):
                    following[ft] += 1

    return {
        "total_pmi": pmi_total,
        "zone_distribution": dict(zone_counts.most_common()),
        "top_preceding_tags": dict(preceding.most_common(15)),
        "top_following_tags": dict(following.most_common(15)),
    }


def build_table_semantics(examples: list[dict]) -> dict[str, Any]:
    """Table tag distributions by zone and tag variant."""
    table_counts: Counter[str] = Counter()
    zone_table: dict[str, Counter[str]] = defaultdict(Counter)

    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED":
            continue
        base, _ = strip_positional(tag)
        is_table = (
            _TBL_RE.match(base)
            or re.match(r"^T[0-9FHSN]?N?$", base)
            or base in {"THDR", "T-DIR"}
        )
        if is_table:
            zone = ex.get("zone", "UNKNOWN")
            table_counts[tag] += 1
            zone_table[zone][tag] += 1

    total = sum(table_counts.values())
    return {
        "total_table_tagged": total,
        "global_distribution": {
            tag: {"count": c, "frequency": round(c / total, 4) if total else 0.0}
            for tag, c in table_counts.most_common()
        },
        "by_zone": {
            zone: {
                "total": sum(counts.values()),
                "distribution": dict(counts.most_common()),
            }
            for zone, counts in sorted(zone_table.items())
        },
    }


def build_reference_semantics(examples: list[dict]) -> dict[str, Any]:
    """Reference and back-matter (REF*/SR*) tag patterns."""
    ref_counts: Counter[str] = Counter()
    zone_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED":
            continue
        base, _ = strip_positional(tag)
        if _REF_RE.match(base) or classify_family(tag) in (
            "references",
            "study_resources",
        ):
            ref_counts[tag] += 1
            zone_counts[ex.get("zone", "UNKNOWN")][tag] += 1

    total = sum(ref_counts.values())
    return {
        "total_reference_tagged": total,
        "global_distribution": dict(ref_counts.most_common(30)),
        "by_zone": {
            zone: dict(counts.most_common())
            for zone, counts in sorted(zone_counts.items())
        },
    }


def build_transition_priors(examples: list[dict]) -> dict[str, Any]:
    """Bigram tag transitions: global and zone-conditioned."""
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if tag not in ("", "UNMAPPED"):
            by_doc[ex.get("doc_id", "")].append(ex)
    for doc in by_doc.values():
        doc.sort(key=lambda x: x.get("para_index", 0))

    global_trans: dict[str, Counter[str]] = defaultdict(Counter)
    zone_trans: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )

    for doc_exs in by_doc.values():
        for i in range(len(doc_exs) - 1):
            cur_tag = doc_exs[i].get("canonical_gold_tag", "")
            nxt_tag = doc_exs[i + 1].get("canonical_gold_tag", "")
            zone = doc_exs[i].get("zone", "UNKNOWN")
            if cur_tag and nxt_tag:
                global_trans[cur_tag][nxt_tag] += 1
                zone_trans[zone][cur_tag][nxt_tag] += 1

    def _normalise(trans_map: dict[str, Counter[str]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for tag, counts in sorted(
            trans_map.items(), key=lambda x: -sum(x[1].values())
        ):
            total = sum(counts.values())
            out[tag] = {
                "total_transitions": total,
                "next_tag_distribution": {
                    t: {"count": c, "probability": round(c / total, 4)}
                    for t, c in counts.most_common(10)
                },
            }
        return out

    return {
        "global_transitions": _normalise(global_trans),
        "zone_conditioned_transitions": {
            zone: _normalise(dict(td))
            for zone, td in sorted(zone_trans.items())
        },
    }


def find_alias_candidates(
    examples: list[dict],
    allowed: set[str],
    aliases: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Identify canonical_gold_tag values that look like publisher styles and
    are not yet covered by style_aliases.json.

    Returns a list of candidate dicts sorted by support (descending).
    """
    tag_count: Counter[str] = Counter()
    tag_docs: dict[str, set[str]] = defaultdict(set)
    tag_zones: dict[str, Counter[str]] = defaultdict(Counter)

    for ex in examples:
        tag = ex.get("canonical_gold_tag", "") or ""
        if not tag or tag == "UNMAPPED":
            continue
        doc_id = ex.get("doc_id", "")
        zone = ex.get("zone", "UNKNOWN")
        tag_count[tag] += 1
        tag_docs[tag].add(doc_id)
        tag_zones[tag][zone] += 1

    candidates: list[dict[str, Any]] = []
    for tag, cnt in tag_count.most_common():
        # Skip if it's already a clean canonical tag
        if is_clean_canonical(tag):
            continue
        # Skip if it's already a KEY in aliases (already handled)
        if tag in aliases:
            continue
        # Skip if it's a VALUE in aliases (it IS a canonical target already)
        # — only skip if it truly looks clean (this check handled by is_clean_canonical)

        suggestion, confidence = _heuristic_canonical(tag)
        ndocs = len(tag_docs[tag])
        zones_dist = dict(tag_zones[tag].most_common())
        candidates.append(
            {
                "raw_style": tag,
                "suggested_canonical": suggestion,
                "confidence": confidence,
                "support": cnt,
                "num_docs": ndocs,
                "seen_in_docs": sorted(tag_docs[tag]),
                "zone_distribution": zones_dist,
                "in_allowed_styles": tag in allowed,
                "recommendation": (
                    "add_alias"
                    if suggestion and confidence >= 0.85
                    else "review_needed"
                ),
            }
        )

    return candidates


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def render_report(
    *,
    knowledge: dict[str, Any],
    transitions: dict[str, Any],
    alias_candidates: list[dict[str, Any]],
    source_path: str,
    total_raw: int,
    total_quality: int,
    generated_at: str,
) -> str:
    lines: list[str] = []

    def h1(s: str) -> None:
        lines.append(f"# {s}\n")

    def h2(s: str) -> None:
        lines.append(f"\n## {s}\n")

    def h3(s: str) -> None:
        lines.append(f"\n### {s}\n")

    def p(s: str) -> None:
        lines.append(s + "\n")

    def tr(*cells: str) -> None:
        lines.append("| " + " | ".join(cells) + " |")

    def sep(*widths: int) -> None:
        lines.append("| " + " | ".join("-" * max(w, 3) for w in widths) + " |")

    h1("Tag Rationale Report")
    p(f"**Generated:** {generated_at}  ")
    p(f"**Source:** `{source_path}`  ")
    p(f"**Total examples (raw):** {total_raw:,}  ")
    p(f"**Quality examples (alignment >= threshold, non-UNMAPPED):** {total_quality:,}  ")
    lines.append("")

    # ── 1. Zone-conditioned tag priors ──────────────────────────────────────
    h2("1. Zone-Conditioned Tag Priors")
    zone_priors: dict = knowledge.get("zone_tag_priors", {})
    for zone, zd in sorted(zone_priors.items()):
        h3(f"Zone: {zone}  ({zd['total']:,} paragraphs, {zd['unique_tags']} unique tags)")
        tr("Rank", "Tag", "Count", "Frequency")
        sep(4, 30, 6, 9)
        for rank, (tag, td) in enumerate(list(zd["distribution"].items())[:20], 1):
            tr(str(rank), f"`{tag}`", str(td["count"]), f"{td['frequency']:.3f}")
        lines.append("")

    # ── 2. Tag family semantics ─────────────────────────────────────────────
    h2("2. Tag Family Semantics")
    families: dict = knowledge.get("tag_families", {})
    tr("Family", "Total", "Unique", "Clean Canonical", "Publisher Styles", "Top Members (<=3)")
    sep(20, 7, 7, 15, 16, 40)
    for fam, fd in sorted(families.items(), key=lambda x: -x[1]["total_count"]):
        top3 = list(fd["members_by_count"].keys())[:3]
        top_str = ", ".join(f"`{t}`" for t in top3)
        tr(
            fam,
            str(fd["total_count"]),
            str(fd["unique_members"]),
            str(fd["clean_canonical_count"]),
            str(fd["publisher_style_count"]),
            top_str,
        )
    lines.append("")

    # ── 3. Positional suffix semantics ──────────────────────────────────────
    h2("3. Positional Suffix Semantics (FIRST / MID / LAST / ONLY)")
    positional: dict = knowledge.get("positional_suffix_semantics", {})
    tr("Base Tag", "Total", "FIRST%", "MID%", "LAST%", "ONLY%", "Sequence")
    sep(20, 6, 7, 6, 6, 6, 30)
    for base, bd in sorted(positional.items(), key=lambda x: -x[1]["total"])[:35]:
        dist = bd["suffix_distribution"]

        def pct(s: str) -> str:
            return f"{dist[s]['ratio']*100:.0f}%" if s in dist else "—"

        tr(
            f"`{base}`",
            str(bd["total"]),
            pct("FIRST"),
            pct("MID"),
            pct("LAST"),
            pct("ONLY"),
            bd.get("typical_sequence", ""),
        )
    lines.append("")

    # ── 4. List depth semantics ─────────────────────────────────────────────
    h2("4. List Depth Semantics")
    list_depth: dict = knowledge.get("list_depth_semantics", {})
    by_depth = list_depth.get("by_depth", {})

    h3("Standard list depths")
    tr("Key", "Total", "Top Tags")
    sep(20, 6, 60)
    for key, kd in sorted(by_depth.items()):
        top3 = ", ".join(f"`{t}`" for t in list(kd["tags"].keys())[:3])
        tr(key, str(kd["total"]), top3)
    lines.append("")

    fp_variants = list_depth.get("family_prefixed_variants", {})
    if fp_variants:
        h3("Family-prefixed list variants")
        tr("Key", "Total", "Top Tags")
        sep(25, 6, 60)
        for key, kd in sorted(fp_variants.items(), key=lambda x: -x[1]["total"]):
            top3 = ", ".join(f"`{t}`" for t in list(kd["tags"].keys())[:3])
            tr(key, str(kd["total"]), top3)
        lines.append("")

    # ── 5. Marker (PMI) semantics ───────────────────────────────────────────
    h2("5. Marker (PMI) Semantics")
    pmi: dict = knowledge.get("marker_pmi_semantics", {})
    p(f"**Total PMI paragraphs:** {pmi.get('total_pmi', 0):,}")
    zone_dist_str = ", ".join(
        f"{z}: {c}" for z, c in pmi.get("zone_distribution", {}).items()
    )
    p(f"**Zone distribution:** {zone_dist_str}")
    pre_tags = ", ".join(
        f"`{t}` ({c})" for t, c in list(pmi.get("top_preceding_tags", {}).items())[:8]
    )
    fol_tags = ", ".join(
        f"`{t}` ({c})" for t, c in list(pmi.get("top_following_tags", {}).items())[:8]
    )
    p(f"**Top preceding tags (within ±2):** {pre_tags}")
    p(f"**Top following tags (within ±2):** {fol_tags}")

    # ── 6. Table semantics ──────────────────────────────────────────────────
    h2("6. Table Semantics")
    table_sem: dict = knowledge.get("table_semantics", {})
    p(f"**Total table-tagged paragraphs:** {table_sem.get('total_table_tagged', 0):,}")
    h3("Global distribution")
    tr("Tag", "Count", "Frequency")
    sep(20, 7, 9)
    for tag, td in list(table_sem.get("global_distribution", {}).items())[:20]:
        tr(f"`{tag}`", str(td["count"]), f"{td['frequency']:.3f}")
    lines.append("")
    for zone, zd in sorted(table_sem.get("by_zone", {}).items()):
        h3(f"Zone: {zone}")
        tr("Tag", "Count")
        sep(20, 7)
        for tag, cnt in list(zd["distribution"].items())[:15]:
            tr(f"`{tag}`", str(cnt))
        lines.append("")

    # ── 7. Reference / back-matter semantics ───────────────────────────────
    h2("7. Reference / Back-Matter Semantics")
    ref_sem: dict = knowledge.get("reference_semantics", {})
    p(f"**Total reference-tagged paragraphs:** {ref_sem.get('total_reference_tagged', 0):,}")
    tr("Tag", "Count")
    sep(25, 7)
    for tag, cnt in list(ref_sem.get("global_distribution", {}).items())[:20]:
        tr(f"`{tag}`", str(cnt))
    lines.append("")

    # ── 8. Transition highlights ────────────────────────────────────────────
    h2("8. Tag Transition Highlights")
    global_trans = transitions.get("global_transitions", {})
    h3("Top 20 most-transitioned tags (global)")
    tr("From Tag", "Total Transitions", "Top 3 Next Tags")
    sep(25, 18, 70)
    sorted_trans = sorted(
        global_trans.items(), key=lambda x: -x[1]["total_transitions"]
    )[:20]
    for tag, td in sorted_trans:
        top3 = list(td["next_tag_distribution"].items())[:3]
        top_str = ", ".join(
            f"`{t}` ({d['probability']:.2f})" for t, d in top3
        )
        tr(f"`{tag}`", str(td["total_transitions"]), top_str)
    lines.append("")

    # ── 9. Style alias candidates ───────────────────────────────────────────
    h2("9. Style Alias Candidates")
    p(
        f"**Total candidates:** {len(alias_candidates)}  "
        f"(publisher styles not yet in `style_aliases.json`)  "
    )
    p("**This section is report-only — do not auto-merge into config.**")

    add_list = [c for c in alias_candidates if c["recommendation"] == "add_alias"]
    review_list = [c for c in alias_candidates if c["recommendation"] == "review_needed"]

    h3(f"Recommended: `add_alias` ({len(add_list)} entries, confidence >= 0.85)")
    if add_list:
        tr("Raw Style", "Suggested Canonical", "Support", "Confidence", "Docs", "Zones")
        sep(30, 22, 8, 10, 5, 20)
        for c in add_list[:35]:
            zones_str = ", ".join(
                f"{z}:{n}" for z, n in list(c["zone_distribution"].items())[:3]
            )
            tr(
                f"`{c['raw_style']}`",
                f"`{c['suggested_canonical']}`",
                str(c["support"]),
                f"{c['confidence']:.2f}",
                str(c["num_docs"]),
                zones_str,
            )
    else:
        p("_None._")
    lines.append("")

    h3(f"Recommended: `review_needed` ({len(review_list)} entries)")
    if review_list:
        tr("Raw Style", "Suggested Canonical", "Support", "Confidence", "Docs")
        sep(30, 22, 8, 10, 5)
        for c in review_list[:40]:
            sugg = f"`{c['suggested_canonical']}`" if c["suggested_canonical"] else "—"
            tr(
                f"`{c['raw_style']}`",
                sugg,
                str(c["support"]),
                f"{c['confidence']:.2f}",
                str(c["num_docs"]),
            )
    else:
        p("_None._")
    lines.append("")

    lines.append("---")
    lines.append(
        f"*Report generated by `build_semantic_knowledge.py` v{TOOL_VERSION}*"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract generalised semantic knowledge from ground_truth.jsonl."
    )
    p.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("backend/data/ground_truth.jsonl"),
        metavar="PATH",
        help="Input ground_truth.jsonl (default: backend/data/ground_truth.jsonl)",
    )
    p.add_argument(
        "--allowed-styles",
        type=Path,
        default=Path("backend/config/allowed_styles.json"),
        metavar="PATH",
        help="Input allowed_styles.json",
    )
    p.add_argument(
        "--style-aliases",
        type=Path,
        default=Path("backend/config/style_aliases.json"),
        metavar="PATH",
        help="Input style_aliases.json",
    )
    p.add_argument(
        "--out-knowledge",
        type=Path,
        default=Path("backend/data/tag_semantics_knowledge.json"),
        metavar="PATH",
        help="Output tag_semantics_knowledge.json",
    )
    p.add_argument(
        "--out-transitions",
        type=Path,
        default=Path("backend/data/tag_transition_priors.json"),
        metavar="PATH",
        help="Output tag_transition_priors.json",
    )
    p.add_argument(
        "--out-alias-candidates",
        type=Path,
        default=Path("backend/data/style_alias_candidates.json"),
        metavar="PATH",
        help="Output style_alias_candidates.json (report only)",
    )
    p.add_argument(
        "--out-report",
        type=Path,
        default=Path("outputs/corpus/tag_rationale_report.md"),
        metavar="PATH",
        help="Output tag_rationale_report.md",
    )
    p.add_argument(
        "--min-alignment",
        type=float,
        default=0.75,
        metavar="FLOAT",
        help="Minimum alignment score for quality filter (default: 0.75)",
    )
    return p.parse_args()


def _write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    size_kb = path.stat().st_size / 1024
    print(f"  Written: {path}  ({size_kb:.1f} KB)")


def main() -> int:
    args = parse_args()

    # ── Load inputs ──────────────────────────────────────────────────────────
    print(f"Loading ground truth: {args.ground_truth}")
    if not args.ground_truth.exists():
        print(f"ERROR: {args.ground_truth} not found.", file=sys.stderr)
        return 1

    all_examples = load_ground_truth(args.ground_truth)
    print(f"  Total examples (raw): {len(all_examples):,}")

    # Quality filter: alignment >= threshold AND non-UNMAPPED
    quality_examples = [
        ex
        for ex in all_examples
        if ex.get("alignment_score", 0) >= args.min_alignment
        and ex.get("canonical_gold_tag", "") not in ("", "UNMAPPED", None)
    ]
    print(
        f"  Quality examples "
        f"(alignment >= {args.min_alignment}, non-UNMAPPED): {len(quality_examples):,}"
    )

    print(f"Loading allowed styles: {args.allowed_styles}")
    allowed: set[str] = (
        load_allowed_styles(args.allowed_styles)
        if args.allowed_styles.exists()
        else set()
    )
    print(f"  {len(allowed):,} styles loaded")

    print(f"Loading style aliases: {args.style_aliases}")
    aliases: dict[str, str] = (
        load_style_aliases(args.style_aliases)
        if args.style_aliases.exists()
        else {}
    )
    print(f"  {len(aliases):,} aliases loaded")

    # ── Extract semantics ─────────────────────────────────────────────────────
    print("\nExtracting semantics from quality examples...")
    generated_at = datetime.now(timezone.utc).isoformat()

    print("  → zone-conditioned tag priors")
    zone_priors = build_zone_tag_priors(quality_examples)

    print("  → tag family semantics")
    tag_families = build_tag_families(quality_examples)

    print("  → positional suffix semantics")
    positional = build_positional_suffix_semantics(quality_examples)

    print("  → list depth semantics")
    list_depth = build_list_depth_semantics(quality_examples)

    print("  → marker PMI semantics")
    pmi_semantics = build_marker_pmi_semantics(quality_examples)

    print("  → table semantics")
    table_semantics = build_table_semantics(quality_examples)

    print("  → reference semantics")
    ref_semantics = build_reference_semantics(quality_examples)

    print("  → transition priors")
    transitions = build_transition_priors(quality_examples)

    # Alias candidates: use all non-UNMAPPED examples (includes publisher styles)
    non_unmapped = [
        ex
        for ex in all_examples
        if ex.get("canonical_gold_tag", "") not in ("", "UNMAPPED", None)
    ]
    print(f"  → alias candidates (all {len(non_unmapped):,} non-UNMAPPED examples)")
    alias_candidates = find_alias_candidates(non_unmapped, allowed, aliases)
    print(f"    Found {len(alias_candidates)} candidates")

    # ── Assemble artifacts ───────────────────────────────────────────────────
    knowledge_artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "generated_at": generated_at,
        "source": str(args.ground_truth),
        "total_examples_raw": len(all_examples),
        "total_examples_quality": len(quality_examples),
        "min_alignment_threshold": args.min_alignment,
        "zone_tag_priors": zone_priors,
        "tag_families": tag_families,
        "positional_suffix_semantics": positional,
        "list_depth_semantics": list_depth,
        "marker_pmi_semantics": pmi_semantics,
        "table_semantics": table_semantics,
        "reference_semantics": ref_semantics,
    }

    transitions_artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "generated_at": generated_at,
        "source": str(args.ground_truth),
        "total_examples_quality": len(quality_examples),
        **transitions,
    }

    alias_artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "generated_at": generated_at,
        "source": str(args.ground_truth),
        "total_non_unmapped": len(non_unmapped),
        "total_candidates": len(alias_candidates),
        "note": (
            "Report only — do not auto-merge into style_aliases.json without manual review."
        ),
        "candidates": alias_candidates,
    }

    # ── Write outputs ────────────────────────────────────────────────────────
    print("\nWriting artifacts...")
    _write_json(knowledge_artifact, args.out_knowledge)
    _write_json(transitions_artifact, args.out_transitions)
    _write_json(alias_artifact, args.out_alias_candidates)

    report_md = render_report(
        knowledge=knowledge_artifact,
        transitions=transitions_artifact,
        alias_candidates=alias_candidates,
        source_path=str(args.ground_truth),
        total_raw=len(all_examples),
        total_quality=len(quality_examples),
        generated_at=generated_at,
    )
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(report_md, encoding="utf-8")
    size_kb = args.out_report.stat().st_size / 1024
    print(f"  Written: {args.out_report}  ({size_kb:.1f} KB)")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\nDone. Artifact summary:")
    print(f"  Zones:                   {len(zone_priors)}")
    print(f"  Tag families:            {len(tag_families)}")
    print(f"  Positional base tags:    {len(positional)}")
    print(
        f"  List depth keys:         {len(list_depth.get('by_depth', {}))}"
        f"  (+{len(list_depth.get('family_prefixed_variants', {}))} family-prefixed)"
    )
    print(f"  PMI paragraphs:          {pmi_semantics['total_pmi']:,}")
    print(f"  Table-tagged:            {table_semantics['total_table_tagged']:,}")
    print(f"  Reference-tagged:        {ref_semantics['total_reference_tagged']:,}")
    print(
        f"  Transition source tags:  {len(transitions_artifact.get('global_transitions', {}))}"
    )
    add_c = sum(1 for c in alias_candidates if c["recommendation"] == "add_alias")
    rev_c = sum(1 for c in alias_candidates if c["recommendation"] == "review_needed")
    print(
        f"  Alias candidates:        {len(alias_candidates)}"
        f"  (add_alias={add_c}, review_needed={rev_c})"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
