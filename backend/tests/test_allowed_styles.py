import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.services.allowed_styles import load_allowed_styles


def test_allowed_styles_loads_and_filters_invalid_entries():
    styles = load_allowed_styles()
    assert "PMI" in styles
    assert "H2 after H1" not in styles
    assert "H3 after H2" not in styles
    assert "NL-MID following L1" not in styles
