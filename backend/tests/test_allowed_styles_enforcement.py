import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from processor.validator import validate_and_repair


def test_high_confidence_allowed_tag_is_preserved():
    blocks = [
        {"id": 1, "text": "Suggested Reading", "metadata": {"context_zone": "BACK_MATTER", "list_kind": "unordered", "list_position": "FIRST"}},
    ]
    classifications = [
        {"id": 1, "tag": "SR", "confidence": 0.95},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"SR", "TXT"})
    assert repaired[0]["tag"] == "SR"


def test_not_allowed_tag_downgrades_to_txt():
    blocks = [
        {"id": 1, "text": "Some text", "metadata": {"context_zone": "BODY"}},
    ]
    classifications = [
        {"id": 1, "tag": "NOT-A-STYLE", "confidence": 0.95},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"TXT"})
    assert repaired[0]["tag"] == "TXT"
    assert repaired[0].get("repair_reason") is not None
