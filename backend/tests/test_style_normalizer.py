import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.services.style_normalizer import normalize_style


def test_normalize_style_strips_and_collapses_whitespace():
    assert normalize_style("  CN  ") == "CN"
    assert normalize_style("H2   after   H1") == "H2 after H1"


def test_normalize_style_replaces_nbsp():
    nbsp = "\u00A0"
    assert normalize_style(f"CT{nbsp}Title") == "CT Title"


def test_normalize_style_alias_ref_h2():
    assert normalize_style("Ref-H2") == "REFH2"

def test_normalize_style_alias_ref_n_u():
    assert normalize_style("Ref-N") == "REF-N"
    assert normalize_style("Ref-U") == "REF-U"

def test_normalize_style_alias_ref_h2a():
    assert normalize_style("Ref-H2a") == "REFH2a"


def test_normalize_style_vendor_prefix_box_ttl():
    meta = {"box_prefix": "BX4"}
    canonical = normalize_style("EFP_BX-TTL", meta=meta)
    assert canonical == "BX4-TTL"
    assert canonical in {"BX4-TTL"}


def test_normalize_style_vendor_prefix_box_txt():
    meta = {"box_prefix": "BX4"}
    assert normalize_style("EYU_BX-TXT", meta=meta) == "BX4-TXT"

def test_normalize_style_default_box_prefix():
    assert normalize_style("BX-TXT") == "BX4-TXT"

def test_normalize_style_vendor_bx_txt_without_meta():
    assert normalize_style("EFP_BX-TXT") == "BX4-TXT"


def test_normalize_style_strip_illegal_list_suffix():
    assert normalize_style("BX4-TXT-LAST") == "BX4-TXT"
