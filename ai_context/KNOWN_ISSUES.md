# KNOWN ISSUES & LIMITATIONS

This document tracks known issues, limitations, and edge cases in the document processing pipeline.

---

## Active Issues


### OPS-001: Local Windows Python Execution Sometimes Blocked (Tooling / Verification Limitation) 🟡

**Status:** 🟡 Environment-specific limitation
**Component:** Local dev environment (not pipeline runtime)

**Observed Symptom:**
- `python.exe` / `backend\\venv\\Scripts\\python.exe` intermittently fail with access denied / file cannot be accessed
- Prevents local pytest execution from Codex shell in some sessions

**Impact:**
- Code patches may require runtime verification through the running backend instead of direct pytest from shell

**Workaround:**
- Restart terminal / IDE / backend process
- Use backend runtime reprocessing to validate behavior when local Python invocation is blocked

---

### ISS-017: List Handling Accuracy Still Degrades Across Publisher-Specific Families and Nested Variants 🟡

**Status:** 🟡 Partially resolved (2026-02-25) — FIRST/MID/LAST corruption for nested and interrupted lists fixed; remaining work is additional corpus-driven family rules
**Component:** `style_normalizer.py`, `validator.py`, list normalizers, classifier/allowed-style vocab

**Observed Symptom:**
- Nested list variants and publisher-specific list families can still be flattened, downgraded, or position-shifted
- Examples from runtime/corpus:
  - `BL2-*` / `KT-BL2-*` / `RQ-LL2-*` variants
  - section-specific families (`KT-*`, `EOC-*`, `OBJ-*`, `RQ-*`) losing `FIRST/MID/LAST` semantics
  - publisher raw list names requiring aliasing before semantic repair

**Impact:**
- Wrong list tags in processed output (especially nested and family-specific lists)
- Extra repair churn (`Tag not allowed`, `zone-restriction`) and reduced fidelity vs manually tagged files

**Current Mitigations (Implemented):**
- Nested list suffix preservation in `style_normalizer.py`
- Corpus-driven alias expansions in `backend/config/style_aliases.json`
- Semantic list-family positional alignment in `validator.py`
- Expanded allowed-style vocab/fallback valid tags from tagged corpus

**Mitigations added 2026-03-04 (Tasks 1-8):**
- `ANS-UL` and `ANS-NL` (unsuffixed) → resolved deterministically to `-MID` via `style_aliases.json` and validator Strategy 1.5
- `TUL` and `TUL-LAST` → resolved to `TUL-MID` via `style_aliases.json`
- `CJC-NN-BL-LAST`, `CJC-UL-FIRST`, `CJC-UL-LAST` added to allowed styles and TABLE-zone constraints
- Log-level semantics split: WARNING only for generic hard fallbacks (`TXT`, `TXT-FLUSH`, `T`, `PMI`); INFO for specific family remaps

**Remaining Work:**
- Add more corpus-derived list-family rules (especially `OBJ-*`, `KT-*`, `EOC-*`, `RQ-*`)
- Build list-heavy regression set from tagged corpus and track per-family accuracy
- Fix `normalize_style("DIALOGUE")` returning "DIA" instead of "DIA-MID" — DIA is not in `LIST_BASES` so the normalizer strips the -MID suffix; requires either adding DIA to LIST_BASES or a normalizer-level alias special-case
- Improve cross-row/cross-cell list semantics in table-adjacent structures where applicable

---

### ISS-018: T4 Over-Assignment in Table First-Column Cells ✅

**Status:** ✅ RESOLVED (2026-02-26)
**Component:** `backend/prompts/system_prompt.txt` (Rule 9a), `backend/processor/validator.py`, `backend/processor/ingestion.py`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-26

**Observed Symptom:**
- 43 table cells assigned `T4` in `ENA_188122_CH04` where the publisher uses plain `TB` (→ `T`)
- All 43 T4 assignments map to `TB` (plain body) in the publisher-tagged file
- LLM uses first-column position as T4 trigger even when cell content is multi-word body data, not a short category label

