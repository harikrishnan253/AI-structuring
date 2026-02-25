# SESSION SNAPSHOT

**Date:** 2026-02-24
**Session Focus:** Table style accuracy, cell-position normalization, table review highlighting, pipeline bug fixes from runtime logs, and ENA_188122_CH04 DOCX mismatch analysis

---

## Summary

This session addressed production runtime bugs (three fixes from log inspection), a table-style diff analysis identifying 142 per-chapter cell mismatches, four targeted table-accuracy improvements, a new human-review visual cue (yellow highlight on low-confidence table paragraphs), and a full paragraph-by-paragraph DOCX diff analysis for `ENA_188122_CH04` identifying root causes for ~67 actionable errors and ~300 correct-but-different canonicalization mappings.

---

## Major Changes Completed

### 1. Runtime Bug Fixes from Production Logs ✅

Three bugs observed in live processing logs:

**a) Missing `COUT-BL-FIRST` / `COUT-BL-LAST` in allowed styles** (ISS-012)
- LLM was outputting these valid tags, triggering self-heal retries
- Added both to `backend/config/allowed_styles.json` in sorted order
- Coverage: `test_allowed_styles.py`

**b) `relock_marker_classifications()` false positive for rule-based predictions** (ISS-013)
- The `reasoning` field is also set by rule-based predictions (`rule_based=True`), causing spurious LLM-leak warnings
- Tightened check: `(clf.get("gated") is False or clf.get("reasoning")) and not clf.get("rule_based")`
- Coverage: `test_marker_lock.py` (65 tests)

**c) `INTEGRITY_TRIGGER_FAIL` false positive for Normal → T1 table caption** (ISS-006)
- `_compare_structure()` flagged heading_level mismatch when Normal (level=None) was canonicalized to T1 (level=0) after table-title enforcement
- Added caption-promotion exemption: skip the diff when `input.level is None`, `output.level == 0`, style is a table-caption style, and text matches `^Table\s+\d+`
- Coverage: `test_integrity_trigger.py` (41 tests)

All 107 targeted tests pass after these fixes.

---

### 2. Table Style Diff Analysis ✅

Ran automated comparison between AI-processed DOCX and publisher-tagged DOCX for `Duggan9781975244347-ch006`:

**Key findings:**
- 142 total cell mismatches across 8 tables
- Processed document has 72 body paragraphs vs expected 51 (21 extra blank Normal separators — expected, not errors)
- T1 captions ARE correctly tagged at their actual paragraph positions (index-drift from blank separators caused apparent "mismatches" in naïve comparison)

**Mismatch taxonomy:**
| Pattern | Count | Root Cause |
|---------|-------|-----------|
| T4 → TBL-MID / T | ~50 | LLM over-assigns T4 to non-category-label cells |
| T2 → TBL-MID | ~15 | LLM over-assigns T2 to list-content cells |
| TBL-FIRST/MID/LAST missing | ~35 | No positional style normalizer for table cells |
| Normal (empty cells) | ~25 | PMI gate for empty TABLE-zone paragraphs |
| List Paragraph in cells | ~3 | XML list locks applied inside TABLE zone |
| Heading 5 in cells | ~10 | Classifier / zone restriction issue |

---

### 3. TABLE Zone Fix: Empty Cell Gate (ISS-014) ✅

**File:** `backend/processor/deterministic_gate.py`

Rule 1 (empty paragraph → PMI) now checks zone first:
```python
if not text or not text.strip():
    if zone == "TABLE":
        return _result("T", 0.99, "gate-empty-table")
    return _result("PMI", 0.99, "gate-empty")
```

---

### 4. TABLE Zone Fix: List Lock Suppression (ISS-015) ✅

**File:** `backend/processor/list_hierarchy.py`

Added early `continue` for TABLE-zone paragraphs before list-locking:
```python
if meta.get("context_zone") == "TABLE":
    skipped_table += 1
    continue
```

Skipped count emitted in log: `"list-hierarchy: locked N; skipped M TABLE-zone paragraphs"`.

---

### 5. TABLE Zone Fix: Cell-Position Normalizer (ISS-016) ✅

**Files:** `backend/processor/table_cell_position_normalizer.py` (new), `backend/processor/pipeline.py`

