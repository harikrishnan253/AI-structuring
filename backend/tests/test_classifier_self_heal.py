import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from processor.classifier import GeminiClassifier


class DummyResp:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = None


def _make_classifier():
    clf = GeminiClassifier.__new__(GeminiClassifier)
    clf.api_timeout = 1
    clf.max_retries = 1
    clf.retry_delay = 0
    clf.total_input_tokens = 0
    clf.total_output_tokens = 0
    clf.total_tokens = 0
    clf._last_token_usage = {}
    return clf


def test_self_heal_retries_on_invalid():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"BADTAG","confidence":90}]'),
        DummyResp('[{"id":1,"tag":"TXT","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Hello"}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 2
    assert results[0]["tag"] == "TXT"


def test_self_heal_fallback_to_txt_when_still_invalid():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"BADTAG","confidence":90}]'),
        DummyResp('[{"id":1,"tag":"BADTAG2","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Hello"}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 2
    assert results[0]["tag"] == "TXT"


def test_alias_mapping_sk_h_table_to_th_no_downgrade():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"SK_H3","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Header", "metadata": {"context_zone": "TABLE"}}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 1
    assert results[0]["tag"] == "TH3"


def test_alias_mapping_ref_zone_ul_to_ref_n_no_downgrade():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"UL-MID","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [
        {"id": 1, "text": "(2) Author. Title.", "metadata": {"context_zone": "BACK_MATTER", "is_reference_zone": True}}
    ]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 1
    assert results[0]["tag"] == "REF-N"


def test_sanitize_junk_prefixed_tag_to_valid_style():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":": FIG-LEG","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Figure legend", "metadata": {"context_zone": "BACK_MATTER"}}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 1
    assert results[0]["tag"] == "FIG-LEG"


def test_alias_mapping_bibitem_to_ref_u_in_reference_zone():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"BibItem","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Smith J. 2019. Journal.", "metadata": {"is_reference_zone": True}}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 1
    assert results[0]["tag"] in {"REF-U", "REF-N"}


def test_alias_mapping_cout_to_cout1():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"COUT","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Overview", "metadata": {"context_zone": "FRONT_MATTER"}}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 1
    assert results[0]["tag"] in {"COUT-1", "COUT-2"}


def test_alias_mapping_efp_box_to_bx4():
    clf = _make_classifier()
    responses = [
        DummyResp('[{"id":1,"tag":"EFP_BX-TXT","confidence":90}]'),
    ]
    calls = {"n": 0}

    def _gen(_prompt):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r

    clf._generate_content = _gen

    paragraphs = [{"id": 1, "text": "Box text", "metadata": {"context_zone": "BODY", "box_prefix": "BX4"}}]
    results = clf._classify_chunk(paragraphs, "doc", "Academic", "")
    assert calls["n"] == 1
    assert results[0]["tag"] == "BX4-TXT"