**Resolution (3-layer fix):**
1. **`system_prompt.txt` Rule 9a** — Rewrote to explicitly DEFAULT to `T` for first-column cells; T4 now requires all 5 conditions: short label (1–4 words, max 5), names/identifies entire row, no trailing punctuation, not a sentence/clause, not numeric data. Added explicit "when in doubt between T and T4, ALWAYS choose T."
2. **`validator.py` stub-col heuristic** — Restricted `is_stub_col` → T4 promotion to require `_looks_like_t4_heading(text)` passing (conservative: all-caps strings or multi-word 70%+ title-case, ≤60 chars, no trailing punctuation, not numeric). Body data cells can no longer be promoted to T4 by the validator.
3. **`ingestion.py` `_infer_table_style()`** — Removed 3 locations that blanket-defaulted first-column cells to T4 (for T/TableBody/GT style, UNT style, and position-infer fallback). All now return `T`; the classifier decides T vs T4 from content.

**Coverage:** `test_t4_and_sdt_fixes.py` (26 tests), `test_table_inference.py` (9 tests, updated)

---

### ISS-019: SDT (Content Control) Paragraphs Absorb Surrounding Box Zone ✅

**Status:** ✅ RESOLVED (2026-02-26)
**Component:** `backend/processor/ingestion.py`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-26

**Observed Symptom:**
- In `ENA_188122_CH04`: ~28 body paragraphs that appear inside `sdt` (Word content controls) are assigned `BX1-*` or `BX2-*` zone tags
- Publisher tags these same paragraphs as plain body text (`TXL` → `TXT-FLUSH`, `TX` → `TXT`)
- The paragraphs are in standalone content controls (figures, callouts), not inside PMI-bounded box regions

**Resolution:**
- Added `DocumentIngestion._build_sdt_para_set(doc)` static method: pre-computes `id(p_elem)` for all `<w:p>` elements that are direct children of `<w:sdtContent>` inside body-level `<w:sdt>` elements (i.e., only direct `<w:body>` children, not table-nested SDTs).
- In `extract_paragraphs()`, looks up each paragraph's `id(para._p)` against the pre-computed set. If the paragraph is inside a body-level SDT AND the current zone is `BOX_*`, resets zone to `BODY` and clears `box_type`.
- Adds `is_sdt=True` to paragraph metadata for downstream traceability.

**Coverage:** `test_t4_and_sdt_fixes.py` (5 SDT tests: `TestBuildSdtParaSet` + `TestSdtZoneReset`)

---

## Resolved Issues

### ISS-018: T4 Over-Assignment in Table First-Column Cells ✅

**Status:** ✅ RESOLVED
**Component:** `backend/prompts/system_prompt.txt`, `backend/processor/validator.py`, `backend/processor/ingestion.py`
**Date Resolved:** 2026-02-26

**Problem:**
43 table cells per chapter assigned `T4` instead of `T`. LLM used first-column position as a T4 trigger regardless of cell content.

**Resolution:**
Three-layer fix: (1) Rule 9a in system_prompt.txt now defaults first-column cells to T and requires 5 conditions for T4; (2) validator.py stub-col heuristic gated by `_looks_like_t4_heading()`; (3) `_infer_table_style()` in ingestion.py no longer returns T4 for any first-column cell by default.

**Coverage:** `test_t4_and_sdt_fixes.py` (26 tests), `test_table_inference.py` (9 tests, updated)

---

### ISS-019: SDT (Content Control) Paragraphs Absorb Surrounding Box Zone ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/ingestion.py`
**Date Resolved:** 2026-02-26

**Problem:**
~28 paragraphs inside body-level Word `<w:sdt>` content controls inherited surrounding BOX zone instead of resetting to BODY zone.

**Resolution:**
Added `_build_sdt_para_set()` static method to `DocumentIngestion`; `extract_paragraphs()` resets zone to BODY for SDT paragraphs that would otherwise inherit a `BOX_*` zone. Adds `is_sdt=True` metadata flag for traceability.

**Coverage:** `test_t4_and_sdt_fixes.py` (5 SDT tests)

---

### ISS-005: Marker-Locked (`skip_llm`) Blocks Leaked into LLM Payload ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/classifier.py`, `backend/processor/deterministic_gate.py`
**Date Resolved:** 2026-02-23