New post-classification normalizer `normalize_table_cell_positions()`:
- Groups TABLE-zone classifications by `(table_index, row_index, cell_index)` using block metadata
- For cells with ≥2 list-flagged (has_bullet / has_numbering / has_xml_list) paragraphs all tagged with flat T-family (T, T2, T4, TBL-MID):
  - First → `TBL-FIRST`
  - Middle → `TBL-MID`
  - Last → `TBL-LAST`
- Skips cells already containing TBL-FIRST or TBL-LAST (already processed)
- Emits `TABLE_CELL_POSITIONS cells_normalized=N paragraphs_relabeled=N` log

Wired into **both** pipeline paths (override path + LLM retry loop) after `relock_marker_classifications`, before quality scoring.

---

### 6. Classifier Prompt Refinement: T vs T2 vs T4 in TABLE Zone ✅

**File:** `backend/prompts/system_prompt.txt` (Rule 9a)

Expanded Rule 9a with three key clarifications:
- **T4 scope**: Only SHORT category labels (1–5 words) that identify the entire row; longer/bulleted first-column content → T or TBL-MID
- **Multi-paragraph cells**: Always output TBL-MID for list items; the pipeline promotes to TBL-FIRST/LAST automatically. LLM should NEVER output TBL-FIRST or TBL-LAST directly.
- **Common over-use mistakes**: Body data cell in first column → T (not T4); bullet list in non-header cell → TBL-MID (not T2 or T4)

---

### 7. Table Low-Confidence Yellow Highlight ✅

**Files:** `backend/processor/reconstruction.py`, `backend/tests/test_table_highlight.py` (new)

Added table-specific configurable highlight threshold separate from the existing general < 85 body threshold:

**Constants (module-level):**
```python
_TABLE_HIGHLIGHT_THRESHOLD = int(os.getenv("TABLE_REVIEW_HIGHLIGHT_THRESHOLD", "80"))
_TABLE_RELATED_BODY_TAGS = frozenset({"T1", "T11", "T12", "UNT-T1", "TFN", "TSN"})
```

**`apply_styles()` signature addition:**
```python
def apply_styles(self, ..., table_highlight_threshold: Optional[int] = None) -> Path:
```

**Logic:**
- BODY loop: T1/TFN/TSN/etc. body paragraphs → use `_tbl_thresh`; all other body tags → unchanged existing `< 85`
- TABLE loop: all in-table paragraphs → use `_tbl_thresh` (was hardcoded 85)

**Configure at runtime:**
```bash
TABLE_REVIEW_HIGHLIGHT_THRESHOLD=70 celery -A app.celery worker ...
```

**8 regression tests**, all passing:
- `TestTableHighlight`: low conf → YELLOW; high conf → none; non-table isolation; T1 caption in body
- `TestThresholdConfigurable`: boundary at/below; custom lower threshold

---

### 8. Corpus-Driven Tag Semantics Calibration (30-File Zip) ✅

**Files:** `Tag files.zip` corpus (32 usable tagged DOCX files analyzed), `backend/app/services/style_normalizer.py`, `backend/config/style_aliases.json`, `ai_context/TAG_SEMANTICS_CORPUS.md`

Added a corpus-driven calibration pass to improve semantic normalization accuracy:
- Analyzed 32 manually tagged DOCX files (1 temp `~$` file excluded)
- Observed `540` unique paragraph styles and many publisher aliases/variants
- Added semantic behavior guide in `ai_context/TAG_SEMANTICS_CORPUS.md`
- Added/expanded alias normalization for recurring publisher styles (examples: `EOCREF`, `COKTL`, `BulletList1first`, `NBX1-TXT-FLUSH`, `TBL-MID0`)

High-impact engine fix from corpus analysis:
- Fixed `style_normalizer` bug that stripped positional suffixes from nested list tags (e.g. `BL2-MID`, `KT-BL2-MID`, `TBL3-MID`)

Practical impact:
- Fewer `Tag not allowed, downgraded` repairs
- Fewer `zone-restriction: unknown style ...` replacements
- Better nested-list semantics preservation across publishers

---

### 9. List Semantics Hardening (Still In Progress) ✅ / ⚠️

