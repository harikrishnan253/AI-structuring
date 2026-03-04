# ARCHITECTURAL DECISIONS LOG

This document records major architectural and design decisions made during development.

---

## ADR-001: Dual Validation Gate Architecture

**Date:** 2026-02-18
**Status:** ✅ Implemented
**Context:** Need to ensure document processing doesn't corrupt or alter documents beyond intended style changes.

### Decision

Implement TWO sequential hard validation gates after document reconstruction:

1. **Structure Guard (Stage 5.5)**
   - Purpose: Enforce style-only mutations
   - Validation: Paragraph count, order, text, list structure, table structure, sections
   - Fail condition: ANY structural change detected

2. **Integrity Trigger (Stage 6)**
   - Purpose: Verify content and structural preservation
   - Validation: Content integrity + structural integrity
   - Fail condition: ANY missing text OR structural difference

### Rationale

- **Defense in Depth:** Two layers of protection against data corruption
- **Different Purposes:**
  - Structure Guard: Catches unintended mutations from processors
  - Integrity Trigger: Comprehensive verification of final output
- **Fail-Fast:** Both gates stop pipeline immediately on failure
- **No LLM:** Both are 100% deterministic (no AI in validation)

### Alternatives Considered

1. **Single Validation Gate**
   - Rejected: Would mix concerns (mutation prevention vs. integrity verification)
   - Less clear error diagnostics

2. **Soft Validation (warnings only)**
   - Rejected: Data integrity is critical, cannot be optional
   - Risk of silent data loss

3. **LLM-based Validation**
   - Rejected: Non-deterministic, costly, slower
   - Validation must be reliable and fast

### Consequences

**Positive:**
- ✅ Zero data loss guarantee
- ✅ Clear separation of concerns
- ✅ Detailed error diagnostics
- ✅ Fast (O(n) complexity)

**Negative:**
- ⚠️ Slight performance overhead (~1-2s per document)
- ⚠️ More complex pipeline

**Metrics:**
- Structure guard: ~1s for 500 paragraphs
- Integrity trigger: ~2s for 500 paragraphs
- Total overhead: <1% of total processing time

---

## ADR-002: Marker Preservation in Structure Guard

**Date:** 2026-02-18
**Status:** ✅ Implemented
**Context:** Structure guard and integrity trigger handle marker tokens differently.

### Decision

- **Structure Guard:** Preserves markers in text comparison
- **Integrity Trigger:** Removes markers in text comparison

### Rationale

**Structure Guard:**
- Purpose: Ensure processors don't mutate document structure
- Markers are PART of the document structure at this stage
- Comparison BEFORE marker removal ensures no unintended changes

**Integrity Trigger:**
- Purpose: Verify original content is preserved
- Markers are ADDED by processors (not in original input)
- Removing markers allows comparison of actual content

### Consequences

✅ **Correct:** Each gate validates at the right abstraction level
✅ **Clear:** Different normalization rules for different purposes
⚠️ **Documented:** Must be clear in code comments

---

## ADR-003: List Detection Dual Strategy

**Date:** 2026-02-18
**Status:** ✅ Implemented
**Context:** DOCX list detection can fail if XML numPr properties are missing.

### Decision

Implement fallback strategy in `_get_list_info()`:

1. **Primary:** Check XML numPr/ilvl/numId properties
2. **Fallback:** Check paragraph style name for 'list', 'bullet', 'number'

### Rationale

- Some DOCX files only use style-based lists (no XML properties)
- python-docx `add_paragraph(..., style='List Bullet')` doesn't always set numPr
- Tests need to work reliably across different DOCX generation methods

### Alternatives Considered

1. **XML-only detection**
   - Rejected: Would miss style-based lists
   - Tests would fail

2. **Style-only detection**
   - Rejected: Less accurate, misses true list structure
   - XML properties are more reliable when present

### Consequences

✅ **Robust:** Works with both XML and style-based lists
✅ **Backward compatible:** Handles legacy DOCX files
⚠️ **Edge case:** May detect non-list paragraphs with "list" in style name (rare)

---

## ADR-004: FORCE_LLM Evaluation Mode

**Date:** 2026-02-18 (Earlier Session)
**Status:** ✅ Implemented
**Context:** Evaluation runs need to measure true LLM performance without cache interference.

### Decision

Add `FORCE_LLM` environment variable:
- `FORCE_LLM=false` (default): Respects cache and rule-based short-circuits
- `FORCE_LLM=true`: Bypasses cache/rules, forces at least 1 LLM call per document

### Rationale

- **Evaluation:** Measure true LLM classification accuracy
- **Cost Analysis:** Calculate actual token usage without cache benefits
- **Testing:** Verify LLM behavior in isolation
- **Production:** Keep caching for cost optimization

### Implementation

- Classifier checks `os.getenv("FORCE_LLM")` before skipping LLM
- Even if all paragraphs are cached/ruled, forces LLM call
- Token usage tracked separately

### Consequences

✅ **Clear:** Evaluation vs. production modes separated
✅ **Safe:** Default behavior unchanged (cache still works)
✅ **Flexible:** Can toggle per-job or per-environment
⚠️ **Cost:** Higher token usage in FORCE_LLM mode (intentional)

---

## ADR-005: Test Document Generation Strategy

**Date:** 2026-02-18
**Status:** ✅ Implemented
**Context:** Need reliable test fixtures for structure guard and integrity tests.

### Decision

Use **dynamic document generation** via `pytest`'s `tmp_path` fixture instead of static fixture files.

### Rationale

**Dynamic Generation:**
- ✅ Self-contained tests (no external file dependencies)
- ✅ Easy to understand (document structure visible in test)
- ✅ Flexible (can create any document structure)
- ✅ Platform-independent

**Static Fixtures:**
- ❌ Require maintenance (fixture files can become stale)
- ❌ Less readable (must open fixture file to understand test)
- ❌ Platform issues (line endings, paths)

### Implementation

```python
def _create_test_docx(file_path, paragraphs=None, tables=None, ...):
    """Helper to create test DOCX files dynamically"""
    doc = Document()
    # ... add content
    doc.save(str(file_path))
```

