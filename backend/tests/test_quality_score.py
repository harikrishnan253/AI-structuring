import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.services.quality_score import score_document


def _make_blocks(total, txt_count=0, conf=0.95):
    blocks = []
    for i in range(total):
        tag = "TXT" if i < txt_count else "H1"
        blocks.append(
            {
                "id": i + 1,
                "text": f"Para {i+1}",
                "tag": tag,
                "confidence": conf,
                "metadata": {"context_zone": "BODY"},
            }
        )
    return blocks


def test_score_pass():
    blocks = _make_blocks(100, txt_count=10)
    score, metrics, action = score_document(blocks, {"TXT", "H1"})
    assert action == "PASS"
    assert score >= 85


def test_score_retry():
    blocks = _make_blocks(100, txt_count=30)
    score, metrics, action = score_document(blocks, {"TXT", "H1"})
    assert action == "RETRY"


def test_score_review_low():
    blocks = _make_blocks(100, txt_count=80)
    score, metrics, action = score_document(blocks, {"TXT", "H1"})
    assert action == "REVIEW"


def test_unknown_style_raises():
    blocks = _make_blocks(10, txt_count=0)
    blocks[0]["tag"] = "NOT-A-STYLE"
    try:
        score_document(blocks, {"TXT", "H1"})
    except ValueError:
        assert True
    else:
        assert False, "Expected ValueError for unknown styles"
