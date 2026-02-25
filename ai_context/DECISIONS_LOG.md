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

**Total ADRs:** 24 implemented
**Pending Decisions:** 1 future item
**Last Updated:** 2026-02-24

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