**Problem:**
Blocks marked by `marker_lock` with `skip_llm=True` could still pass into cache/rule/chunk paths and reach LLM payload construction.

**Resolution:**
- Added hard `skip_llm` exclusion before cache/rule/LLM eligibility
- Added deterministic local classification for skipped blocks
- Added payload build assertion/warning if any `skip_llm` block reaches `_classify_chunk()`

**Coverage:** `test_marker_lock.py`, `test_llm_execution_audit.py`

---

### ISS-006: Normal→T1 Table Caption Integrity False Positive ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/integrity.py`
**Date Identified:** 2026-02-23
**Date Resolved:** 2026-02-24

**Problem:**
`_compare_structure()` flagged a heading level mismatch when an input paragraph had `Normal` style (heading_level=None) and its output was canonicalized to `T1` style by table-title enforcement. `_get_heading_level()` correctly assigns heading_level=0 to T1+"Table N…" paragraphs, but that made input=None vs output=0 look like a structural violation.

**Resolution:**
- Added caption-promotion exemption in `_compare_structure()` heading-level comparison: skip the diff when `input.heading_level is None` AND `output.heading_level == 0` AND `output.style_name` is a table-caption style (T1/T11/T12/UNT-T1/TableCaption) AND output text matches `^Table\s+\d+`.

**Coverage:** Verified via existing `test_integrity_trigger.py` (41 tests, all pass).

---

### ISS-012: Missing `COUT-BL-FIRST` / `COUT-BL-LAST` in Allowed Styles ✅

**Status:** ✅ RESOLVED
**Component:** `backend/config/allowed_styles.json`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-24

**Problem:**
LLM output tags `COUT-BL-FIRST` and `COUT-BL-LAST` were not present in `allowed_styles.json`, causing them to be treated as invalid and triggering classifier self-heal retries.

**Resolution:**
- Added both tags to `allowed_styles.json` in sorted order (after `COUT-2`, before `COUT-NL-FIRST`).

**Coverage:** `tests/test_allowed_styles.py` (passes).

---

### ISS-013: `relock_marker_classifications()` Leak Diagnostic Precision ✅

**Status:** ✅ RESOLVED (extended 2026-03-02)
**Component:** `backend/processor/marker_lock.py`
**Date Identified:** 2026-02-24
**Date Resolved (initial):** 2026-02-24 — excluded rule-based predictions from leak detection
**Date Resolved (extended):** 2026-03-02 — distinguished Case A (true skip_llm leak) from Case B (post-hoc marker detection)

**Problem (initial, 2026-02-24):**
The "leaked to LLM" check `clf.get("gated") is False or clf.get("reasoning")` was too broad. Rule-based predictions also set `reasoning`, so any rule-classified marker block triggered a spurious LLM-leak warning.

**Resolution (initial):**
Updated check to exclude rule-based classifications: `(clf.get("gated") is False or clf.get("reasoning")) and not clf.get("rule_based")`.

**Problem (extended, 2026-03-02):**
Even with the rule-based exclusion, `leaked_to_llm` and the WARNING were firing for markers that arrived at the post-classification re-lock pass *without* a prior `skip_llm=True` flag (Case B: post-hoc marker detection by text pattern). These should not count as true leaks.

**Resolution (extended):**
Added `had_skip_llm = block.get("skip_llm") is True` guard:
- **Case A** (true leak): block had `skip_llm=True` AND LLM-touched → WARNING + `leaked_to_llm` increment
- **Case B** (post-hoc): marker detected without prior `skip_llm=True` → DEBUG only; not counted

PMI re-lock behavior unchanged for both cases. See ADR-030.

**Coverage:** `tests/test_marker_lock.py` (78 tests — 12 new tests in `TestLeakDiagnosticCorrectness`).

---

### ISS-014: Empty TABLE-Zone Paragraphs Gated to `PMI` Instead of `T` ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/deterministic_gate.py`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-24

**Problem:**
Rule 1 in `classify_deterministic()` gated all empty/whitespace-only paragraphs to `PMI` regardless of zone. Empty table cells are structural padding and should receive `T` (plain table body); assigning `PMI` violated TABLE-zone style validation.

