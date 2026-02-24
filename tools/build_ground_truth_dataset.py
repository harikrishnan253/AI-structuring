from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANUAL_ZIP = ROOT / "manual tagged files.zip"
DEFAULT_ORG_ZIP = ROOT / "Org files.zip"
DEFAULT_MANUAL_DIR = ROOT / "backend" / "data" / "_gold_manual"
DEFAULT_ORG_DIR = ROOT / "backend" / "data" / "_org"
DEFAULT_OUTPUT = ROOT / "backend" / "data" / "ground_truth.jsonl"
DEFAULT_ALLOWED_STYLES = ROOT / "backend" / "config" / "allowed_styles.json"
DEFAULT_STYLE_ALIASES = ROOT / "backend" / "config" / "style_aliases.json"

INLINE_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
STEM_CLEAN_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class DocPair:
    doc_id: str
    manual_path: Path
    org_path: Path
    pair_method: str


def normalize_paragraph_text(text: str) -> str:
    cleaned = INLINE_TAG_RE.sub(" ", text or "")
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = WS_RE.sub(" ", cleaned).strip().lower()
    return cleaned


def normalize_style_name(name: str) -> str:
    cleaned = (name or "").replace("\u00a0", " ")
    cleaned = WS_RE.sub(" ", cleaned).strip()
    return cleaned


def normalized_stem(stem: str) -> str:
    return STEM_CLEAN_RE.sub("", stem.lower())


def longest_common_stem_len(a: str, b: str) -> int:
    if not a or not b:
        return 0
    match = SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return int(match.size)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_allowed_styles(path: Path) -> set[str]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Allowed styles must be a list: {path}")
    return {normalize_style_name(str(item)) for item in data if normalize_style_name(str(item))}


def load_style_aliases(path: Path) -> dict[str, str]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Style aliases must be an object: {path}")
    aliases: dict[str, str] = {}
    for key, value in data.items():
        k = normalize_style_name(str(key))
        v = normalize_style_name(str(value))
        if k and v:
            aliases[k] = v
    return aliases


def build_casefold_lookup(values: set[str]) -> dict[str, str]:
    by_fold: dict[str, set[str]] = defaultdict(set)
    for value in values:
        by_fold[value.casefold()].add(value)
    resolved: dict[str, str] = {}
    for folded, originals in by_fold.items():
        if len(originals) == 1:
            resolved[folded] = next(iter(originals))
    return resolved


def canonicalize_tag(
    raw_tag: str,
    allowed_styles: set[str],
    style_aliases: dict[str, str],
    allowed_casefold: dict[str, str],
    alias_casefold: dict[str, str],
) -> tuple[str, list[str]]:
    notes: list[str] = []
    cleaned = normalize_style_name(raw_tag)
    if not cleaned:
        return "UNMAPPED", ["empty_manual_style"]

    if cleaned in allowed_styles:
        notes.append("tag_map:direct")
        return cleaned, notes

    alias_target = style_aliases.get(cleaned)
    if alias_target and alias_target in allowed_styles:
        notes.append("tag_map:alias")
        return alias_target, notes

    folded = cleaned.casefold()
    allowed_folded = allowed_casefold.get(folded)
    if allowed_folded:
        notes.append("tag_map:direct_casefold")
        return allowed_folded, notes

    alias_key = alias_casefold.get(folded)
    if alias_key:
        mapped = style_aliases[alias_key]
        mapped_folded = allowed_casefold.get(mapped.casefold(), mapped)
        if mapped in allowed_styles:
            notes.append("tag_map:alias_casefold")
            return mapped, notes
        if mapped_folded in allowed_styles:
            notes.append("tag_map:alias_casefold_to_allowed_casefold")
            return mapped_folded, notes

    notes.append("tag_map:unmapped")
    return "UNMAPPED", notes


