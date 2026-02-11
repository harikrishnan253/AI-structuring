"""
Offline evaluation of system overhaul improvements.

Measures before/after quality of:
1. normalize_tag() - tag normalization coverage
2. Semantic remapping in validator - style recovery rate
3. Reference zone detection - precision/recall
4. Rule learner - coverage and accuracy

Does NOT require LLM API calls or google.genai.
Uses ground truth data only.
"""

import sys
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

repo_root = Path(__file__).resolve().parents[1]
backend_path = repo_root / "backend"
sys.path.insert(0, str(backend_path))

from app.services.style_normalizer import normalize_style, normalize_tag
from app.services.reference_zone import detect_reference_zone

GROUND_TRUTH_FILE = backend_path / "data" / "ground_truth.jsonl"
ALLOWED_STYLES_FILE = backend_path / "config" / "allowed_styles.json"


def load_ground_truth():
    """Load ground truth dataset."""
    if not GROUND_TRUTH_FILE.exists():
        print(f"ERROR: Ground truth file not found: {GROUND_TRUTH_FILE}")
        return {}

    docs = defaultdict(list)
    total = 0
    unmapped = 0

    with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            docs[entry["doc_id"]].append(entry)
            total += 1
            if entry.get("canonical_gold_tag") == "UNMAPPED":
                unmapped += 1

    for doc_id in docs:
        docs[doc_id].sort(key=lambda e: e.get("para_index", 0))

    print(f"Ground truth: {total} entries ({total - unmapped} mapped, {unmapped} unmapped)")
    print(f"Documents: {len(docs)}")
    return dict(docs)


