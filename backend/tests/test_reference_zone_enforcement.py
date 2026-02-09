import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from processor.validator import validate_and_repair


def test_reference_zone_numbered_to_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "1. Smith et al. 2019.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "UL-MID", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_unnumbered_to_ref_u():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "Scholle SH et al. 2019. Journal.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "BL-FIRST", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-U"


def test_reference_zone_author_line_ref_u():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "Doe J, Smith A. Title.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-U"


def test_reference_zone_numbered_bullet_to_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "1. • Some ref", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_non_reference_sentence_unchanged():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "This chapter discusses methods.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "TXT", "H1"})
    assert repaired[1]["tag"] == "TXT"


def test_reference_zone_bracket_numbered_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "[12] Doe et al. 2020.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "UL-MID", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_paren_numbered_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "(12) Doe et al. 2020.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_numbered_paren_suffix_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "12) Doe et al. 2020.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_plain_number_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "12 Doe et al. 2020.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_bullet_number_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "• 12 Doe et al. 2020.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "UL-MID", "confidence": 0.8},
        {"id": 2, "tag": "UL-MID", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_ul_to_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "(2) Author. Title.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "UL-MID", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"
    assert not repaired[1]["tag"].startswith(("UL-", "BL-"))


def test_reference_zone_bullet_entry_to_ref_u():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "• Author. Title.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "UL-MID", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-U"


def test_reference_zone_heading_ref_h2():
    blocks = [
        {"id": 1, "text": "<Ref-H2> References", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H2", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REFH2"})
    assert repaired[0]["tag"] == "REFH2"


def test_reference_zone_three_digit_numbered_to_ref_n():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "551. Author et al. 2020.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "TXT", "confidence": 0.7},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-N"


def test_reference_zone_em_dash_bullet_to_ref_u():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "— Author. Title.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "BL-MID", "confidence": 0.7},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-U"


def test_reference_zone_bl_mid_maps_to_ref_u():
    blocks = [
        {"id": 1, "text": "References", "metadata": {"is_reference_zone": True}},
        {"id": 2, "text": "Author. Title.", "metadata": {"is_reference_zone": True}},
    ]
    classifications = [
        {"id": 1, "tag": "H1", "confidence": 0.95},
        {"id": 2, "tag": "BL-MID", "confidence": 0.8},
    ]
    repaired = validate_and_repair(classifications, blocks, allowed_styles={"REF-N", "REF-U", "H1"})
    assert repaired[1]["tag"] == "REF-U"
    assert not repaired[1]["tag"].startswith(("UL-", "BL-"))