**Resolution:**
- Added TABLE zone check in Rule 1: empty paragraphs in `context_zone == "TABLE"` are now gated to `T` at 99% confidence under rule name `"gate-empty-table"`.

**Coverage:** `tests/test_deterministic_gate.py` (51 tests, all pass).

---

### ISS-015: XML List Locks Applied Inside TABLE-Zone Cells ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/list_hierarchy.py`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-24

**Problem:**
`enforce_list_hierarchy_from_word_xml()` locked paragraphs with `numPr` XML to list-family styles (`BL-MID`, `NL-MID`, etc.) regardless of zone. These styles are invalid inside TABLE zone. Table cells with bullet points were getting `skip_llm=True` with a list tag, preventing correct T-family classification.

**Resolution:**
- Added early `continue` for paragraphs with `context_zone == "TABLE"` at the top of the block loop; skipped count logged alongside the locked count.

**Coverage:** `tests/test_list_hierarchy.py` (33 tests, all pass).

---

### ISS-016: TBL-FIRST / TBL-LAST Positional Styles Never Generated for Multi-Paragraph Table Cells ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/table_cell_position_normalizer.py` (new), `backend/processor/pipeline.py`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-24

**Problem:**
The existing `_compute_list_positions()` in `blocks.py` computed FIRST/MID/LAST only for BODY and BOX zone lists. Table cells with multiple bullet paragraphs all received flat `T` or `TBL-MID` tags; no FIRST/LAST positional styles were generated, causing ~35 style mismatches per chapter compared to expected publisher output.

**Resolution:**
- Created `backend/processor/table_cell_position_normalizer.py`: groups TABLE-zone classifications by `(table_index, row_index, cell_index)`, and for cells with ≥2 list-flagged paragraphs (has_bullet / has_numbering / has_xml_list) currently tagged as flat T-family (T, T2, T4, TBL-MID), reassigns: first → `TBL-FIRST`, middle → `TBL-MID`, last → `TBL-LAST`.
- Wired into both pipeline paths (override path and LLM retry loop) immediately after `relock_marker_classifications`.

**Coverage:** Pipeline import verification; existing 107-test suite unaffected.

---

### ISS-007: Structure-Safety Violations in Table Title Normalizer ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/table_title_normalizer.py`
**Date Resolved:** 2026-02-23

**Problem:**
`table_title_normalizer` could reorder or drop blocks (`pop/insert`), causing structural index drift.

**Resolution:**
- Converted to structure-safe mode (retag/metadata normalization only)
- Added invariants: same length, same ordered IDs
- Added regression tests for count/order/ID preservation

---

### ISS-008: Queue Masked Pipeline Failures with `OUTPUT_MISSING` ✅

**Status:** ✅ RESOLVED
**Component:** `backend/app/services/queue.py`
**Date Resolved:** 2026-02-23

**Problem:**
Expected pipeline fail-fast results (e.g., `STRUCTURE_GUARD_FAIL`, `INTEGRITY_TRIGGER_FAIL`) could be replaced by generic `OUTPUT_MISSING`.

**Resolution:**
- Queue now distinguishes pipeline `status='FAILED'` vs unexpected success-without-output
- Persists original `error`, `stage`, and diagnostics in job failure message

---

### ISS-009: Missing `learned_rules.json` Warning Spam ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/rule_learner.py`
**Date Resolved:** 2026-02-23

**Problem:**
Optional missing learned-rules file emitted repeated warnings and cluttered logs.

**Resolution:**
- Missing rules file treated as optional by default
- Log once per process/path (`INFO` first, `DEBUG` repeats)
- Strict mode available via `REQUIRE_LEARNED_RULES=true`

---

### ISS-010: Stale Queue Error Message Persisted After Successful Retry ✅

**Status:** ✅ RESOLVED
**Component:** `backend/app/services/queue.py`, frontend batch/job views
**Date Resolved:** 2026-02-24

**Problem:**
After retry success, job row could show `Completed` while still rendering a stale prior error (e.g., permission denied).

**Resolution:**
- Clear `job.error_message` when retry starts and on successful completion
- Frontend only displays failure details for `failed` / `cancelled` jobs

---

### ISS-011: `getaddrinfo failed` Treated as Non-Retryable LLM Error ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/llm_client.py`
**Date Resolved:** 2026-02-24

