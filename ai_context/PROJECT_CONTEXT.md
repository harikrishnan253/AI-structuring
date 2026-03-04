# PROJECT CONTEXT

## Project Overview

**Name:** AI DOCX Structuring Pipeline
**Type:** Document Processing & Classification System
**Language:** Python
**Primary Goal:** Automated classification and styling of DOCX document paragraphs using LLM-based classification with deterministic validation gates.

## System Architecture

### High-Level Flow

```
Input DOCX
  ↓
Stage 1:   Document Ingestion (Block Extraction)
Stage 1b:  List Hierarchy Lock (pre-LLM, XML-based)
  ↓
Stage 1.5: Marker Lock (pre-LLM, skip_llm=True)
  ↓
Stage 2:   AI Classification (Gemini LLM)
  ↓
Stage 3:   Validation & Repair
           └─ Composite tag detection + STYLE_CANONICALIZATION log
  ↓
Stage 4:   Confidence Filtering
  ↓
Stage 4.5: Final Style Enforcement (HARD GATE)
           └─ Zone-safe fallbacks, 100% allowed_styles compliance
  ↓
Stage 5:   Document Reconstruction
  ↓
Stage 5.25: Table Title House Rules (post-reconstruction, structure-safe)
           └─ Canonicalize table captions (T1) without table movement/content mutation
  ↓
Stage 5.5: Structure Guard (HARD GATE)
  ↓
Stage 6:   Integrity Verification (HARD GATE)
  ↓
Stage 7:   Quality Scoring
  ↓
Output DOCX + Reports
```

### Core Components

**1. Processing Pipeline** (`backend/processor/pipeline.py`)
- Orchestrates entire document processing flow
- Integrates all validation gates
- Manages retry logic for quality improvement

**2. Block Extraction** (`backend/processor/blocks.py`)
- Extracts paragraphs, tables, metadata from DOCX
- Preserves structural information

**3. LLM Classifier** (`backend/processor/classifier.py`)
- Uses Google Gemini API for paragraph classification
- Implements caching and rule-based pre-filtering
- Supports FORCE_LLM mode for evaluation

**4. Style Enforcement** (`backend/processor/`)
- **Zone Styles** (`zone_styles.py`) — centralized zone-to-valid-styles mapping
- **Style Enforcement** (`style_enforcement.py`) — Stage 4.5 safety gate; zone-safe fallbacks
- **Validator** (`validator.py`) — composite tag detection, alias canonicalization, STYLE_CANONICALIZATION logging

**5. Validation Gates** (Sequential Hard Gates)
- **Structure Guard** (`backend/processor/structure_guard.py`)
  - Enforces style-only mutations
  - Validates no structural changes to document
- **Integrity Trigger** (`backend/processor/integrity.py`)
  - Content integrity: verifies all text preserved
  - Structural integrity: validates document structure
  - Emits first-diff diagnostics (`INTEGRITY_FIRST_DIFF`) with input/output metadata snapshots

**5a. Structural Invariants Contract** (`backend/processor/structural_invariants.py`)
- Centralized invariant definitions for paragraph/list/heading/table/section preservation
- Shared block-transform contract checks (count/order/id invariants)
- Used by pipeline stage wrappers and normalizers

**6. LLM Execution Guardrails** (`backend/processor/classifier.py`)
- Tracks `llm_audit` dict on every `classify()` call
- Validates cache integrity before skipping LLM
- Emits `LLM_EXECUTION_TRACE` and `LLM_INVOCATION_VALIDATED` logs
- Warns on `LLM_TOKEN_COUNT_ERROR` (token_count == 0 when invoked)

**6. Document Reconstruction** (`backend/processor/reconstruction.py`)
- Applies classified styles back to DOCX
- Generates review reports and JSON outputs
- Preserves source list/heading semantics (style-only mutation contract)
- Guards paragraph counts before/after reconstruction

**7. Post-Reconstruction Table Rules** (`backend/processor/table_title_enforcement.py`)
- Canonical table-title styling after reconstruction (Stage 5.25)
- Structure-safe (no table/paragraph insertion/deletion)
- Preserves title-equivalent semantics for legacy `Title` captions