def extract_zip(zip_path: Path, target_dir: Path, force: bool = True) -> None:
    if not zip_path.exists():
        raise FileNotFoundError(f"Missing ZIP file: {zip_path}")
    if force and target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            if not member.filename.lower().endswith(".docx"):
                continue
            zf.extract(member, target_dir)


def list_docx_files(root_dir: Path) -> list[Path]:
    return sorted([p for p in root_dir.rglob("*.docx") if p.is_file()])


def pair_docs(manual_files: list[Path], org_files: list[Path]) -> tuple[list[DocPair], list[Path], list[Path]]:
    pairs: list[DocPair] = []
    unmatched_manual = manual_files[:]
    unmatched_org = org_files[:]

    org_by_stem: dict[str, list[Path]] = defaultdict(list)
    for org in org_files:
        org_by_stem[normalized_stem(org.stem)].append(org)

    next_unmatched_manual: list[Path] = []
    for manual in unmatched_manual:
        key = normalized_stem(manual.stem)
        candidates = [c for c in org_by_stem.get(key, []) if c in unmatched_org]
        if len(candidates) == 1:
            org = candidates[0]
            pairs.append(DocPair(doc_id=manual.stem, manual_path=manual, org_path=org, pair_method="exact_stem"))
            unmatched_org.remove(org)
        else:
            next_unmatched_manual.append(manual)

    unmatched_manual = next_unmatched_manual
    final_unmatched_manual: list[Path] = []

    for manual in unmatched_manual:
        manual_key = normalized_stem(manual.stem)
        best_org: Path | None = None
        best_score = (-1, -1.0)

        for org in unmatched_org:
            org_key = normalized_stem(org.stem)
            lcs = longest_common_stem_len(manual_key, org_key)
            ratio = SequenceMatcher(None, manual_key, org_key).ratio()
            score = (lcs, ratio)
            if score > best_score:
                best_score = score
                best_org = org

        if best_org is not None and best_score[0] > 0:
            pairs.append(
                DocPair(
                    doc_id=manual.stem,
                    manual_path=manual,
                    org_path=best_org,
                    pair_method=f"longest_common_stem:{best_score[0]}:{best_score[1]:.3f}",
                )
            )
            unmatched_org.remove(best_org)
        else:
            final_unmatched_manual.append(manual)

    return pairs, final_unmatched_manual, unmatched_org


def read_doc_paragraphs(path: Path, include_style: bool) -> list[dict[str, Any]]:
    doc = Document(path)
    rows: list[dict[str, Any]] = []
    for idx, para in enumerate(doc.paragraphs):
        text = para.text or ""
        row: dict[str, Any] = {
            "index": idx,
            "text": text,
            "clean_text": normalize_paragraph_text(text),
        }
        if include_style:
            style_name = ""
            try:
                if para.style is not None and para.style.name is not None:
                    style_name = str(para.style.name)
            except Exception:
                style_name = ""
            row["style_name"] = style_name
        rows.append(row)
    return rows


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def align_paragraphs(
    org_paragraphs: list[dict[str, Any]],
    manual_paragraphs: list[dict[str, Any]],
) -> tuple[list[int | None], list[float]]:
    org_texts = [p["clean_text"] for p in org_paragraphs]
    manual_texts = [p["clean_text"] for p in manual_paragraphs]
    matcher = SequenceMatcher(None, org_texts, manual_texts, autojunk=False)

    mapping: list[int | None] = [None] * len(org_paragraphs)
    scores: list[float] = [0.0] * len(org_paragraphs)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                oi = i1 + offset
                mj = j1 + offset
                mapping[oi] = mj
                scores[oi] = 1.0
            continue

        if tag == "replace":
            for oi in range(i1, i2):
                best_j: int | None = None
                best_score = 0.0
                for mj in range(j1, j2):
                    s = similarity(org_texts[oi], manual_texts[mj])
                    if s > best_score:
                        best_score = s
                        best_j = mj
                mapping[oi] = best_j
                scores[oi] = best_score if best_j is not None else 0.0
            continue

        if tag == "delete":
            for oi in range(i1, i2):
                mapping[oi] = None
                scores[oi] = 0.0

    return mapping, scores