### Consequences

✅ **Maintainable:** Tests document structure inline
✅ **Reliable:** Fresh documents per test (no state pollution)
⚠️ **Performance:** Slightly slower (creates new DOCX per test)
   - Impact: Minimal (~0.1s per test)

---

## ADR-006: SHA256 Structural Signatures

**Date:** 2026-02-18
**Status:** ✅ Implemented
**Context:** Need fast, deterministic structural comparison.

### Decision

Create canonical structural signature and hash with SHA256:

**Format:**
```
P|{idx}|L{list_level}|T{in_table}|S{section_idx}
T|{idx}|R{rows}|C{cols}
SEC|{idx}|{break_type}
```

**Hash:** SHA256 of concatenated signatures

### Rationale

- **Fast:** O(n) signature creation, O(1) comparison
- **Deterministic:** Same structure → same hash
- **Sensitive:** Any structural change → different hash
- **Debuggable:** Can log signature for comparison

### Alternatives Considered

1. **Deep equality comparison**
   - Rejected: Complex, error-prone
   - Hard to debug

2. **JSON serialization + hash**
   - Rejected: Slower, order-dependent
   - Non-canonical representation

### Consequences

✅ **Performance:** Fast comparison even for large documents
✅ **Reliable:** Cryptographic hash guarantees uniqueness
✅ **Debuggable:** Can compare signatures when hashes differ

---

## ADR-007: O(n) Indexed Lookup for Content Integrity

**Date:** 2026-02-18 (Earlier Session)
**Status:** ✅ Implemented
**Context:** Need to handle 2000+ paragraph documents efficiently.

### Decision

Build indexed output set for O(1) lookups:

**Index Contents:**
1. Individual paragraphs
2. 2-paragraph rolling concatenations (for split detection)
3. Table cells

**Algorithm:** Check each input paragraph against indexed output

### Rationale

- **Performance:** O(n) vs. O(n²) substring matching
- **Split Detection:** Rolling concatenations catch paragraph splits
- **Memory:** Acceptable (<10MB for 2000 paragraphs)

### Alternatives Considered

1. **Naive substring search**
   - Rejected: O(n²) complexity
   - Too slow for large documents

2. **Full fuzzy matching**
   - Rejected: Over-engineered, slower
   - Our use case doesn't need fuzzy matching

### Consequences

✅ **Fast:** Handles 2000+ paragraphs in <1 minute
✅ **Accurate:** Detects splits and exact matches
⚠️ **Memory:** Uses ~5-10MB for 2000 paragraphs (acceptable)

---

## ADR-008: Fail-Fast Pipeline Stops

**Date:** 2026-02-18
**Status:** ✅ Implemented
**Context:** What should happen when a validation gate fails?

### Decision

**Immediate pipeline termination:**
- Structure guard fails → Return FAILED (skip integrity + quality)
- Integrity fails → Return FAILED (skip quality)
- No retry, no partial results, no warnings

### Rationale

- **Safety:** Cannot trust output if validation fails
- **Clarity:** Failure is unambiguous
- **Debugging:** Error message contains full diagnostics
- **Cost:** Don't waste resources on invalid output

### Alternatives Considered

1. **Log warning and continue**
   - Rejected: Too risky, data loss could go unnoticed

2. **Retry with different settings**
   - Rejected: Validation failures indicate processor bugs, not LLM issues
   - Should fix processor, not retry

3. **Partial output**
   - Rejected: Incomplete output worse than no output

### Consequences

✅ **Safe:** Zero tolerance for data corruption
✅ **Clear:** Failure is explicit and actionable
⚠️ **Strict:** May fail jobs that could be "acceptable"
   - Acceptable tradeoff for data integrity

---

---

## ADR-009: Stage 4.5 Final Style Enforcement Gate

**Date:** 2026-02-21
**Status:** ✅ Implemented
**Context:** Style repair in `validator.py` (Stage 3) operates at LLM output time and may miss zone-forbidden or unknown styles that pass through confidence filtering.

### Decision

Add a final deterministic style enforcement pass (Stage 4.5) after confidence filtering and before reconstruction via `enforce_style_compliance()` in `style_enforcement.py`.

### Rationale

- **Defense in Depth:** Validator repairs at classification time; Stage 4.5 is a second pass after filtering may re-introduce issues
- **Zone-safe fallbacks:** Each zone has a defined safe fallback: TABLE→`T`, METADATA→`PMI`, others→`TXT`
- **100% compliance guarantee:** No unknown or zone-forbidden style can reach the DOCX writer
- **Deterministic:** No LLM involved; uses `normalize_style()` and `_find_closest_style()`

### Consequences

✅ No unknown style reaches DOCX reconstruction
✅ Zone violations caught at a second layer
⚠️ Minor CPU overhead per document (negligible)

---

## ADR-010: Centralized Zone-Style Mapping

**Date:** 2026-02-21
**Status:** ✅ Implemented
**Context:** Zone-to-valid-styles logic was duplicated across `ingestion.py` and `zone_enforcement.py`, making it hard to maintain.

### Decision

Create `backend/processor/zone_styles.py` as the single source of truth for zone-style validation. All zone lookups go through `get_allowed_styles_for_zone(zone, allowed_styles)`.

### Rationale

- **Single source of truth:** Changes to zone rules require editing one file
- **Testable in isolation:** 14 dedicated tests
- **BODY zone is unrestricted:** Returns full `allowed_styles` without intersection

### Consequences

[OK] Zone rules are auditable and testable independently
[OK] `style_enforcement.py` and `validator.py` both consume from one source
[OK] `ingestion.py` now imports zone styles from `zone_styles.py` and derives JSON-safe lists
---

## ADR-011: Composite Tag Detection and Smart Repair

**Date:** 2026-02-21
**Status:** ✅ Implemented
**Context:** The LLM occasionally outputs composite tags (e.g., `TBL-H2+TXT`, `REF-N/PMI`) that are invalid. No detection existed.