**Problem:**
Windows DNS resolution failures (`[Errno 11001] getaddrinfo failed`) were treated as non-retryable and caused chunk-wide `TXT` fallback.

**Resolution:**
- Reclassified DNS/network resolution errors as transient
- Uses existing exponential-backoff retry path before chunk fallback

### ISS-001: Section Break Type Detection May Be Incomplete ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/structure_guard.py`
**Date Identified:** 2026-02-18
**Date Resolved:** 2026-02-21

**Original Problem:**
`_validate_sections()` failed to detect section break TYPE changes (e.g., CONTINUOUS → NEW_PAGE) because `_extract_sections()` parsed raw XML for `w:type` which python-docx does not always write (NEW_PAGE is the document default and often omitted from the XML).

**Resolution:**
Changed `_extract_sections()` to use the python-docx API instead of raw XML:
```python
# Before (broken): raw XML parsing
type_element = sectPr.find('.//{...}type')
break_type = type_element.get('{...}val', 'continuous') if type_element else 'continuous'

# After (fixed): python-docx API
try:
    break_type = section.start_type.name.lower()
except Exception:
    break_type = 'new_page'
```

Updated `test_fail_when_section_break_modified` to assert `pytest.raises(RuntimeError, match="STRUCTURE_GUARD_FAIL")`.

**Test Coverage:** ✅ Fixed in `backend/tests/test_structure_guard.py::TestFailSectionMutations::test_fail_when_section_break_modified`

---

### ISS-004: ZONE_VALID_STYLES Drift Between ingestion.py and zone_styles.py [OK]

**Status:** [OK] RESOLVED (single canonical source + verification tests)
**Component:** `backend/processor/zone_styles.py`
**Date Identified:** 2026-02-21
**Date Resolved:** 2026-02-21

**Resolution:**
`ingestion.py` now imports the canonical zone map from `zone_styles.py` and derives JSON-safe list values.

Added `TestZoneStyleSingleSource` class in `backend/tests/test_zone_styles.py`:
- `test_ingestion_imports_canonical_zone_styles`
- `test_same_zone_keys`
- `test_body_zone_both_none`
- `test_zone_style_contents_match`

This prevents future manual drift while keeping ingestion metadata serializable.

---

### ISS-002: List Detection Failed for Style-Based Lists ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/structure_guard.py`
**Date Identified:** 2026-02-18
**Date Resolved:** 2026-02-18

**Original Problem:**
`_get_list_info()` only checked XML numPr properties. DOCX files created with `add_paragraph(..., style='List Bullet')` don't always have XML properties, causing list detection to fail.

**Tests Affected:**
- `test_fail_list_item_becomes_regular_paragraph`
- `test_fail_regular_paragraph_becomes_list_item`

**Resolution:**
Implemented dual detection strategy in `_get_list_info()`:
1. Primary: Check XML numPr/ilvl/numId properties
2. Fallback: Check paragraph style name for 'list', 'bullet', 'number' keywords

**Code:**
```python
# Primary: Check XML properties
if numPr is not None:
    return True, list_level, list_id

# Fallback: Check paragraph style name
style_name = paragraph.style.name if paragraph.style else ""
is_list_style = any(indicator in style_name.lower()
                    for indicator in ['list', 'bullet', 'number'])
if is_list_style:
    return True, 0, -1
```

**Documented:** ADR-003 in DECISIONS_LOG.md

---

### ISS-003: Wrong Import for Section Break Constants ✅

**Status:** ✅ RESOLVED
**Component:** `backend/tests/test_structure_guard.py`
**Date Identified:** 2026-02-18
**Date Resolved:** 2026-02-18

**Original Problem:**
Used incorrect import `from docx.enum.text import WD_BREAK` instead of `from docx.enum.section import WD_SECTION`.

**Error:**
```
AttributeError: type object 'WD_BREAK_TYPE' has no attribute 'CONTINUOUS'
```

**Resolution:**
Changed import to correct enum:
```python
from docx.enum.section import WD_SECTION  # Correct
# Not: from docx.enum.text import WD_BREAK
```

---

## Performance Limitations

### PERF-001: Structure Guard Performance on Very Large Documents