def detect_zone_labels(org_paragraphs: list[dict[str, Any]]) -> dict[int, str]:
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from app.services.reference_zone import detect_reference_zone

        blocks = [{"id": p["index"], "text": p["text"]} for p in org_paragraphs]
        ref_ids, _, _ = detect_reference_zone(blocks)
        return {p["index"]: ("reference" if p["index"] in ref_ids else "body") for p in org_paragraphs}
    except Exception:
        return {}


def write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def print_summary(
    *,
    pairs: list[DocPair],
    total_rows: int,
    high_quality_rows: int,
    align_threshold: float,
    unmapped_counter: Counter[str],
    per_doc_distribution: dict[str, Counter[str]],
    unmatched_manual: list[Path],
    unmatched_org: list[Path],
) -> None:
    aligned_pct = (100.0 * high_quality_rows / total_rows) if total_rows else 0.0

    print("Ground truth dataset build summary")
    print(f"- Total matched doc pairs: {len(pairs)}")
    print(f"- Total dataset rows: {total_rows}")
    print(f"- Rows aligned >= {align_threshold:.2f}: {high_quality_rows} ({aligned_pct:.2f}%)")

    if unmapped_counter:
        top_unmapped = unmapped_counter.most_common(15)
        formatted = ", ".join(f"{tag}:{count}" for tag, count in top_unmapped)
        print(f"- Top UNMAPPED tags: {formatted}")
    else:
        print("- Top UNMAPPED tags: none")

    print("- Per-doc canonical tag distribution:")
    for doc_id in sorted(per_doc_distribution):
        dist = per_doc_distribution[doc_id]
        top = ", ".join(f"{tag}:{count}" for tag, count in dist.most_common(12))
        print(f"  - {doc_id}: {top}")

    if unmatched_manual:
        print(f"- Unmatched manual docs: {len(unmatched_manual)}")
    if unmatched_org:
        print(f"- Unmatched org docs: {len(unmatched_org)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build paragraph-level gold dataset by aligning manual-tagged DOCX to org DOCX."
    )
    parser.add_argument("--manual-zip", type=Path, default=DEFAULT_MANUAL_ZIP)
    parser.add_argument("--org-zip", type=Path, default=DEFAULT_ORG_ZIP)
    parser.add_argument("--manual-dir", type=Path, default=DEFAULT_MANUAL_DIR)
    parser.add_argument("--org-dir", type=Path, default=DEFAULT_ORG_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allowed-styles", type=Path, default=DEFAULT_ALLOWED_STYLES)
    parser.add_argument("--style-aliases", type=Path, default=DEFAULT_STYLE_ALIASES)
    parser.add_argument("--alignment-threshold", type=float, default=0.85)
    parser.add_argument(
        "--min-aligned-ratio",
        type=float,
        default=0.80,
        help="Fail if fraction of rows with alignment score >= alignment-threshold is below this.",
    )
    parser.add_argument(
        "--max-unmapped-ratio",
        type=float,
        default=0.10,
        help="Fail if fraction of rows with canonical_gold_tag == UNMAPPED exceeds this.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.manual_zip.exists():
        print(f"Missing manual ZIP: {args.manual_zip}", file=sys.stderr)
        return 1
    if not args.org_zip.exists():
        print(f"Missing org ZIP: {args.org_zip}", file=sys.stderr)
        return 1

    allowed_styles = load_allowed_styles(args.allowed_styles)
    style_aliases = load_style_aliases(args.style_aliases)
    allowed_casefold = build_casefold_lookup(allowed_styles)
    alias_casefold = {k.casefold(): k for k in style_aliases}

    extract_zip(args.manual_zip, args.manual_dir, force=True)
    extract_zip(args.org_zip, args.org_dir, force=True)

    manual_files = list_docx_files(args.manual_dir)
    org_files = list_docx_files(args.org_dir)
    pairs, unmatched_manual, unmatched_org = pair_docs(manual_files, org_files)

    if not pairs:
        print("No document pairs were matched.", file=sys.stderr)
        return 1

    rows: list[dict[str, Any]] = []
    high_quality_rows = 0
    unmapped_rows = 0
    unmapped_counter: Counter[str] = Counter()
    per_doc_distribution: dict[str, Counter[str]] = defaultdict(Counter)

    for pair in pairs:
        org_paragraphs = read_doc_paragraphs(pair.org_path, include_style=False)
        manual_paragraphs = read_doc_paragraphs(pair.manual_path, include_style=True)
        mapping, scores = align_paragraphs(org_paragraphs, manual_paragraphs)
        zone_by_index = detect_zone_labels(org_paragraphs)

        for i, org_para in enumerate(org_paragraphs):
            manual_idx = mapping[i]
            score = float(scores[i])
            notes = [f"pair_method:{pair.pair_method}"]

            if manual_idx is None:
                gold_tag = ""
                canonical_gold_tag = "UNMAPPED"
                notes.append("alignment:no_manual_match")
                unmapped_counter["[NO_MANUAL_MATCH]"] += 1
            else:
                manual_para = manual_paragraphs[manual_idx]
                gold_tag = str(manual_para.get("style_name", ""))
                canonical_gold_tag, tag_notes = canonicalize_tag(
                    gold_tag,
                    allowed_styles,
                    style_aliases,
                    allowed_casefold,
                    alias_casefold,
                )
                notes.extend(tag_notes)
                notes.append(f"manual_para_index:{manual_idx}")
                if canonical_gold_tag == "UNMAPPED":
                    style_key = normalize_style_name(gold_tag) or "[EMPTY_STYLE]"
                    unmapped_counter[style_key] += 1

            if score >= args.alignment_threshold:
                high_quality_rows += 1
            if canonical_gold_tag == "UNMAPPED":
                unmapped_rows += 1

            per_doc_distribution[pair.doc_id][canonical_gold_tag] += 1
            zone = zone_by_index.get(org_para["index"])
            if zone:
                notes.append(f"zone:{zone}")

            row = {
                "doc_id": pair.doc_id,
                "para_index": org_para["index"],
                "text": org_para["text"],
                "gold_tag": gold_tag,
                "canonical_gold_tag": canonical_gold_tag,
                "alignment_score": round(score, 4),
                "notes": "; ".join(notes),
                "zone": zone,
            }
            rows.append(row)

    write_jsonl(rows, args.output)

    total_rows = len(rows)
    print_summary(
        pairs=pairs,
        total_rows=total_rows,
        high_quality_rows=high_quality_rows,
        align_threshold=args.alignment_threshold,
        unmapped_counter=unmapped_counter,
        per_doc_distribution=per_doc_distribution,
        unmatched_manual=unmatched_manual,
        unmatched_org=unmatched_org,
    )

    aligned_ratio = (high_quality_rows / total_rows) if total_rows else 0.0
    unmapped_ratio = (unmapped_rows / total_rows) if total_rows else 1.0

    failed = False
    if aligned_ratio < args.min_aligned_ratio:
        print(
            (
                f"Alignment quality gate failed: aligned_ratio={aligned_ratio:.4f} "
                f"< min_aligned_ratio={args.min_aligned_ratio:.4f}"
            ),
            file=sys.stderr,
        )
        failed = True

    if unmapped_ratio > args.max_unmapped_ratio:
        print(
            (
                f"Unmapped gate failed: unmapped_ratio={unmapped_ratio:.4f} "
                f"> max_unmapped_ratio={args.max_unmapped_ratio:.4f}"
            ),
            file=sys.stderr,
        )
        failed = True

    if failed:
        return 2

    print(f"Wrote dataset: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