### Decision

In `validator.py`, detect composite tags using separator characters (`+`, `/`, `,`, `|`) and repair by selecting the **first valid component** (one present in `allowed` after normalization). If none are valid, use the first component and let the existing semantic fallback handle it.

### Rationale

- **Prefer valid over first:** Choosing the first valid component is semantically better than blindly taking the first component
- **Graceful fallback:** If no component is valid, existing repair chains handle it
- **Metrics:** `composite_rejected` counter in `STYLE_CANONICALIZATION` log

### Consequences

✅ Composite tags never reach downstream stages
✅ Smart component selection improves repair quality
⚠️ Hyphenated valid tags (e.g., `BL-MID`) correctly excluded from detection

---

## ADR-012: LLM Execution Audit in classify()

**Date:** 2026-02-21
**Status:** ✅ Implemented
**Context:** The classifier could silently skip the LLM when all paragraphs appeared cached, even if cache hit count was incorrect. No audit trail existed.

### Decision

Track an `llm_audit` dict throughout `classify()` and emit `LLM_EXECUTION_TRACE` on every return path. Validate cache integrity before accepting "all cached" early exit.

### Key Rules Enforced:
1. `llm_eligible > 0` → `llm_invoked` must be `True`
2. `all_blocks_cached` only valid if `cache_hits == total_eligible`
3. Partial cache → force LLM run
4. `token_count == 0` when `llm_invoked` → emit `LLM_TOKEN_COUNT_ERROR` warning

### Consequences

✅ Zero silent LLM skips
✅ Full observability via structured `LLM_EXECUTION_TRACE` log
✅ Cache corruption detected and corrected automatically

---

## ADR-013: LLM Audit Hardening — llm_attempted vs llm_successful

**Date:** 2026-02-21
**Status:** ✅ Implemented
**Context:** `llm_invoked` was set before the actual API call (when `llm_eligible > 0`), making it an intent flag rather than a factual record. `LLM_TOKEN_COUNT_ERROR` was guarded by this pre-call flag, causing potential false positives on FORCE_LLM paths.

### Decision

Add two fields to `llm_audit` in `classify()`:
- `llm_attempted` — set to `True` immediately before the `_classify_chunk()` call
- `llm_successful` — set to `True` after getting a valid non-empty response

Guard `LLM_TOKEN_COUNT_ERROR` with `llm_attempted` instead of `llm_invoked`.
Include both fields in `LLM_EXECUTION_TRACE`.

### Rationale

- `llm_invoked` (pre-call intent) → still useful to signal "system determined LLM should run"
- `llm_attempted` (actual API call) → only set when the code actually reaches `_classify_chunk()`
- `llm_successful` (valid response) → distinguishes API call made vs. useful response received
- Token count warning is only meaningful when `llm_attempted=True AND token_count==0`

### Consequences

✅ Token count warnings are true anomalies (API called, empty response)
✅ FORCE_LLM paths can no longer trigger false `LLM_TOKEN_COUNT_ERROR`
✅ Full execution state visible in `LLM_EXECUTION_TRACE`
⚠️ Existing tests pass unchanged (llm_invoked still in trace)

---

## ADR-014: pytest.mark.slow for Performance Regression Tests

**Date:** 2026-02-21
**Status:** ✅ Implemented
**Context:** TEST-002 (large document performance) and PERF-001 coverage were missing.

### Decision

- Add `@pytest.mark.slow` marker gated by `--slow` CLI flag
- Register marker in `conftest.py` via `pytest_configure`; add `--slow` option via `pytest_addoption`; skip slow tests by default in `pytest_collection_modifyitems`
- Create `backend/tests/test_performance_regression.py` with 5 large-doc tests

### Consequences

✅ Regular test suite stays fast (5 skipped tests add 0 overhead)
✅ CI can opt in to performance validation with `pytest --slow`
✅ Threshold regressions caught immediately when performance degrades

---


## ADR-015: Chunk-Level Batch Error Recovery

**Date:** 2026-02-21
**Status:** [OK] Implemented
**Context:** Large documents are chunked for LLM classification. A transient failure in one chunk should not fail the entire job.

### Decision

When a chunk classification fails, continue processing remaining chunks and assign deterministic fallback outputs for the failed chunk:
- `tag="TXT"`
- `confidence=30`
- `batch_fallback=True`
- `reasoning` includes the chunk error

### Rationale

- Preserves progress on large documents
- Avoids all-or-nothing failures from transient API issues
- Keeps fallback behavior observable and auditable

### Consequences

[OK] More resilient batch processing for long documents
[OK] Explicit fallback markers available for downstream review
[WARN] Failed chunks may have low-confidence default tags until retried

---

## ADR-016: `skip_llm=True` Is a Hard Exclusion (All Classifier Paths)

**Date:** 2026-02-23
**Status:** ✅ Implemented
**Context:** Marker-locked blocks (`skip_llm=True`) were observed leaking into LLM chunk payloads despite pre-LLM locking.

### Decision

Treat `skip_llm=True` as an explicit hard exclusion in classifier execution, independent of `lock_style` / `allowed_styles`.

### Implementation

- Deterministic gate returns local classification for `skip_llm` blocks
- Classifier strips `skip_llm` paragraphs before cache/rule/LLM eligibility
- Skip results are merged back into final output deterministically
- Hard payload-path assertion logs and raises if any `skip_llm` block reaches LLM prompt build

### Consequences

✅ Marker/lock blocks never reach LLM payloads  
✅ Covers cache/rule/filter/chunk branches  
✅ Regressions fail fast with explicit diagnostics

---

## ADR-017: Central Structural Invariants Contract + Block Transform Assertions

**Date:** 2026-02-23
**Status:** ✅ Implemented
**Context:** Multiple normalizers/locks required consistent structural safety rules, but invariants were implicit and duplicated.

### Decision

Centralize structural invariants and block-transform contracts in `backend/processor/structural_invariants.py`, and enforce them with pre/post stage assertions in `pipeline.py`.

### Key Rules

