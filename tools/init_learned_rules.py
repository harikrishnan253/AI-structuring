"""
Initialize an empty learned_rules.json with the expected schema.

Usage:
    python tools/init_learned_rules.py
    python tools/init_learned_rules.py --path backend/data/learned_rules.json --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from processor.rule_learner import initialize_learned_rules_file, resolve_learned_rules_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize learned_rules.json")
    parser.add_argument("--path", type=str, default=None, help="Optional target path")
    parser.add_argument("--force", action="store_true", help="Overwrite existing file")
    args = parser.parse_args()

    target = resolve_learned_rules_path(Path(args.path) if args.path else None)
    created = initialize_learned_rules_file(path=target, force=args.force)
    print(f"initialized learned rules: {created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