**Files:** `backend/processor/validator.py`, `backend/tests/test_style_enforcement.py`, `backend/tests/test_style_normalizer.py`

Added semantic list-position alignment in validator:
- Preserves family prefixes while fixing positional suffixes:
  - `KT-BL-MID -> KT-BL-FIRST/LAST`
  - `EOC-NL-MID -> EOC-NL-FIRST/LAST`
  - `RQ-LL2-MID -> RQ-LL2-LAST`
- Falls back to `MID` only when a family lacks `FIRST/LAST` variants

Known remaining limitation:
- List handling is still a major accuracy hotspot across publisher-specific families and nested list variants; additional corpus-driven rules are still needed.

---

### 10. Gemini Model Default Updated to Pro ✅

**Files:** `backend/processor/pipeline.py`, `backend/processor/classifier.py`, `.env.example`

Default model configuration now points to `gemini-2.5-pro` for primary + strong paths.

Notes:
- Caching/deterministic/rule paths can still result in `0` tokens and no LLM call
- `FORCE_LLM=true` is still required when forcing runtime verification of LLM invocation

---

## Test Status

| Test file | Tests | Status |
|-----------|-------|--------|
| `test_marker_lock.py` | 65 | ✅ All pass |
| `test_integrity_trigger.py` | 41 | ✅ All pass |
| `test_allowed_styles.py` | 1 | ✅ Pass |
| `test_deterministic_gate.py` | 51 | ✅ All pass |
| `test_list_hierarchy.py` | 33 | ✅ All pass |
| `test_table_highlight.py` | 8 | ✅ All pass (new) |
| **Combined regression** | **199** | ✅ All pass |

### Verification Note (Current Local Shell)

- Local Python execution was intermittently blocked in this environment (`python.exe` / venv interpreter inaccessible), so some later patches were validated through runtime backend reprocessing/logs instead of direct `pytest` in-shell.

Pre-existing failures in the broader suite (unrelated to this session):
- `test_comprehensive_overhaul.py::test_ul_to_ref_u_in_reference_zone` — `validate_and_repair` maps UL-FIRST → REF-N instead of REF-U in BACK_MATTER; not introduced by this session
- `test_zone_enforcement.py` (4 failures) — SK_H / BX4 zone enforcement edge cases; not introduced by this session
- `test_style_normalizer.py` (5 failures) — vendor prefix / box normalization; not introduced by this session
- `test_reference_zone*` (5 failures) — reference zone mapping edge cases; not introduced by this session
- `test_golden_pipeline.py` — missing test fixture ZIP file (`Org files.zip`); environment issue

---

## Modified Files This Session

| File | Change Type |
|------|------------|
| `backend/config/allowed_styles.json` | Added COUT-BL-FIRST, COUT-BL-LAST |
| `backend/processor/marker_lock.py` | Tightened LLM-leak detection |
| `backend/processor/integrity.py` | Caption-promotion exemption in _compare_structure() |
| `backend/processor/deterministic_gate.py` | Rule 1 TABLE-zone override (→ T) |
| `backend/processor/list_hierarchy.py` | TABLE-zone skip before list-lock |
| `backend/processor/table_cell_position_normalizer.py` | **New file** — TBL-FIRST/MID/LAST normalizer |
| `backend/processor/pipeline.py` | Import + two call sites for cell-position normalizer |
| `backend/prompts/system_prompt.txt` | Rule 9a T vs T2 vs T4 clarification |
| `backend/processor/reconstruction.py` | Table-specific highlight threshold + apply_styles() |
| `backend/tests/test_table_highlight.py` | **New file** — 8 highlight tests |

Additional later updates (post-table pass, same hardening cycle):
- `backend/app/services/style_normalizer.py` — corpus-driven alias/list normalization + nested list suffix bug fix
- `backend/processor/validator.py` — semantic list-family position alignment + marker/reference hardening
- `backend/config/style_aliases.json` — corpus-derived alias expansions
- `backend/config/allowed_styles.json` / `backend/processor/allowed_styles.json` — vocab additions from corpus/runtime
- `backend/processor/classifier.py` — fallback valid tags synced with expanded vocab
- `backend/processor/llm_client.py` — transient DNS/network retry classification
- `ai_context/TAG_SEMANTICS_CORPUS.md` — new semantic guide from tagged corpus