- Preserve block count
- Preserve ordered block IDs
- Do not rewrite block IDs
- Style/tag-only normalizers must preserve text

### Consequences

✅ Earlier failure localization to the exact mutating stage  
✅ Shared reusable assertions for normalizers and tests  
✅ Hard gates remain strict (diagnostics improved, not weakened)

---

## ADR-018: Reconstruction Must Preserve Source List/Heading Semantics

**Date:** 2026-02-23
**Status:** ✅ Implemented
**Context:** Style application in reconstruction introduced list XML changes, heading promotions/demotions, and paragraph-count false positives.

### Decision

Reconstruction may change paragraph styles for presentation, but must preserve source structural semantics:
- paragraph count/order
- list semantics (`numPr`, list level/id, style-based list behavior)
- heading semantics (including deep/custom heading styles and `Title`)

### Implementation Notes

- Non-list source paragraphs never receive new `numPr`
- XML-numbered lists preserve existing numbering
- Style-based lists may be upgraded to explicit `numPr` only when needed to preserve structure while applying semantic list tags
- Source headings preserve semantics; non-heading paragraphs may receive visual-only `H*` styles
- Paragraph-count guard added before/after reconstruction save

### Consequences

✅ Eliminates structural mutations from style application  
✅ Supports semantic restyling without integrity drift  
⚠️ Adds complexity to reconstruction logic (tradeoff accepted)

---

## ADR-019: Post-Reconstruction Table Caption Canonicalization Is Structure-Safe and Title-Equivalent

**Date:** 2026-02-23 / 2026-02-24
**Status:** ✅ Implemented (runtime verification of one publisher edge case pending)
**Context:** Table-title enforcement (Stage 5.25) must canonicalize captions to `T1` without breaking structural integrity when source templates use `Title` style.

### Decision

- Keep Stage 5.25 as post-reconstruction style-only enforcement (no table/paragraph insertion/deletion)
- Preserve title-equivalent semantics when canonicalizing `Title` captions to `T1`
- Integrity treats `T1`/`T11`/`T12` table-caption styles as title-equivalent (`heading_level=0`) when text matches `Table N...`

### Consequences

✅ Canonical table caption styling (`T1`) preserved  
✅ Structural integrity can compare legacy `Title` captions and canonical `T1` captions fairly  
⚠️ Requires careful text-pattern gating to avoid false positives

---

## ADR-020: Queue/API Failure UX Must Surface True Pipeline Failure and Clear Retry Stale Errors

**Date:** 2026-02-23 / 2026-02-24
**Status:** ✅ Implemented
**Context:** Queue jobs could mask real pipeline failures as `OUTPUT_MISSING`, and successful retries could retain stale error text in UI.

### Decision

- Treat pipeline `status='FAILED'` results as expected terminal failures with explicit `error`, `stage`, diagnostics
- Reserve `OUTPUT_MISSING` only for inconsistent success-without-output results
- Clear `job.error_message` when retry starts and on successful completion
- UI renders failure details only for `failed` / `cancelled` jobs

### Consequences

✅ API/job status shows real failure cause (`STRUCTURE_GUARD_FAIL`, `INTEGRITY_TRIGGER_FAIL`, etc.)  
✅ Retry success no longer shows stale error banners  
✅ Polling endpoints stay HTTP 200 while payload becomes unambiguously terminal

---

## ADR-021: Learned Rules File Is Optional by Default (Strict Mode Opt-In)

**Date:** 2026-02-23
**Status:** ✅ Implemented
**Context:** Missing `backend/data/learned_rules.json` generated repeated warning spam even when rule-learning was not required.

### Decision

- Missing learned-rules file is optional by default
- Log once per process/path (first `INFO`, repeats `DEBUG`)
- Strict mode via `REQUIRE_LEARNED_RULES=true` raises a hard failure

### Consequences

✅ Reduced log noise in normal operation  
✅ Explicit strict-mode behavior for environments that require learned rules  
✅ Classifier fallback to LLM remains unchanged by default

---

## ADR-022: DNS/Network Resolution Errors Are Transient LLM Errors

**Date:** 2026-02-24
**Status:** ✅ Implemented
**Context:** Windows DNS failures (`[Errno 11001] getaddrinfo failed`) were treated as non-retryable, causing unnecessary chunk-level `TXT` fallbacks.

### Decision

Classify DNS/socket resolution failures and common transient network errors as retryable in `llm_client.py`, using existing exponential backoff.

### Consequences

✅ Fewer unnecessary chunk-wide TXT fallbacks during temporary network issues  
✅ Better resilience for large chunked LLM classifications  
⚠️ Slightly longer wait before fallback when network is genuinely down

---

## ADR-023: Corpus-Driven Style Normalization and List-Semantics Preservation

**Date:** 2026-02-24
**Status:** ✅ Implemented
**Context:** Manually tagged corpus files exposed recurring publisher aliases and nested-list style variants that were being downgraded or flattened (especially list positional suffixes such as `BL2-MID`, `KT-BL2-MID`).

### Decision

- Use the tagged corpus as a calibration source for deterministic normalization and repair rules
- Expand `style_aliases.json` with high-frequency publisher aliases
- Preserve nested list positional suffix semantics in `style_normalizer.py`
- Add semantic list-family position alignment in `validator.py` so repairs keep family prefixes (`KT-*`, `EOC-*`, `RQ-*`, etc.)

### Consequences

✅ Fewer "Tag not allowed" downgrades for publisher variants  
✅ Better nested-list and family-specific list behavior across documents  
✅ Knowledge of tag semantics captured in `ai_context/TAG_SEMANTICS_CORPUS.md` for future rule-learning  
⚠️ List handling remains a high-variance area and still needs additional corpus-driven rules

---

## ADR-024: Gemini 2.5 Pro Is the Default Processing Model (Configurable)

**Date:** 2026-02-24
**Status:** ✅ Implemented
**Context:** The project needed a consistent default to ensure high-quality classification behavior during normal processing without requiring per-environment overrides.

### Decision