**Status:** 🟡 Known Limitation
**Component:** `backend/processor/structure_guard.py`

**Current Performance:**
- 500 paragraphs: ~1s
- 1000 paragraphs: ~5-10s
- 2000 paragraphs: ~30-60s

**Meets Requirements:** ✅ Yes (requirement: <1 minute for 2000 paragraphs)

**Limitation:**
For documents with 5000+ paragraphs, structure guard may take >2 minutes. This is acceptable for batch processing but may impact interactive workflows.

**Optimization Opportunities:**
1. Parallel processing for independent validations (paragraphs vs tables vs sections)
2. Early exit on first N differences (currently collects up to 50)
3. Lazy evaluation of structural signatures (only compute if needed)

**Priority:** Low (current performance meets requirements)

---

### PERF-002: Integrity Verification Memory Usage

**Status:** 🟡 Known Limitation
**Component:** `backend/processor/integrity.py`

**Memory Profile:**
- 500 paragraphs: ~2-5 MB
- 2000 paragraphs: ~10-20 MB
- 5000 paragraphs: ~50-100 MB

**Cause:**
`verify_content_integrity()` builds indexed output set including:
- All paragraphs
- 2-paragraph rolling concatenations
- Table cells

**Impact:**
For very large documents (10,000+ paragraphs), memory usage could exceed 200MB for a single document. This is acceptable for server environments but may impact resource-constrained systems.

**Mitigation:**
- O(n) algorithm is necessary for performance
- Memory usage is temporary (released after validation)
- Alternative streaming approach would be O(n²) and slower

**Priority:** Low (acceptable tradeoff for performance)

---

## Edge Cases

### EDGE-001: Nested Tables

**Status:** 🟢 Handled
**Component:** `backend/processor/structure_guard.py`

**Behavior:**
Structure guard correctly detects nested tables via `nested_tables_count` field in table validation.

**Test Coverage:** ✅ Covered in `test_pass_complex_document_with_nested_structures`

---

### EDGE-002: Empty Paragraphs

**Status:** 🟢 Handled
**Component:** Both `structure_guard.py` and `integrity.py`

**Behavior:**
- Structure guard: Validates empty paragraphs (text = "")
- Integrity trigger: Skips empty paragraphs in content verification
- Rationale: Empty paragraphs are structural elements, not content

**Test Coverage:** ✅ Covered in edge case tests

---

### EDGE-003: Unicode Text Normalization

**Status:** 🟢 Handled
**Component:** Both modules

**Normalization Applied:**
- Unicode NFKC normalization
- Whitespace trimming
- Multiple space collapsing
- Smart quote normalization (integrity only)

**Edge Cases Handled:**
- ✅ Combining characters (é vs é)
- ✅ Zero-width spaces
- ✅ Different whitespace characters (nbsp, tab, etc.)
- ✅ Smart quotes ("" vs "")

**Test Coverage:** ✅ Covered in `TestTextNormalization` class

---

## Future Considerations

### FC-001: PDF Output Support

**Status:** 📋 Future Enhancement

**Current State:**
Pipeline only supports DOCX input/output. No PDF support.

**Considerations:**
- PDF structure extraction is complex (no paragraph/table metadata)
- Would require OCR or PDF parsing library (PyPDF2, pdfplumber)
- Structure guard would need significant modifications
- Priority: Low (not in current requirements)

---

### FC-002: Real-time Validation API

**Status:** 📋 Future Enhancement

**Current State:**
Structure guard and integrity trigger are synchronous and blocking.

**Considerations:**
- For interactive workflows, async validation would improve UX
- Could implement streaming validation with progress updates
- Would require architectural changes to pipeline
- Priority: Medium (depends on user feedback)

---

### FC-003: Granular Style Change Tracking

**Status:** 📋 Future Enhancement

**Current State:**
Structure guard validates that styles CAN change, but doesn't track WHICH styles changed or WHY.

**Use Cases:**
- Audit trail of style transformations
- Debugging classifier decisions
- Quality metrics for style consistency

**Implementation:**
```python
style_changes = [
    {"paragraph_id": 42, "old_style": "Normal", "new_style": "SP-P", "reason": "LLM classified as body text"},
    {"paragraph_id": 43, "old_style": "Heading 1", "new_style": "SP-H1", "reason": "Marker <H1> detected"},
]
```

