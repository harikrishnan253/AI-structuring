"""
Grounded Rule Learner for Document Style Classification

This module learns deterministic if-then rules from manually tagged ground truth documents.

Features:
- Loads pairs of original and manually-tagged documents
- Aligns paragraphs using robust text similarity (difflib.SequenceMatcher)
- Extracts deterministic features (numbering, indentation, formatting, context)
- Learns simple if-then rules
- Stores rules in learned_rules.json
- Provides CLI for training and reporting

Usage:
    python -m processor.rule_learner --train --report
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from difflib import SequenceMatcher
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.jsonl"
LEARNED_RULES_PATH = DATA_DIR / "learned_rules.json"
ALLOWED_STYLES_PATH = Path(__file__).parent.parent / "config" / "allowed_styles.json"


class FeatureExtractor:
    """Extract deterministic features from paragraph text and metadata."""

    # Patterns for numbering detection
    NUMBERED_RE = re.compile(r"^\s*(\d+[\.\)]|\(\d+\)|\[\d+\])\s+")
    LETTERED_RE = re.compile(r"^\s*([a-z][\.\)]|\([a-z]\))\s+", re.IGNORECASE)
    ROMAN_RE = re.compile(r"^\s*([ivxlcdm]+[\.\)]|\([ivxlcdm]+\))\s+", re.IGNORECASE)
    BULLET_RE = re.compile(r"^\s*[\u2022\u25CF\-\*\u2013\u2014]\s+")
    ALL_CAPS_RE = re.compile(r"^[A-Z\s\d\-,.:;!?\'\"]+$")

    def __init__(self):
        self.allowed_styles = self._load_allowed_styles()

    def _load_allowed_styles(self) -> set[str]:
        """Load allowed styles from config."""
        try:
            with ALLOWED_STYLES_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data) if isinstance(data, list) else set()
        except Exception as e:
            logger.warning(f"Failed to load allowed styles: {e}")
            return set()

    def extract_features(self, text: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract deterministic features from paragraph text.

        Args:
            text: Paragraph text
            metadata: Optional metadata dict

        Returns:
            Dictionary of features
        """
        if metadata is None:
            metadata = {}

        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        features = {
            # Text characteristics
            "length": len(text),
            "word_count": len(text.split()),
            "is_empty": len(text_stripped) == 0,
            "is_short": len(text_stripped) < 50,
            "is_long": len(text_stripped) > 500,

            # Numbering patterns
            "has_number_prefix": bool(self.NUMBERED_RE.match(text_stripped)),
            "has_letter_prefix": bool(self.LETTERED_RE.match(text_stripped)),
            "has_roman_prefix": bool(self.ROMAN_RE.match(text_stripped)),
            "has_bullet": bool(self.BULLET_RE.match(text_stripped)),

            # Formatting
            "is_all_caps": bool(self.ALL_CAPS_RE.match(text_stripped)),
            "starts_with_digit": text_stripped[:1].isdigit() if text_stripped else False,
            "ends_with_period": text_stripped.endswith("."),
            "ends_with_colon": text_stripped.endswith(":"),
            "has_citation_year": bool(re.search(r"\b(19|20)\d{2}\b", text)),

            # Content patterns
            "looks_like_heading": self._looks_like_heading(text_stripped),
            "looks_like_caption": text_lower.startswith(("figure", "table", "fig.", "tab.")),
            "looks_like_reference": self._looks_like_reference(text),
            "looks_like_footnote": text_stripped.startswith(("*", "†", "‡")) or bool(re.match(r"^[a-z]\)", text_stripped)),

            # Zone and context from metadata
            "zone": metadata.get("context_zone", "BODY"),
            "is_in_table": metadata.get("context_zone") == "TABLE",
            "is_in_box": metadata.get("context_zone", "").startswith("BOX_"),
            "is_in_back_matter": metadata.get("context_zone") == "BACK_MATTER",
            "list_kind": metadata.get("list_kind"),
            "list_position": metadata.get("list_position"),
        }

        return features

    def _looks_like_heading(self, text: str) -> bool:
        """Check if text looks like a heading."""
        if not text or len(text) > 200:
            return False
        if re.search(r"[.!?]\s*$", text):
            return False
        # Title Case or ALL CAPS
        words = text.split()
        if len(words) < 1:
            return False
        titled = sum(1 for w in words if w and w[0].isupper())
        return titled >= max(1, int(0.6 * len(words)))

    def _looks_like_reference(self, text: str) -> bool:
        """Check if text looks like a reference entry."""
        text_stripped = text.strip()
        if not text_stripped:
            return False
        text_lower = text_stripped.lower()

        # Has numbering or bullet
        if self.NUMBERED_RE.match(text_stripped) or self.BULLET_RE.match(text_stripped):
            return True

        # Has year, DOI, et al, and punctuation
        has_year = bool(re.search(r"\b(19|20)\d{2}\b", text_lower))
        has_doi = "doi" in text_lower
        has_et_al = "et al" in text_lower
        punct_count = text.count(".") + text.count(";") + text.count(":") + text.count(",")

        return (has_year or has_doi or has_et_al) and punct_count >= 2