- Set `gemini-2.5-pro` as the default for:
  - `GEMINI_MODEL_PRIMARY`
  - `GEMINI_MODEL_STRONG`
  - classifier prompt fallback default model
- Keep runtime overrides via environment variables intact

### Consequences

✅ Consistent model selection across pipeline/classifier defaults  
✅ Easier operational verification (`LLM_EXECUTION_TRACE` / attempt logs)  
⚠️ Caching/deterministic/rule paths may still bypass LLM entirely (`0` tokens), which is expected behavior

---

## ADR-025: Generic List-Position Normalizer — Depth-Transparent + PMI-Bridge + numId Grouping

**Date:** 2026-02-25
**Status:** ✅ Implemented

### Decision

Fix generic FIRST/MID/LAST corruption across all document types with four coordinated changes:

1. **`allowed_styles.json`**: Add 15 missing FIRST/LAST variants (BL2-FIRST, BL3/BL4 full sets, NL2/NL3 full sets, KT-BL2-FIRST, RQ-LL2-FIRST/LAST, TNL-LAST).
2. **`list_normalizer.py`**: Replace strict-contiguity algorithm with depth-transparent run grouping (`_is_deeper_family`) and recursive `_process_outer_run`. Add `_is_pmi_bridge` for transparent empty/marker PMI gaps.
3. **`list_preservation.py`**: Make `_is_position_compatible` and `_coerce_expected_tag_preserving_position` prefix-aware so KT-BL-FIRST survives against expected BL-MID.
4. **`blocks.py`**: `_compute_list_positions` groups XML-listed paras by `xml_num_id` for accurate metadata positions; style-based lists use legacy key.

### Consequences

✅ Nested lists get correct FIRST/MID/LAST on both outer and inner levels
✅ Blank-paragraph-interrupted lists no longer fragment into all-FIRST runs
✅ Prefixed families (KT-BL, OBJ-BL, EOC-NL) preserve prefix through list_preservation
✅ NL2, BL2, BL3, BL4 positional tags now reachable (were previously silently suppressed)
✅ 204 existing tests all pass; structure guard and integrity gates unaffected
⚠️ PMI-bridge only activates for empty text or structural marker tokens

---

## ADR-026: ISS-018 — T4 Conservative Default (Three-Layer Fix)

**Date:** 2026-02-26
**Status:** ✅ Implemented
**Context:** ~43 table cells per chapter were receiving `T4` instead of `T` because three independent code paths all defaulted first-column cells to T4 without checking cell content.

### Decision

Fix T4 over-assignment at all three layers simultaneously so no single path can restore the over-assignment behavior:

1. **Prompt layer** (`system_prompt.txt` Rule 9a): Rewrite to explicitly "DEFAULT to T" for first-column cells; T4 only when all 5 conditions met simultaneously: short label (1–4 words, max 5), names/identifies entire row, no trailing punctuation, not a sentence/clause, not numeric data. Add "when in doubt between T and T4, ALWAYS choose T."
2. **Validator layer** (`validator.py`): Gate stub-col T4 heuristic with `_looks_like_t4_heading(text)` — conservative function that accepts all-caps or multi-word 70%+ title-case strings ≤60 chars with no trailing punctuation and not purely numeric. Body data cells no longer promoted to T4.
3. **Ingestion layer** (`ingestion.py` `_infer_table_style()`): Remove all 3 locations that returned `'T4'` for first-column cells (T/TableBody/GT branch, UNT branch, position-infer fallback). All return `'T'`; content-based T4 assignment is the classifier's responsibility.

### Rationale

- **Defense in depth**: If only the prompt is changed, the validator or ingestion could still over-assign. All three layers must agree.
- **Conservative T**: T is a safe default; T4 has specific semantics (short categorical row label). Over-assigning T4 causes visible mismatches with publisher output.
- **`_looks_like_t4_heading` gating**: The heuristic function correctly rejects single capitalized words ("Protein"), sentences, numeric data, and long text while accepting true category labels ("MACRONUTRIENTS", "Risk Factors").

### Consequences

✅ First-column cells classified as `T` by default; T4 requires conservative heuristic to pass
✅ No regression on legitimate T4 cases (all-caps headings, multi-word title-case category labels)
✅ Reduces ~43 T4 mismatches per chapter toward 0
✅ Three-layer architecture means any single layer relaxation does not re-introduce the bug
⚠️ Edge case: `N/A` passes `_looks_like_t4_heading` (all-caps pattern) — noted as known behavior

---

## ADR-027: ISS-019 — SDT Zone Reset via XML Element Identity

**Date:** 2026-02-26
**Status:** ✅ Implemented
**Context:** Word `<w:sdt>` (Structured Document Tag / content control) paragraphs at body level were inheriting surrounding BOX zone because python-docx's `doc.paragraphs` flattens them into the same stream as regular paragraphs, losing the SDT wrapper context.

### Decision

Use XML element identity (`id(para._p)`) to detect SDT-contained paragraphs before the zone-tracking loop:

1. Add `DocumentIngestion._build_sdt_para_set(doc) -> set[int]` static method that iterates direct `<w:body>` children, finds `<w:sdt>` elements, and collects `id(p_elem)` for every `<w:p>` inside their `<w:sdtContent>`. Only body-level SDTs (not table-nested ones) are included.
2. In `extract_paragraphs()`, look up `id(para._p)` against the pre-computed set at each paragraph. If it's an SDT paragraph and current zone is `BOX_*`, reset zone to `BODY` and clear `box_type`.
3. Set `metadata['is_sdt'] = True` for traceability in downstream stages.

### Rationale

- **XML identity is stable**: `id(para._p)` matches precisely because python-docx paragraph objects wrap the same lxml element that was iterated over during `_build_sdt_para_set`. No string matching required.
- **Body-level only**: Table-nested SDTs (inside `<w:tc>`) are excluded intentionally — they should retain TABLE zone semantics. Only SDTs that are direct `<w:body>` children represent standalone content controls that should be BODY zone.
- **Additive metadata**: `is_sdt=True` flag enables future stages to treat these paragraphs specially (e.g., zone enforcement, quality scoring) without requiring re-detection.
- **Zero impact on non-SDT documents**: Pre-computation is O(n) over body children; if no SDTs exist, the set is empty and all lookups are O(1) misses.