**8. Queue / API Failure Reporting** (`backend/app/services/queue.py`, `backend/app/models/database.py`)
- Persists terminal FAILED states with `stage`, `error`, `diagnostics`
- Distinguishes expected pipeline failures vs unexpected `OUTPUT_MISSING`
- Frontend polling stops on terminal batch states and renders structured failure details

## Key Constraints

### 1. Processing Constraints
- **No Text Loss:** All input text must be preserved in output
- **No Structure Mutation:** Only style changes allowed, no paragraph merging/splitting/deletion
- **List/Heading Semantics Preserved:** Style changes must not mutate list XML or heading levels
- **Deterministic Validation:** No LLM in validation gates
- **Fail-Fast:** Pipeline stops immediately on validation failure

### 2. Performance Constraints
- Must handle 2000+ paragraph documents
- Integrity checks must complete in <1 minute
- O(n) complexity for validation operations

### 3. Quality Constraints
- Confidence threshold: 85%
- Quality scoring determines: PASS / RETRY / REVIEW
- Max 3 retry attempts with model escalation

### 4. LLM Constraints
- Primary model: `gemini-2.5-flash-lite` (fast, cost-effective)
- Strong model: `gemini-2.0-flash` (retry scenarios)
- Batch size: 75-100 paragraphs per API call (configurable)
- Token usage tracked for cost analysis

## Technology Stack

- **Language:** Python 3.13
- **Document Processing:** python-docx
- **LLM Provider:** Google Gemini API
- **Testing:** pytest
- **Task Queue:** Celery (Redis backend)
- **Database:** PostgreSQL (job metadata)
- **Web Framework:** Flask

## File Structure

```
backend/
├── processor/
│   ├── pipeline.py              # Main orchestration
│   ├── blocks.py                # DOCX extraction
│   ├── classifier.py            # LLM classification + execution audit
│   ├── zone_styles.py           # Zone-to-valid-styles mapping
│   ├── style_enforcement.py     # Stage 4.5 final style gate
│   ├── validator.py             # Composite detection + canonicalization
│   ├── structure_guard.py       # Style-only enforcement (Stage 5.5)
│   ├── integrity.py             # Content + structural validation (Stage 6)
│   ├── marker_lock.py           # Pre-LLM marker protection
│   ├── list_hierarchy.py        # Pre-LLM list locking from XML
│   ├── reconstruction.py        # DOCX generation
│   ├── table_title_enforcement.py # Post-reconstruction table caption house rules
│   ├── structural_invariants.py # Central invariant contract + block-stage assertions
│   └── [other processors...]
├── tests/
│   ├── test_zone_styles.py       # 14 tests
│   ├── test_style_enforcement.py # 27 tests
│   ├── test_llm_execution_audit.py # 10 tests
│   ├── test_structure_guard.py   # 33 tests
│   ├── test_integrity_trigger.py # 27 tests
│   ├── test_force_llm.py         # 14 tests
│   └── [other tests...]
├── tools/
│   ├── eval_generalization.py   # Offline ablation & generalization evaluation (no LLM)
│   └── build_semantic_knowledge.py    # Offline semantic artifact builder (Phase 1)
├── app/
│   ├── api/                     # Flask endpoints
│   └── services/                # Business logic
└── workers/
    └── celery_worker.py         # Async task processing

ai_context/                      # Project documentation (this folder)
├── PROJECT_CONTEXT.md
├── INTEGRITY_INVARIANTS.md
├── TAG_SEMANTICS_CORPUS.md
├── OFFLINE_PIPELINE_GUIDE.md   # Offline rule learning + generalization evaluation
├── SESSION_SNAPSHOT.md
├── DECISIONS_LOG.md
└── KNOWN_ISSUES.md
```

## Environment Variables

Key configuration (see `.env.example`):