**Priority:** Low (nice-to-have for debugging)

---

## Testing Gaps

### TEST-001: Multi-section Documents

**Status:** 🟡 Partial Coverage

**Current Coverage:**
- ✅ Single section documents
- ✅ Two-section documents
- ⚠️ Limited coverage for 5+ section documents

**Recommendation:**
Add test cases for documents with:
- Multiple section break types (CONTINUOUS, NEW_PAGE, ODD_PAGE, EVEN_PAGE)
- Sections with different page orientations
- Sections with different headers/footers

**Priority:** Medium

---

### TEST-002: Large Document Performance Tests ✅

**Status:** ✅ RESOLVED
**Date Resolved:** 2026-02-21

**New file:** `backend/tests/test_performance_regression.py`
- 5 tests, gated by `@pytest.mark.slow` (skipped in regular runs)
- Run with `pytest --slow`
- Covers: structure guard 1 000 para (<10 s), 2 000 para (<60 s), 1 000 para + tables (<15 s)
- Covers: integrity trigger 1 000 para (<10 s), 2 000 para (<60 s)

conftest.py updated to register `slow` marker and `--slow` flag.

---

### TEST-003: Error Recovery and Graceful Degradation ✅

**Status:** ✅ RESOLVED
**Date Resolved:** 2026-02-21

**New file:** `backend/tests/test_error_recovery.py` — 13 tests, all passing.

**Coverage Added:**
- ✅ Non-existent file paths → `FileNotFoundError`
- ✅ Plain text / empty file as DOCX → `zipfile.BadZipFile`
- ✅ Corrupted ZIP (missing Content_Types) → `KeyError`
- ✅ Malformed XML inside DOCX → `lxml.etree.XMLSyntaxError`
- ✅ Valid mutation → `RuntimeError(STRUCTURE_GUARD_FAIL)` (regression test)
- ✅ Content loss → `RuntimeError(INTEGRITY_TRIGGER_FAIL)` (regression test)

**Exception type note:** When Path objects are passed (as both modules do internally), raw stdlib exceptions propagate rather than `PackageNotFoundError`.

---

## Documentation Updates Needed

### DOC-001: API Documentation

**Status:** 📋 Pending

**Missing:**
- Docstring examples for main entry points
- Usage guide for structure_guard.py
- Common error scenarios and solutions

**Recommendation:**
Add comprehensive docstrings with examples:
```python
def enforce_style_only_mutation(input_path, output_path):
    """
    Examples
    --------
    >>> result = enforce_style_only_mutation("input.docx", "output.docx")
    >>> print(result["status"])  # "PASS"

    >>> # Structural mutation detected
    >>> enforce_style_only_mutation("input.docx", "modified.docx")
    RuntimeError: STRUCTURE_GUARD_FAIL: 3 structural violations detected
    """
```

**Priority:** Medium

---

## Accepted Non-Goals / Limitations

These are known behaviors that are intentionally out of scope for the pipeline. They will not be fixed unless scope explicitly changes.

### NGL-001: `prev_tag` Transition Rules Cannot Fire at Runtime Without Explicit Metadata Injection

**Status:** 🟢 Handled (by design)
**Date noted:** 2026-02-27

`rule_learner.py` can learn rules with condition `prev_tag=X` from the training corpus (via `enrich_from_semantic_artifacts()` transition priors). However, `apply_rules()` calls `feature_extractor.extract_features(text, metadata)` internally, and `extract_features()` does not populate `prev_tag` from the `metadata` dict. As a result, `prev_tag=X` conditions never match at runtime.

**Implication:** Transition-prior enriched rules are included in `learned_rules.json` and counted by eval tools, but have zero effective coverage in the runtime classifier path.

**Accepted because:** Injecting `prev_tag` into every classification call would require the classifier to maintain per-document sequential state, which conflicts with the current batch/chunk architecture. The rules remain in the file and may become active if `extract_features()` is extended later.

**Reference:** ADR-029.

---

### NGL-002: Dash-Prefixed False Positives Are an Ingestion-Layer Issue