### Alternatives Considered

1. **Style-name detection**: Rejected — SDT paragraphs can have any style; no reliable style marker.
2. **Parse surrounding XML in paragraph loop**: Rejected — would require walking lxml ancestry for every paragraph (O(n×depth)); identity pre-computation is faster and cleaner.
3. **python-docx InlineShape / ContentControl API**: Rejected — python-docx does not expose SDT elements through its high-level API in versions tested.

### Consequences

✅ ~28 SDT body paragraphs per chapter no longer assigned BOX zone
✅ `is_sdt=True` metadata available for downstream audit/quality scoring
✅ Table-nested SDTs unaffected (retain TABLE zone semantics)
✅ Zero overhead when no SDT elements present
⚠️ Object identity depends on in-process lxml element objects; must call `_build_sdt_para_set` on the same Document object passed to the paragraph loop (guaranteed by existing code structure)

---

## ADR-028: Runtime Decoupled from Corpus/Ground-Truth by Default

**Date:** 2026-02-27
**Status:** ✅ Implemented
**Context:** The grounded retriever (`GroundedRetriever` in `classifier.py`) can load `ground_truth.jsonl` at classification time and inject similar labeled paragraphs into the prompt. This creates a direct dependency between production runtime and raw training data, and risks data leakage when the same corpus is used for offline evaluation.

### Decision

- `ENABLE_GROUNDED_RETRIEVER` environment variable defaults to `false`.
- When disabled, `classifier.py` never loads or accesses `ground_truth.jsonl` during classification.
- Semantic artifact files (`tag_semantics_knowledge.json`, `tag_transition_priors.json`) are loaded only by offline tools (`rule_learner.py`, `eval_generalization.py`), not at classification time.
- `load_semantic_artifacts()` in `rule_learner.py` is module-level and offline-only.

### Rationale

- **Data leakage prevention**: Holdout evaluation in `eval_generalization.py` and `rule_learner.py` cannot be trusted if the runtime classifier reads the same ground-truth corpus.
- **Operational simplicity**: Production classification depends only on `learned_rules.json` (optional) + LLM API; no training data files need to be present.
- **Audit clarity**: Separation makes it unambiguous which inference paths are corpus-dependent and which are not.

### Alternatives Considered

1. **Always-on retriever**: Rejected — leaks training distribution into every classification; evaluation metrics become meaningless.
2. **Retriever with holdout-doc exclusion**: Considered but deferred — requires per-request holdout metadata and adds runtime complexity for marginal gain.

### Consequences

✅ Offline evaluation metrics are trustworthy (no ground-truth leakage into classifier)
✅ Production classifier is portable: only `learned_rules.json` and API key required
✅ Retriever mode available for development/research via `ENABLE_GROUNDED_RETRIEVER=true`
⚠️ `eval_generalization.py` retriever ablation mode explicitly labelled `[LEAKAGE]` in reports as a reminder

---

## ADR-029: Corpus as Offline Calibration Pipeline (Semantic Artifact Architecture)

**Date:** 2026-02-27
**Status:** ✅ Implemented
**Context:** The manually tagged corpus (`ground_truth.jsonl`, 30 documents, ~11k entries) is a high-value calibration source, but loading it at runtime couples production inference to training data and prevents clean holdout evaluation.

### Decision

Establish a strictly offline calibration pipeline:

1. **Build phase** (`build_semantic_knowledge.py`): Reads corpus, produces three artifact files in `backend/data/`:
   - `tag_semantics_knowledge.json` — zone-tag frequency distributions and tag family groupings
   - `tag_transition_priors.json` — sequential tag transition probabilities
   - `style_alias_candidates.json` — publisher alias candidates (confidence ≥ 0.70)

2. **Rule-learning phase** (`rule_learner.py --train`): Reads artifacts to enrich candidate rules (`enrich_from_semantic_artifacts()`); validates enriched rules against training split before adding. Produces `learned_rules.json`.

3. **Evaluation phase** (`eval_generalization.py`): Reads artifacts to power semantic and alias predictor ablation modes on holdout splits. Never writes to `learned_rules.json`.

4. **Runtime classifier** (`classifier.py`): Reads only `learned_rules.json` (optional). Receives generalized zone-prior hints via system prompt — not raw corpus paragraphs.

### Rationale

- **Clean separation**: Each phase consumes only the outputs of the phase before it; corpus docs never reach the classifier.
- **Reproducibility**: Artifacts are deterministic builds; `rule_learner.py` uses a seeded holdout split (`--holdout-seed 42`).
- **Graceful degradation**: `load_semantic_artifacts()` returns `{}` on missing files; the classifier, rule learner, and eval tool all work without the artifact files.

### Consequences

✅ Corpus knowledge propagates to runtime through stable artifact files, not raw training data
✅ Holdout and ablation metrics are uncontaminated
✅ Artifact files can be versioned and diffed in git
✅ `learned_rules.json` backward-compatible: new optional `metadata` field ignored by `load_rules()`
⚠️ `prev_tag` transition rules learned offline cannot fire through `apply_rules()` at runtime without explicit `prev_tag` metadata injection (current `extract_features()` does not populate `prev_tag` from metadata)

---

## ADR-030: Marker-Lock Leak Diagnostic — Case A vs Case B Distinction

**Date:** 2026-03-02
**Status:** ✅ Implemented
**Context:** ISS-013 (2026-02-24) added `not clf.get("rule_based")` to the leaked-to-LLM predicate in `relock_marker_classifications()`. The fix correctly excluded rule-classified markers from the leak count. However, the WARNING and `leaked_to_llm` metric were still triggered for markers that arrived at the post-classification re-lock pass *without* a prior `skip_llm=True` flag — i.e., markers detected post-hoc by text pattern alone (Case B). These should not be counted as leaks because they were never subject to the pre-LLM lock in the first place.

### Decision