```bash
# LLM Configuration
GOOGLE_API_KEY=<api_key>
GEMINI_MODEL_PRIMARY=gemini-2.5-pro
GEMINI_MODEL_STRONG=gemini-2.5-pro

# Processing Settings
CONFIDENCE_THRESHOLD=85
MAX_PARAGRAPHS_PER_CHUNK=100

# Evaluation Control
FORCE_LLM=false  # Set true to bypass caching for evaluation

# Rules Loading
REQUIRE_LEARNED_RULES=false  # Set true to hard-fail when learned_rules.json is missing
```

## Design Principles

1. **Deterministic Where Possible:** Use LLM only for classification, not validation
2. **Fail-Fast:** Stop processing immediately when validation fails
3. **Comprehensive Testing:** Each module has dedicated test suite
4. **Performance First:** O(n) algorithms, indexed lookups, batch processing
5. **Cost Optimization:** Caching, rule-based pre-filtering, appropriate model selection
6. **Transparency:** Detailed logging, structured metrics, error diagnostics

## Recent Hardening (2026-02-23 to 2026-02-24)

- Marker-lock (`skip_llm=True`) is now a hard exclusion before cache/rule/LLM eligibility and guarded at LLM payload build path.
- Table-title normalizer is structure-safe (retag only; no reorder/delete/insert).
- Reconstruction preserves paragraph count, list semantics (`numPr`/style-based lists), and heading semantics while allowing visual heading styles on non-heading source paragraphs.
- Integrity and structure guard use richer first-diff diagnostics (stage + paragraph index + metadata snapshots).
- Queue/API surfaces pipeline fail-fast reasons (`STRUCTURE_GUARD_FAIL`, `INTEGRITY_TRIGGER_FAIL`, etc.) instead of masking them with `OUTPUT_MISSING`.
- Missing learned rules file is optional by default (low-noise logging, strict mode via `REQUIRE_LEARNED_RULES=true`).
- DNS/network resolution errors (e.g., `getaddrinfo failed`) are treated as transient and retried with backoff before chunk fallback.
- Default Gemini processing model is now `gemini-2.5-pro` (still configurable via env vars).

## Tagged Corpus Calibration (30-File Zip, 2026-02-24)

- Imported and analyzed 32 usable tagged DOCX files from `Tag files.zip` (plus 1 temp lock file excluded).
- Corpus inventory found `540` unique paragraph styles and many publisher-specific aliases / variants.
- High-signal engine updates based on this corpus:
  - Fixed `style_normalizer` nested-list suffix bug that incorrectly stripped position suffixes from tags like `BL2-MID`, `BL2-LAST`, `KT-BL2-MID`, `TBL3-MID`.
- Added validator-side semantic list-family position alignment so repairs preserve family prefixes (`KT-*`, `EOC-*`, `RQ-*`, etc.) when correcting `FIRST/MID/LAST`.
- Added corpus-driven aliases for recurring publisher variants (e.g., `BulletList1first/last`, `EOCREF`, `COKTL`, `BX1BL`, `NBX1-TXT-FLUSH`, `TBL-MID0`, `T10`, `T20`, etc.).
- Added corpus semantics reference: `ai_context/TAG_SEMANTICS_CORPUS.md` (tag family behavior, list semantics, marker/table/reference guidance).
  - Expanded allowed-style vocab for real tags observed in corpus-driven runs (e.g., `NBX-FIG-LEG`, `NBX-TXT-FLUSH`, `BL2-LAST`, `KT-BL2-MID`, `KT-BL2-LAST`, `SP-H1`).
- Practical impact:
  - Fewer `Tag not allowed, downgraded` repairs
  - Fewer `zone-restriction: unknown style ...` replacements
  - Better preservation of nested list and box/table semantics from tagged corpora
  - List handling remains the highest-variance area and continues to need more corpus-driven rules

## External Dependencies

- Google Gemini API (classification)
- Redis (Celery backend, optional caching)
- PostgreSQL (job metadata)
- python-docx (document processing)

## Non-Functional Requirements

- **Reliability:** Validation gates ensure data integrity
- **Observability:** Structured logging, token usage tracking, quality metrics
- **Testability:** 125+ tests covering all critical paths
- **Maintainability:** Modular design, clear separation of concerns
- **Cost Control:** Token usage minimization, caching strategy