class DocumentAligner:
    """Align paragraphs between original and manually-tagged documents."""

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize aligner.

        Args:
            similarity_threshold: Minimum similarity score for alignment (0.0-1.0)
        """
        self.similarity_threshold = similarity_threshold

    def align_documents(
        self,
        original_paragraphs: List[Dict[str, Any]],
        tagged_paragraphs: List[Dict[str, Any]]
    ) -> List[Tuple[Optional[Dict], Optional[Dict], float]]:
        """
        Align paragraphs from original and tagged documents.

        Args:
            original_paragraphs: List of paragraphs from original document
            tagged_paragraphs: List of paragraphs from manually-tagged document

        Returns:
            List of (original_para, tagged_para, similarity_score) tuples
        """
        alignments = []

        # Simple greedy alignment: for each original paragraph, find best match in tagged
        used_tagged = set()

        for orig_para in original_paragraphs:
            orig_text = self._normalize_text(orig_para.get("text", ""))

            if not orig_text:
                alignments.append((orig_para, None, 0.0))
                continue

            best_match = None
            best_score = 0.0
            best_idx = None

            for idx, tagged_para in enumerate(tagged_paragraphs):
                if idx in used_tagged:
                    continue

                tagged_text = self._normalize_text(tagged_para.get("text", ""))
                if not tagged_text:
                    continue

                score = SequenceMatcher(None, orig_text, tagged_text).ratio()

                if score > best_score:
                    best_score = score
                    best_match = tagged_para
                    best_idx = idx

            if best_score >= self.similarity_threshold and best_match:
                alignments.append((orig_para, best_match, best_score))
                used_tagged.add(best_idx)
            else:
                alignments.append((orig_para, None, best_score))

        return alignments

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Remove extra whitespace, normalize punctuation
        text = re.sub(r"\s+", " ", text.strip())
        text = text.replace("\u00A0", " ")  # NBSP
        return text.lower()


class RuleLearner:
    """Learn deterministic if-then rules from aligned documents."""

    def __init__(self):
        self.feature_extractor = FeatureExtractor()
        self.aligner = DocumentAligner()
        self.rules: List[Dict[str, Any]] = []
        self.tag_stats: Dict[str, Counter] = defaultdict(Counter)

    def load_ground_truth(self) -> Dict[str, List[Dict]]:
        """
        Load ground truth dataset from ground_truth.jsonl.

        Returns:
            Dictionary mapping doc_id to list of entries
        """
        if not GROUND_TRUTH_PATH.exists():
            logger.error(f"Ground truth file not found: {GROUND_TRUTH_PATH}")
            return {}

        docs = defaultdict(list)
        with GROUND_TRUTH_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                doc_id = entry.get("doc_id", "")
                if doc_id:
                    docs[doc_id].append(entry)

        # Sort by para_index
        for doc_id in docs:
            docs[doc_id].sort(key=lambda x: x.get("para_index", 0))

        logger.info(f"Loaded ground truth: {len(docs)} documents, {sum(len(v) for v in docs.values())} entries")
        return dict(docs)

    def extract_training_examples(
        self,
        ground_truth: Dict[str, List[Dict]]
    ) -> List[Dict[str, Any]]:
        """
        Extract training examples with features and labels from ground truth.

        Args:
            ground_truth: Dictionary of doc_id -> entries

        Returns:
            List of training examples with features and canonical_gold_tag
        """
        examples = []

        for doc_id, entries in ground_truth.items():
            for i, entry in enumerate(entries):
                # Skip UNMAPPED entries
                if entry.get("canonical_gold_tag") == "UNMAPPED":
                    continue

                text = entry.get("text", "")
                gold_tag = entry.get("canonical_gold_tag", "")

                if not text or not gold_tag:
                    continue

                # Extract features
                metadata = {
                    "context_zone": entry.get("zone", "BODY"),
                    "doc_id": doc_id,
                    "para_index": entry.get("para_index", i)
                }
                features = self.feature_extractor.extract_features(text, metadata)

                # Add context features (previous/next tags)
                if i > 0:
                    features["prev_tag"] = entries[i - 1].get("canonical_gold_tag", "")
                else:
                    features["prev_tag"] = "START"

                if i < len(entries) - 1:
                    features["next_tag"] = entries[i + 1].get("canonical_gold_tag", "")
                else:
                    features["next_tag"] = "END"

                examples.append({
                    "features": features,
                    "label": gold_tag,
                    "text": text,
                    "doc_id": doc_id,
                })

                # Update statistics
                for feature_name, feature_value in features.items():
                    if isinstance(feature_value, bool) and feature_value:
                        self.tag_stats[gold_tag][feature_name] += 1

        logger.info(f"Extracted {len(examples)} training examples")
        return examples

    def learn_rules(self, examples: List[Dict[str, Any]], min_support: int = 10, min_confidence: float = 0.8) -> List[Dict[str, Any]]:
        """
        Learn deterministic if-then rules from training examples.

        Args:
            examples: List of training examples
            min_support: Minimum number of examples to support a rule
            min_confidence: Minimum confidence (precision) for a rule

        Returns:
            List of learned rules
        """
        rules = []

        # Group examples by tag
        examples_by_tag = defaultdict(list)
        for ex in examples:
            examples_by_tag[ex["label"]].append(ex)

        # For each tag, find discriminative feature combinations
        for tag, tag_examples in examples_by_tag.items():
            if len(tag_examples) < min_support:
                continue

            # Count feature occurrences
            feature_counts = Counter()
            for ex in tag_examples:
                for feature_name, feature_value in ex["features"].items():
                    if isinstance(feature_value, bool) and feature_value:
                        feature_counts[feature_name] += 1
                    elif isinstance(feature_value, str) and feature_value:
                        feature_counts[f"{feature_name}={feature_value}"] += 1

            # Find high-confidence single-feature rules
            for feature_key, count in feature_counts.most_common():
                if count < min_support:
                    continue

                # Calculate confidence: P(tag | feature)
                total_with_feature = sum(
                    1 for ex in examples
                    if self._feature_matches(ex["features"], feature_key)
                )

                if total_with_feature == 0:
                    continue

                confidence = count / total_with_feature

                if confidence >= min_confidence:
                    rules.append({
                        "condition": feature_key,
                        "predicted_tag": tag,
                        "support": count,
                        "total": total_with_feature,
                        "confidence": confidence,
                    })

        # Sort rules by confidence and support
        rules.sort(key=lambda r: (r["confidence"], r["support"]), reverse=True)

        logger.info(f"Learned {len(rules)} rules")
        self.rules = rules
        return rules

    def _feature_matches(self, features: Dict[str, Any], feature_key: str) -> bool:
        """Check if a feature matches the given key."""
        if "=" in feature_key:
            # Handle feature=value pairs
            feature_name, feature_value = feature_key.split("=", 1)
            return str(features.get(feature_name, "")) == feature_value
        else:
            # Handle boolean features
            return bool(features.get(feature_key, False))

    def apply_rules(self, text: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Apply learned rules to predict tag for given text.

        Args:
            text: Paragraph text
            metadata: Optional metadata dict

        Returns:
            Predicted tag or None if no rule matches
        """
        if not self.rules:
            return None

        if metadata is None:
            metadata = {}

        features = self.feature_extractor.extract_features(text, metadata)

        # Apply rules in order of confidence
        for rule in self.rules:
            if self._feature_matches(features, rule["condition"]):
                return rule["predicted_tag"]

        return None

    def save_rules(self, path: Optional[Path] = None):
        """Save learned rules to JSON file."""
        if path is None:
            path = LEARNED_RULES_PATH

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "rules": self.rules,
            "num_rules": len(self.rules),
            "tag_stats": {tag: dict(stats) for tag, stats in self.tag_stats.items()},
        }

        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.rules)} rules to {path}")

    def load_rules(self, path: Optional[Path] = None):
        """Load rules from JSON file."""
        if path is None:
            path = LEARNED_RULES_PATH

        if not path.exists():
            logger.warning(f"Rules file not found: {path}")
            return

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.rules = data.get("rules", [])
        self.tag_stats = defaultdict(Counter, {
            tag: Counter(stats) for tag, stats in data.get("tag_stats", {}).items()
        })

        logger.info(f"Loaded {len(self.rules)} rules from {path}")

    def generate_report(self) -> str:
        """Generate a human-readable report of learned rules."""
        if not self.rules:
            return "No rules learned yet."

        report_lines = [
            "=" * 80,
            "LEARNED RULES REPORT",
            "=" * 80,
            "",
            f"Total rules: {len(self.rules)}",
            "",
            "Top 50 rules by confidence:",
            "-" * 80,
        ]

        for i, rule in enumerate(self.rules[:50], 1):
            report_lines.append(
                f"{i:3d}. IF {rule['condition']:40s} THEN {rule['predicted_tag']:15s} "
                f"(conf={rule['confidence']:.2%}, support={rule['support']}/{rule['total']})"
            )

        report_lines.extend([
            "",
            "-" * 80,
            "Tag Statistics:",
            "-" * 80,
        ])

        for tag, stats in sorted(self.tag_stats.items(), key=lambda x: sum(x[1].values()), reverse=True)[:20]:
            total = sum(stats.values())
            top_features = stats.most_common(3)
            report_lines.append(f"\n{tag} ({total} examples):")
            for feature, count in top_features:
                report_lines.append(f"  - {feature}: {count} ({count/total:.1%})")

        return "\n".join(report_lines)


def train_rules():
    """Train rule learner on ground truth dataset."""
    logger.info("Starting rule learning...")

    learner = RuleLearner()

    # Load ground truth
    ground_truth = learner.load_ground_truth()
    if not ground_truth:
        logger.error("No ground truth data found. Exiting.")
        return

    # Extract training examples
    examples = learner.extract_training_examples(ground_truth)
    if not examples:
        logger.error("No training examples extracted. Exiting.")
        return

    # Learn rules
    rules = learner.learn_rules(examples, min_support=10, min_confidence=0.8)

    # Save rules
    learner.save_rules()

    # Generate and print report
    report = learner.generate_report()
    print(report)

    logger.info("Rule learning complete!")


def main():
    """CLI entry point for rule learner."""
    import argparse

    parser = argparse.ArgumentParser(description="Grounded Rule Learner for Document Style Classification")
    parser.add_argument("--train", action="store_true", help="Train rules from ground truth")
    parser.add_argument("--report", action="store_true", help="Generate report of learned rules")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if args.train:
        train_rules()
    elif args.report:
        learner = RuleLearner()
        learner.load_rules()
        print(learner.generate_report())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