Distinguish two cases explicitly inside the leak-detection branch of `relock_marker_classifications()`:

- **Case A (true leak):** Block had `skip_llm=True` (pre-LLM marker lock was set) AND the classification object contains LLM-generated signals (`gated is False` OR `reasoning` present) AND not rule-based. → Log WARNING; increment `leaked_to_llm` metric.
- **Case B (post-hoc detection):** Marker identified by text pattern or `_is_marker` flag but `skip_llm=True` was never set on the block. → Log DEBUG only; do not increment `leaked_to_llm`.

PMI re-lock behavior (overriding non-PMI tag to PMI) is unchanged for both cases.

### Implementation

```python
had_skip_llm = block.get("skip_llm") is True
llm_touched = (
    (clf.get("gated") is False or clf.get("reasoning"))
    and not clf.get("rule_based")
)
if llm_touched:
    if had_skip_llm:          # Case A
        leaked_to_llm += 1
        logger.warning(...)
    else:                     # Case B
        logger.debug(...)
```

### Rationale

- `leaked_to_llm` is intended to measure failures of the pre-LLM marker lock. A block that was never locked cannot leak.
- Inflated Case B counts masked true Case A signal and caused spurious oncall alerts during high-volume evaluation runs.
- DEBUG-level logging for Case B retains observability without metric pollution.

### Consequences

✅ `leaked_to_llm` is now a precise count of pre-LLM lock failures
✅ Case B markers are still relocked to PMI (functional behavior unchanged)
✅ 78/78 `test_marker_lock.py` tests pass (12 new tests in `TestLeakDiagnosticCorrectness`)
⚠️ Existing tests that covered Case B scenarios needed `skip_llm=True` added to their block fixture to represent true Case A leaks; covered by test updates

---

## ADR-031: Eval Generalization Metric Extension

**Date:** 2026-03-02
**Status:** ✅ Implemented
**Context:** `eval_generalization.py` previously reported 7 metrics per ablation mode: `accuracy`, `zone_violation`, `list_depth`, `table_sem`, `ref_accuracy`, `txt_fallback`, `unmapped_rate`. These did not capture: (1) the rate of predictions that would be rejected by `allowed_styles.json` at deployment; (2) the fraction of structurally sensitive entries where the predicted tag changed structural category (list↔non-list, heading↔non-heading), which is a proxy for Structure Guard failure probability; (3) a per-tag accuracy breakdown within the TABLE zone to distinguish errors on T, T2, T4, TFN, and TSN.

### Decision

Add three metrics to `compute_metrics()` and extend the report format:

| New Metric | Definition | Gate Condition |
|---|---|---|
| `invalid_tag_rate` | % predictions not in `allowed_styles.json` | all holdout entries |
| `structure_guard_fail_rate` | % entries where structural category (list/heading) changes between gold and predicted | gold is list OR heading |
| `table_per_tag` | per-gold-tag accuracy dict | `zone == "TABLE"` OR `gold in table_styles` |

### Implementation Notes

- `_is_list_tag(tag)`: regex `r"(?:^|[-_])(BL|NL|UL)\d*(?:[-_]|$)"` — matches BL/NL/UL families at any nesting level; excludes TBL-* (table rows) because "TBL" does not match the required BL/NL/UL token boundary.
- `_is_heading_tag(tag)`: regex `r"^(H[1-9]|TH[1-9]|CH)$"`.
- `table_per_tag` gate aligns with the existing `table_total` gate to avoid divergence between the aggregate `table_sem` metric and the per-tag breakdown.
- Report width extended from 110 to 120 columns. Delta headers use ASCII prefix (`dAccuracy`, `dZoneViol`, etc.) instead of Unicode for Windows CP-1252 terminal compatibility.
- `TABLE SEMANTICS DETAIL` section appended to report; shows `_TABLE_FOCUS_TAGS` (`T`, `T1`, `T2`, `T4`, `TFN`, `TSN`) first, then remaining tags alphabetically.

### Rationale

- `invalid_tag_rate` directly predicts Stage 4.5 (`style_enforcement.py`) workload — high rates indicate classifier quality regression.
- `structure_guard_fail_rate` surfaces regressions that would cause hard pipeline failures at the Structure Guard (Stage 5.5) without requiring a full pipeline run.
- `table_per_tag` allows targeted per-tag debugging of TABLE-zone classification without running the live pipeline.

### Consequences

✅ Three new signals available for offline regression tracking without any LLM calls
✅ `invalid_tag_rate` and `structure_guard_fail_rate` added to delta table for per-mode contribution tracking
✅ Table breakdown section identifies high-error tags (e.g. T4 vs T confusion) directly from holdout
⚠️ Report is wider (120 cols); terminals narrower than 120 chars will wrap delta rows
⚠️ `structure_guard_fail_rate` is a simulation metric — actual SG failure rates depend on document-level sequential context not available during flat holdout evaluation

---

## ADR-032: Alias-First Tag Normalization + Validator Log-Level Semantics

**Date:** 2026-03-04
**Status:** ✅ Implemented
**Context:** Several publisher-specific tag families (CJC-*, ANS-*, TUL) were producing false "Tag not allowed, downgraded" WARNING logs even when the target canonical form was a specific, semantically correct tag (e.g. ANS-UL → ANS-UL-MID). The validator also had nondeterministic fallback for unsuffixed list-family tags: Strategy 2 (prefix-family matching) could select ANS-UL-FIRST before ANS-UL-MID depending on allowed-set iteration order. All downgrade-level log messages used WARNING regardless of whether the remap was a generic fallback or a precise semantic repair.

### Decision

Apply changes at three layers to prevent false downgrades and improve log signal quality:

**1. Alias layer (`style_aliases.json`)**

Add six alias mappings that resolve publisher raw forms to their canonical equivalents before the validator's not-allowed path is reached:

| Raw form | Canonical | Rationale |
|---|---|---|
| `DIALOGUE` | `DIA-MID` | Publisher alias for dialogue mid-position |
| `CJC-NGN-BL-LAST` | `CJC-NN-BL-LAST` | Backward-compat alias (NGN → NN) |
| `ANS-UL` | `ANS-UL-MID` | Unsuffixed → deterministic MID |
| `ANS-NL` | `ANS-NL-MID` | Unsuffixed → deterministic MID |
| `TUL` | `TUL-MID` | Unsuffixed → deterministic MID (TUL in LIST_BASES, suffix preserved) |
| `TUL-LAST` | `TUL-MID` | No standalone LAST variant in this family |

Tags that resolve via alias never reach the validator's not-allowed path, so no log message is emitted.

**2. Validator fallback layer (`validator.py`)**

- **Strategy 1.5** (new): `_UNSUFFIXED_LIST_FAMILY_RE` matches unsuffixed ANS-UL, ANS-NL, TUL directly. If matched and the corresponding `-MID` variant is in the allowed set, return it deterministically — no iteration order dependency.
- **Strategy 2** (updated): After finding prefix-family candidates, check for `prefix + "-MID"` first before falling back to shortest-string sort. Sort key is `(len(s), s)` for stable lexicographic tie-breaking.

**3. Log-level semantics (`validator.py`)**

```python
_HARD_FALLBACK_TAGS: frozenset[str] = frozenset({"TXT", "TXT-FLUSH", "T", "PMI"})
```

- If the repaired tag is in `_HARD_FALLBACK_TAGS` → log **WARNING** with `"downgraded"` (true hard fallback; operator should investigate)
- Otherwise → log **INFO** with `"semantic-repair"` (specific family remap; expected behavior)

**4. New canonical tags (`allowed_styles.json`)**

Added: `DIALOGUE`, `CJC-NN-BL-LAST`, `CJC-UL-FIRST`, `CJC-UL-LAST` — these were valid publisher-output tags not present in the allowed set, triggering classifier self-heal retries.

**5. TABLE-zone constraints (`zone_styles.py`, `classifier.py`)**

Added `CJC-UL-FIRST`, `CJC-UL-LAST`, `CJC-NN-BL-LAST` to the TABLE-zone valid-style set so the zone enforcement gate does not reject them for CJC dialogue-in-table contexts.

### Rationale

- **Alias-first resolution**: A tag that aliases cleanly to a valid canonical should never be logged as a downgrade. Moving the normalization to the alias layer (before validation) is cleaner than special-casing it inside the validator.
- **MID preference in Strategy 2**: Unsuffixed or mismapped positional tags are almost always meant to be the middle (continuation) case. Preferring `-MID` deterministically is both more correct and more predictable than alphabetic or length-based ordering.
- **Log-level split**: WARNING-level "downgraded" messages are high-signal operational alerts. Flooding them with INFO-level semantic repairs (ANS-UL-FIRST → ANS-UL-MID) degrades their usefulness and can mask real problems. Separating the two makes `grep WARNING downgraded` a reliable production health check.
- **`_HARD_FALLBACK_TAGS` frozenset**: Explicit and auditable definition of what counts as a "true downgrade" vs a "semantic repair". Adding a new generic fallback tag requires an intentional code change, not an implicit threshold.

### Alternatives Considered

1. **Suppress WARNING logs entirely for all non-TXT repairs**: Rejected — would hide genuine validator fallbacks where no better match exists.
2. **Treat all positional-suffix mismatches as INFO**: Partially adopted — this is what the MID preference + INFO semantics achieves for suffix-only repairs within the same family.
3. **Fix the DIALOGUE/DIA normalizer bug at the same time**: Out of scope for Tasks 1-8. The bug (DIA not in LIST_BASES → "-MID" stripped) requires a LIST_BASES extension or a normalizer-level special case; tracked as a pre-existing failure.

### Consequences

✅ `ANS-UL`, `ANS-NL`, `TUL`, `TUL-LAST` resolve deterministically via alias — no log messages emitted
✅ `ANS-UL-FIRST` → `ANS-UL-MID` semantic repair logs INFO, not WARNING
✅ `XYZZY-TOTALLY-UNKNOWN` → `TXT` hard downgrade still logs WARNING
✅ `CJC-UL-FIRST/LAST`, `CJC-NN-BL-LAST`, `DIALOGUE` no longer trigger self-heal retries
✅ 9/9 `test_allowed_styles_enforcement.py` tests pass (4 new regression tests including log-level checks)
✅ 2 new TUL alias tests in `test_style_normalizer.py` pass
⚠️ `normalize_style("DIALOGUE")` still returns "DIA" not "DIA-MID" due to pre-existing normalizer bug (DIA not in LIST_BASES); tracked separately
⚠️ `_HARD_FALLBACK_TAGS` must be kept in sync if new generic fallback tags are added to `allowed_styles.json`

---

## Future Decisions (To Be Made)

### FD-001: Deterministic Pre-LLM Gating

**Context:** ~30-50% of paragraphs could be classified deterministically before LLM.

**Options:**
1. Implement deterministic gate (from plan file)
2. Keep current LLM-first approach

**Trade-offs:**
- **Pro:** 30-50% token cost reduction
- **Con:** More complexity, another layer to maintain
- **Con:** May reduce LLM classification quality (less context)

**Status:** Planned but not prioritized

---


## Decision Tracking

**Total ADRs:** 32 implemented
**Pending Decisions:** 1 future item
**Last Updated:** 2026-03-04

---

## How to Use This Document

1. **Before adding a feature:** Check if decision already exists
2. **When making a decision:** Add new ADR with context, rationale, alternatives, consequences
3. **When changing a decision:** Update status, add new ADR explaining change
4. **When removing a feature:** Mark ADR as deprecated with reason

**Format:**
```markdown
## ADR-XXX: Title

**Date:** YYYY-MM-DD
**Status:** ✅ Implemented | 🚧 In Progress | ❌ Rejected | 📋 Planned
**Context:** What problem are we solving?

### Decision
What we decided to do.

### Rationale
Why this decision makes sense.

### Alternatives Considered
What else we looked at and why we didn't choose them.

### Consequences
What are the implications (positive and negative)?
```