---

## Operational Notes

- Celery worker must be restarted to pick up changes to `integrity.py`, `deterministic_gate.py`, `list_hierarchy.py`, `reconstruction.py`, and `pipeline.py`.
- `TABLE_REVIEW_HIGHLIGHT_THRESHOLD` env var controls the highlight threshold (default 80); set on the Celery worker process.
- Cell-position normalizer emits `TABLE_CELL_POSITIONS` structured log; grep for this to monitor table list position fixups.

---

---

### 11. ENA_188122_CH04 DOCX Mismatch Analysis (Analysis Only — No Code Changes) ✅

**Files compared:**
- Processed: `ENA_188122_CH04_org_processed (1).docx` (602 paragraphs: 273 body + 329 table)
- Expected: `ENA_188122_CH04_tag.docx` (584 paragraphs: 177 body + 69 SDT + 338 table)

**Key structural insight:** The expected (publisher-tagged) file stores box/figure content inside Word `sdt` (content controls), not as inline body paragraphs. The processed file flattens SDT content into BODY zone paragraphs.

**Mismatch taxonomy:**

| Category | Volume | Classification | Fixable? |
|----------|--------|----------------|----------|
| TB → T (plain table body) | ~178 | Correct alias (canonical rename) | N/A |
| TB → TBL-FIRST/MID/LAST | ~60 | Correct positional expansion | N/A |
| EOC_REF → REF-N | 77 | Correct alias (canonical rename) | N/A |
| TX → TXT, TXL → TXT-FLUSH | ~22 | Correct alias (canonical rename) | N/A |
| TCH1 → T2 | 12 | Correct alias (column header) | Add to aliases |
| **T4 over-assignment** (TB expected) | **43** | **True misclassification** | Yes — prompt (ISS-018) |
| **SDT body text → BX zone** | **~28** | **Zone assignment error** | Yes — block extraction (ISS-019) |
| BX3/BX4/BX5 → BX1/BX2 (level collapse) | ~50 | Schema difference (type vs depth) | Requires box-type classifier |
| BX*_T box labels → PMI markers | ~10 | Design difference (structural model) | Intentional |
| TFN/TSN merged-cell duplication | ~27 | Analysis artifact (not real errors) | N/A |
| PMI in TABLE zone | 1 | Misclassification (border case) | Existing ISS-014 fix covers most |

**Net actionable errors:** ~67 (43 T4 over-assignment + ~23 SDT zone leakage + 1 PMI). The remaining ~300+ apparent mismatches are correct canonicalization or accepted design differences.

**Root-cause stage mapping:**

| Stage | Issue | Severity |
|-------|-------|----------|
| Classifier prompt (Rule 9a) | T4 over-assignment on first-column cells | High |
| Block extraction / zone tagging | SDT paragraphs inherit BOX zone instead of BODY | High |
| style_aliases.json | `TCH1` / `TT` not mapped to `T2` / `T1` | Medium |
| Box level detection | BX1/2 depth-based vs BX1-5 type-based schema mismatch | Design difference |

**Concrete code change targets:**
1. `backend/prompts/system_prompt.txt` Rule 9a — strengthen "when in doubt, default to T not T4" (ISS-018)
2. `backend/processor/blocks.py` or zone-tagging step — SDT stand-alone content controls should reset zone to BODY, not inherit surrounding box zone (ISS-019)
3. `backend/config/style_aliases.json` — add `"TCH1": "T2"`, `"TCH": "T2"`, `"TT": "T1"` if missing

---

## Next Verification Steps

```bash
# All targeted tests
pytest backend/tests/test_marker_lock.py backend/tests/test_integrity_trigger.py \
       backend/tests/test_deterministic_gate.py backend/tests/test_list_hierarchy.py \
       backend/tests/test_table_highlight.py -v

# Reprocess a chapter with known table mismatches and check DOCX output
# Look for: TABLE_CELL_POSITIONS log, yellow highlight on low-conf table cells

# For ENA_188122_CH04 fix verification (once ISS-018/ISS-019 addressed):
# Re-run DOCX diff and check T4 count drops from 43 toward 0
# Check SDT body paragraphs no longer receive BX* zone tags
```