**Status:** 🟢 Handled (by design)
**Date noted:** 2026-02-27

Some DOCX files contain paragraphs whose raw text begins with a dash character (e.g., `- Item text`) that is part of the source content, not a list marker. These can produce false positives in `list_hierarchy.py` or `blocks.py` when the list-detection heuristic fires on dash-prefixed text.

**Accepted because:** The pipeline's list-detection logic operates on extracted text and XML list markers. Distinguishing "dash-as-bullet-char" from "dash-as-content-prefix" requires publisher-specific knowledge that is not consistently available. Fixing this in the pipeline would require per-publisher ingestion overrides that are out of scope for the current architecture.

**Workaround:** If a specific publisher uses dash-prefix content, add a publisher-specific alias or pre-processing rule in `style_aliases.json` or `blocks.py` ingestion logic.

---

### NGL-003: Paragraph-Index Drift in Holdout Reporting Is Not Tracked

**Status:** 🟡 Known Limitation
**Date noted:** 2026-02-27

`eval_generalization.py` and `rule_learner.py` holdout evaluation reports paragraph-level metrics (accuracy, coverage, per-tag P/R). When the same document is split between train and holdout sets at the doc level, paragraph indices within each split are re-counted from zero. This means holdout report row counts will differ from the full-corpus counts.

**Implication:** Holdout metrics are internally consistent and correct for generalization measurement. However, paragraph-level diagnostics (which specific paragraphs failed) cannot be cross-referenced with the full-corpus index without re-running evaluation on the full set.

**Accepted because:** The primary purpose of holdout evaluation is aggregate generalization metrics, not per-paragraph debugging. Per-paragraph debugging should be done on the full training set or with specific document fixtures.

---

### NGL-004: Grounded Retriever Index Is Stale After Corpus Updates

**Status:** 🟡 Known Limitation
**Date noted:** 2026-03-02

When `ENABLE_GROUNDED_RETRIEVER=true`, the classifier builds a TF-IDF index over `ground_truth.jsonl` at startup. If the corpus is updated (entries added, removed, or relabelled) while the service is running, the in-memory index becomes stale. The service does not detect corpus changes at classification time.

**Implication:** Classifications made with a stale index may retrieve outdated example paragraphs. The mismatch between retrieved examples and current canonical labels could cause soft accuracy regressions without any error signal.

**Accepted because:**
- `ENABLE_GROUNDED_RETRIEVER` defaults to `false`; stale-index risk only materialises in development or research configurations.
- Corpus updates in production follow the re-training checklist (OFFLINE_PIPELINE_GUIDE.md), which includes a service restart as its final step.
- Adding a corpus file-watcher would require background threads and introduce complexity that is not justified for an optional research mode.

**Workaround:** Restart the backend service after any `ground_truth.jsonl` update when `ENABLE_GROUNDED_RETRIEVER=true`.

**Reference:** ADR-028 (runtime decoupling decision).

---

## How to Use This Document

1. **Before deployment:** Review Active Issues for production impact
2. **When debugging:** Check Resolved Issues for similar past problems
3. **During development:** Check Future Considerations for planned work
4. **When adding tests:** Review Testing Gaps for coverage needs

**Update Guidelines:**
- Mark issues as ✅ RESOLVED when fixed (move to Resolved Issues section)
- Add new issues with 🟡 or 🔴 status in Active Issues
- Document edge cases discovered during testing
- Track performance regressions in Performance Limitations

**Status Legend:**
- 🔴 Critical (blocks production use)
- 🟡 Known Limitation (acceptable for now)
- 🟢 Handled (working as designed)
- ✅ RESOLVED (fixed)
- 📋 Future Enhancement (planned work)

---

**Last Updated:** 2026-03-04
**Total Active Issues:** 2 (ISS-017 list accuracy — partially mitigated, OPS-001 environment-specific)
**Total Resolved Issues:** 13 (ISS-001 through ISS-019, plus ISS-004/ISS-005)
**Total Edge Cases Documented:** 3
**Accepted Non-Goals:** 4 (NGL-001 prev_tag runtime gap, NGL-002 dash-prefix false positives, NGL-003 holdout index drift, NGL-004 grounded retriever stale index)