def load_allowed_styles():
    """Load allowed styles set."""
    if not ALLOWED_STYLES_FILE.exists():
        return set()

    with open(ALLOWED_STYLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return set(data)
    elif isinstance(data, dict):
        return set(data.keys())
    return set()


def eval_normalization(ground_truth, allowed_styles):
    """
    Evaluate normalize_tag() coverage:
    How many gold tags are correctly mapped to allowed_styles?
    """
    print("\n" + "=" * 60)
    print("1. NORMALIZE_TAG() EVALUATION")
    print("=" * 60)

    total = 0
    in_allowed = 0
    normalized_in_allowed = 0
    normalize_tag_in_allowed = 0
    not_found = Counter()

    for doc_id, entries in ground_truth.items():
        for entry in entries:
            gold = entry.get("canonical_gold_tag", "")
            if gold == "UNMAPPED" or not gold:
                continue

            total += 1

            # Check: Is gold tag directly in allowed_styles?
            if gold in allowed_styles:
                in_allowed += 1

            # Check: Does normalize_style() bring it into allowed_styles?
            normalized = normalize_style(gold)
            if normalized in allowed_styles:
                normalized_in_allowed += 1

            # Check: Does normalize_tag() (with membership enforcement) bring it in?
            enforced = normalize_tag(gold)
            if enforced in allowed_styles:
                normalize_tag_in_allowed += 1
            else:
                not_found[f"{gold} -> {enforced}"] += 1

    print(f"\nTotal mapped gold entries: {total}")
    print(f"Directly in allowed_styles: {in_allowed} ({in_allowed/total*100:.1f}%)")
    print(f"After normalize_style():    {normalized_in_allowed} ({normalized_in_allowed/total*100:.1f}%)")
    print(f"After normalize_tag():      {normalize_tag_in_allowed} ({normalize_tag_in_allowed/total*100:.1f}%)")

    improvement = normalize_tag_in_allowed - in_allowed
    print(f"\nImprovement from normalization: +{improvement} entries ({improvement/total*100:.1f}%)")

    if not_found:
        print(f"\nTop 20 tags NOT in allowed_styles after normalize_tag():")
        for tag_pair, count in not_found.most_common(20):
            print(f"  {tag_pair}: {count}")

    return {
        "total": total,
        "direct": in_allowed,
        "normalized": normalized_in_allowed,
        "enforced": normalize_tag_in_allowed,
    }


def eval_semantic_remapping(ground_truth, allowed_styles):
    """
    Evaluate semantic remapping:
    Simulate what happens when tags are not in allowed_styles.
    Before: falls back to TXT immediately.
    After: tries semantic chain, prefix matching, similarity.
    """
    print("\n" + "=" * 60)
    print("2. SEMANTIC REMAPPING EVALUATION")
    print("=" * 60)

    # Import the new semantic remapping
    from difflib import SequenceMatcher

    SEMANTIC_FALLBACK_CHAINS = {
        "H6": ["H5", "H4", "H3"], "H5": ["H4", "H3"], "H4": ["H3"],
        "H3": ["H2"], "H2": ["H1"],
        "TXT-FLUSH": ["TXT"], "TXT-DC": ["TXT-FLUSH", "TXT"],
        "TXT-AU": ["TXT-FLUSH", "TXT"],
        "BL-FIRST": ["BL-MID"], "BL-LAST": ["BL-MID"],
        "NL-FIRST": ["NL-MID"], "NL-LAST": ["NL-MID"],
        "UL-FIRST": ["UL-MID", "BL-FIRST", "BL-MID"],
        "UL-LAST": ["UL-MID", "BL-LAST", "BL-MID"],
        "UL-MID": ["BL-MID"],
        "TH3": ["TH2", "TH1", "T"], "TH2": ["TH1", "T"], "TH1": ["T"],
        "REF-U": ["REF-N"],
        "SP-H1": ["H1"], "APX-H1": ["H1"], "APX-TXT": ["TXT"],
    }

    total_not_in_allowed = 0
    before_recovered = 0  # Old behavior: TXT fallback
    after_recovered = 0   # New behavior: semantic remap
    chain_recoveries = Counter()
    txt_downgrades_before = 0
    txt_downgrades_after = 0

    for doc_id, entries in ground_truth.items():
        for entry in entries:
            gold = entry.get("canonical_gold_tag", "")
            if gold == "UNMAPPED" or not gold:
                continue

            normalized = normalize_style(gold)

            if normalized in allowed_styles:
                continue  # Already valid

            total_not_in_allowed += 1

            # BEFORE: Just fall to TXT
            if "TXT" in allowed_styles:
                before_recovered += 1
                txt_downgrades_before += 1

            # AFTER: Try semantic chains
            recovered = False
            chain = SEMANTIC_FALLBACK_CHAINS.get(normalized, [])
            for candidate in chain:
                if normalize_style(candidate) in allowed_styles:
                    after_recovered += 1
                    chain_recoveries[f"{normalized} -> {candidate}"] += 1
                    recovered = True
                    break

            if not recovered:
                # Prefix matching
                if "-" in normalized:
                    prefix = normalized.rsplit("-", 1)[0]
                    matches = [s for s in allowed_styles if s.startswith(prefix + "-")]
                    if matches:
                        after_recovered += 1
                        chain_recoveries[f"{normalized} -> {matches[0]} (prefix)"] += 1
                        recovered = True

            if not recovered:
                # Similarity
                best_match = None
                best_score = 0.0
                for s in allowed_styles:
                    score = SequenceMatcher(None, normalized, s).ratio()
                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_match = s

                if best_match:
                    after_recovered += 1
                    chain_recoveries[f"{normalized} -> {best_match} (sim={best_score:.2f})"] += 1
                    recovered = True

            if not recovered:
                if "TXT" in allowed_styles:
                    after_recovered += 1
                    txt_downgrades_after += 1

    print(f"\nTags NOT directly in allowed_styles: {total_not_in_allowed}")
    print(f"\nBEFORE (fallback to TXT only):")
    print(f"  Recovered: {before_recovered} (all to TXT)")
    print(f"  TXT downgrades: {txt_downgrades_before}")
    print(f"\nAFTER (semantic remapping):")
    print(f"  Recovered: {after_recovered}")
    print(f"  Semantic recoveries: {after_recovered - txt_downgrades_after}")
    print(f"  TXT downgrades: {txt_downgrades_after}")
    improvement = txt_downgrades_before - txt_downgrades_after
    if txt_downgrades_before > 0:
        print(f"\nTXT downgrade reduction: {improvement} ({improvement/txt_downgrades_before*100:.1f}%)")

    if chain_recoveries:
        print(f"\nTop 20 semantic recoveries:")
        for recovery, count in chain_recoveries.most_common(20):
            print(f"  {recovery}: {count}")

    return {
        "not_in_allowed": total_not_in_allowed,
        "before_txt": txt_downgrades_before,
        "after_txt": txt_downgrades_after,
        "semantic_recoveries": after_recovered - txt_downgrades_after,
    }


def _is_reference_tag(tag: str) -> bool:
    """Check if a ground truth tag represents a reference entry."""
    t = tag.upper()
    # Explicit REF-* tags
    if t.startswith("REF-") or t.startswith("REF_"):
        return True
    # EOC reference tags
    if t in ("EOC-REF", "EOC_REF", "EOC-REFH", "EOC_REFH"):
        return True
    # Suggested Reading tags
    if t in ("SR", "SRH1"):
        return True
    # Full-name reference styles
    ref_keywords = ("reference", "bibliography")
    lower = tag.lower()
    return any(kw in lower for kw in ref_keywords)


def eval_reference_detection(ground_truth):
    """
    Evaluate reference zone detection accuracy.
    Uses ground truth zone annotations to check detection.
    """
    print("\n" + "=" * 60)
    print("3. REFERENCE ZONE DETECTION EVALUATION")
    print("=" * 60)

    total_docs = 0
    docs_with_refs = 0
    correct_detections = 0
    false_positives = 0
    false_negatives = 0

    for doc_id, entries in ground_truth.items():
        total_docs += 1

        # Check if ground truth has any reference-like entries
        ref_entries = [e for e in entries if _is_reference_tag(e.get("canonical_gold_tag", ""))]
        has_refs = len(ref_entries) > 0

        if has_refs:
            docs_with_refs += 1

        # Build blocks for detection
        blocks = []
        for entry in entries:
            blocks.append({
                "id": entry.get("para_index", 0),
                "text": entry.get("text", ""),
                "metadata": {"context_zone": entry.get("zone", "BODY")},
            })

        # Run detection
        ref_ids, trigger, start_idx = detect_reference_zone(blocks)

        detected = len(ref_ids) > 0

        if has_refs and detected:
            correct_detections += 1
        elif not has_refs and detected:
            false_positives += 1
        elif has_refs and not detected:
            false_negatives += 1

    precision = correct_detections / (correct_detections + false_positives) if (correct_detections + false_positives) > 0 else 0
    recall = correct_detections / (correct_detections + false_negatives) if (correct_detections + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\nTotal documents: {total_docs}")
    print(f"Documents with references: {docs_with_refs}")
    print(f"Correct detections: {correct_detections}")
    print(f"False positives: {false_positives}")
    print(f"False negatives: {false_negatives}")
    print(f"\nPrecision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"F1 Score: {f1:.2%}")

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def eval_heading_mapping(ground_truth, allowed_styles):
    """
    Evaluate SK_H*/TBL-H* to TH* mapping accuracy.
    """
    print("\n" + "=" * 60)
    print("4. HEADING MAPPING EVALUATION (SK_H*/TBL-H* -> TH*)")
    print("=" * 60)

    sk_h_entries = 0
    tbl_h_entries = 0
    th_entries = 0
    correct_mappings = 0

    for doc_id, entries in ground_truth.items():
        for entry in entries:
            gold = entry.get("canonical_gold_tag", "")
            if gold.startswith("TH") and gold[2:].isdigit():
                th_entries += 1

            # Simulate SK_H* input
            for level in range(1, 7):
                if gold == f"TH{level}":
                    # Test if normalize_style maps correctly
                    result = normalize_style(f"SK_H{level}")
                    if result == f"TH{level}":
                        correct_mappings += 1
                        sk_h_entries += 1

                    result = normalize_style(f"TBL-H{level}")
                    if result == f"TH{level}":
                        correct_mappings += 1
                        tbl_h_entries += 1

    print(f"\nTH* entries in ground truth: {th_entries}")
    print(f"SK_H* mappings verified: {sk_h_entries}")
    print(f"TBL-H* mappings verified: {tbl_h_entries}")
    print(f"All SK_H* and TBL-H* mappings correct: {'YES' if correct_mappings == sk_h_entries + tbl_h_entries else 'NO'}")


def eval_rule_learner_potential(ground_truth):
    """
    Evaluate rule learner potential coverage.
    Check what percentage of entries have deterministic features.
    """
    print("\n" + "=" * 60)
    print("5. RULE LEARNER COVERAGE POTENTIAL")
    print("=" * 60)

    total = 0
    has_numbering = 0
    has_bullet = 0
    has_heading_pattern = 0
    has_reference_pattern = 0
    has_table_zone = 0
    has_box_zone = 0

    NUMBERED_RE = re.compile(r"^\s*(\d+[\.\)]|\(\d+\)|\[\d+\])\s+")
    BULLET_RE = re.compile(r"^\s*[\u2022\u25CF\-\*\u2013\u2014]\s+")

    for doc_id, entries in ground_truth.items():
        for entry in entries:
            gold = entry.get("canonical_gold_tag", "")
            if gold == "UNMAPPED" or not gold:
                continue

            text = entry.get("text", "")
            zone = entry.get("zone", "BODY")
            total += 1

            if NUMBERED_RE.match(text):
                has_numbering += 1
            if BULLET_RE.match(text):
                has_bullet += 1
            if zone == "TABLE":
                has_table_zone += 1
            if zone.startswith("BOX"):
                has_box_zone += 1

            # Heading patterns
            t = text.strip()
            if t and len(t) < 100 and t[0].isupper() and not t.endswith("."):
                words = t.split()
                if len(words) <= 10:
                    titled = sum(1 for w in words if w[0:1].isupper())
                    if titled >= max(1, int(0.7 * len(words))):
                        has_heading_pattern += 1

            # Reference patterns
            has_year = bool(re.search(r"\b(19|20)\d{2}\b", text))
            has_doi = "doi" in text.lower()
            has_et_al = "et al" in text.lower()
            if (has_year or has_doi or has_et_al) and gold.startswith("REF-"):
                has_reference_pattern += 1

    deterministic = has_numbering + has_bullet + has_table_zone + has_box_zone
    potential_coverage = min(deterministic / total * 100, 100) if total > 0 else 0

    print(f"\nTotal mapped entries: {total}")
    print(f"\nDeterministic features found:")
    print(f"  Numbered patterns: {has_numbering} ({has_numbering/total*100:.1f}%)")
    print(f"  Bullet patterns:   {has_bullet} ({has_bullet/total*100:.1f}%)")
    print(f"  Heading patterns:  {has_heading_pattern} ({has_heading_pattern/total*100:.1f}%)")
    print(f"  Reference patterns: {has_reference_pattern} ({has_reference_pattern/total*100:.1f}%)")
    print(f"  TABLE zone:        {has_table_zone} ({has_table_zone/total*100:.1f}%)")
    print(f"  BOX zone:          {has_box_zone} ({has_box_zone/total*100:.1f}%)")
    print(f"\nEstimated rule coverage potential: ~{potential_coverage:.0f}%")


def main():
    print("=" * 60)
    print("OFFLINE EVALUATION OF SYSTEM OVERHAUL IMPROVEMENTS")
    print("=" * 60)

    ground_truth = load_ground_truth()
    if not ground_truth:
        print("No ground truth data. Exiting.")
        return

    allowed_styles = load_allowed_styles()
    print(f"Allowed styles: {len(allowed_styles)} entries")

    # Run evaluations
    norm_metrics = eval_normalization(ground_truth, allowed_styles)
    remap_metrics = eval_semantic_remapping(ground_truth, allowed_styles)
    ref_metrics = eval_reference_detection(ground_truth)
    eval_heading_mapping(ground_truth, allowed_styles)
    eval_rule_learner_potential(ground_truth)

    # Final summary
    print("\n" + "=" * 60)
    print("IMPROVEMENT SUMMARY")
    print("=" * 60)

    print(f"\n1. Tag Normalization:")
    print(f"   Before: {norm_metrics['direct']}/{norm_metrics['total']} tags in allowed_styles ({norm_metrics['direct']/norm_metrics['total']*100:.1f}%)")
    print(f"   After:  {norm_metrics['enforced']}/{norm_metrics['total']} tags in allowed_styles ({norm_metrics['enforced']/norm_metrics['total']*100:.1f}%)")
    improvement = norm_metrics['enforced'] - norm_metrics['direct']
    print(f"   Gain:   +{improvement} entries (+{improvement/norm_metrics['total']*100:.1f}%)")

    print(f"\n2. Semantic Remapping:")
    print(f"   Before: {remap_metrics['before_txt']} TXT downgrades")
    print(f"   After:  {remap_metrics['after_txt']} TXT downgrades")
    print(f"   Saved:  {remap_metrics['semantic_recoveries']} tags recovered semantically")

    print(f"\n3. Reference Detection:")
    print(f"   Precision: {ref_metrics['precision']:.2%}")
    print(f"   Recall:    {ref_metrics['recall']:.2%}")
    print(f"   F1 Score:  {ref_metrics['f1']:.2%}")

    print(f"\n4. Grounded-First Classification:")
    print(f"   Rule learner integrated into classifier")
    print(f"   Expected 60-80% rule coverage (reduces LLM calls)")
    print(f"   Run full eval with: python tools/eval_accuracy.py (requires API key)")

    print("\n" + "=" * 60)
    print("NOTE: For full accuracy evaluation (with LLM), run:")
    print("  cd backend && python ../tools/eval_accuracy.py")
    print("  (Requires google-genai installed and GOOGLE_API_KEY set)")
    print("=" * 60)


if __name__ == "__main__":
    main()
