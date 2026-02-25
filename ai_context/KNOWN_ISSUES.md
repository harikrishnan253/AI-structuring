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

**Status:** 🟡 Known limitation (actively improving)
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

**Remaining Work:**
- Add more corpus-derived list-family rules (especially `OBJ-*`, `KT-*`, `EOC-*`, `RQ-*`, `ANS-*`)
- Build list-heavy regression set from tagged corpus and track per-family accuracy
- Improve cross-row/cross-cell list semantics in table-adjacent structures where applicable

---

### ISS-018: T4 Over-Assignment in Table First-Column Cells 🔴

**Status:** 🔴 Active bug
**Component:** `backend/prompts/system_prompt.txt` (Rule 9a), LLM classifier
**Date Identified:** 2026-02-24

**Observed Symptom:**
- 43 table cells assigned `T4` in `ENA_188122_CH04` where the publisher uses plain `TB` (→ `T`)
- All 43 T4 assignments map to `TB` (plain body) in the publisher-tagged file
- LLM uses first-column position as T4 trigger even when cell content is multi-word body data, not a short category label

**Impact:**
- ~43 extra style mismatches per chapter compared to publisher output
- T4 semantics are: short (1–4 word) categorical row label; applies to much wider set than intended

**Root Cause:**
- Rule 9a in the classifier prompt was tightened last session but remains insufficiently conservative
- LLM needs an explicit "when in doubt, default to T" instruction for first-column cells

**Fix Target:**
- `backend/prompts/system_prompt.txt` — add to Rule 9a: "NEVER use T4 for cells with multi-word content (>6 words), numeric data, or any cell that is not unambiguously a 1–4 word categorical row label. When in doubt between T and T4, always output T."

---

### ISS-019: SDT (Content Control) Paragraphs Absorb Surrounding Box Zone 🔴

**Status:** 🔴 Active bug
**Component:** `backend/processor/blocks.py` or zone-tagging step
**Date Identified:** 2026-02-24

**Observed Symptom:**
- In `ENA_188122_CH04`: ~28 body paragraphs that appear inside `sdt` (Word content controls) are assigned `BX1-*` or `BX2-*` zone tags
- Publisher tags these same paragraphs as plain body text (`TXL` → `TXT-FLUSH`, `TX` → `TXT`)
- The paragraphs are in standalone content controls (figures, callouts), not inside PMI-bounded box regions

**Impact:**
- ~28 style mismatches per chapter where body-zone text is tagged as box-zone content
- Downstream style validation may trigger zone-restriction repairs unnecessarily

**Root Cause:**
- During block extraction, paragraphs inside `sdt` elements inherit the zone context of the surrounding BODY region (e.g., if the preceding section is in a BOX zone, the SDT paragraphs get BOX zone)
- Standalone content controls should reset zone context to BODY

**Fix Target:**
- `backend/processor/blocks.py` (block extraction / zone context propagation) — when entering an `sdt` element that is a direct child of `<w:body>` (not nested inside a PMI-bounded box), reset `context_zone` to `BODY` for its contained paragraphs

---

## Resolved Issues

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

### ISS-013: `relock_marker_classifications()` False Positive on Rule-Based Predictions ✅

**Status:** ✅ RESOLVED
**Component:** `backend/processor/marker_lock.py`
**Date Identified:** 2026-02-24
**Date Resolved:** 2026-02-24

**Problem:**
The "leaked to LLM" detection check `clf.get("gated") is False or clf.get("reasoning")` was too broad. Rule-based predictions (from `_apply_rules()`) also set `reasoning`, so any marker block that got rule-classified would trigger a spurious LLM-leak warning.

**Resolution:**
- Updated check to exclude rule-based classifications: `(clf.get("gated") is False or clf.get("reasoning")) and not clf.get("rule_based")`.

**Coverage:** `tests/test_marker_lock.py` (65 tests, all pass).

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

**Last Updated:** 2026-02-24
**Total Active Issues:** 4 (ISS-017 list accuracy, ISS-018 T4 over-assignment, ISS-019 SDT zone leakage, OPS-001 environment-specific)
**Total Resolved Issues:** 11 (ISS-001 through ISS-016, plus ISS-004/ISS-005)
**Total Edge Cases Documented:** 3
