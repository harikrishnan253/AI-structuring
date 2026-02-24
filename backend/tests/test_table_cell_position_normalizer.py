import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from processor.table_cell_position_normalizer import normalize_table_cell_positions


def _block(bid, row, cell, *, has_xml_list=False, text="x"):
    return {
        "id": bid,
        "text": text,
        "metadata": {
            "context_zone": "TABLE",
            "table_index": 0,
            "row_index": row,
            "cell_index": cell,
            "para_in_cell": 0,
            "has_xml_list": has_xml_list,
            "has_bullet": False,
            "has_numbering": False,
        },
    }


def test_normalizes_contiguous_table_column_list_rows_to_tbl_positions():
    blocks = [
        _block(1, 0, 0, has_xml_list=False, text="Header"),
        _block(2, 1, 0, has_xml_list=True, text="First bullet-like row"),
        _block(3, 2, 0, has_xml_list=True, text="Second bullet-like row"),
        _block(4, 3, 0, has_xml_list=True, text="Third bullet-like row"),
        _block(5, 4, 0, has_xml_list=False, text="Non-list row"),
    ]
    clfs = [
        {"id": 1, "tag": "T2", "confidence": 95},
        {"id": 2, "tag": "T4", "confidence": 70},
        {"id": 3, "tag": "T4", "confidence": 70},
        {"id": 4, "tag": "T4", "confidence": 70},
        {"id": 5, "tag": "T", "confidence": 95},
    ]

    out = normalize_table_cell_positions(clfs, blocks)
    tags = {c["id"]: c["tag"] for c in out}

    assert tags[1] == "T2"
    assert tags[2] == "TBL-FIRST"
    assert tags[3] == "TBL-MID"
    assert tags[4] == "TBL-LAST"
    assert tags[5] == "T"

