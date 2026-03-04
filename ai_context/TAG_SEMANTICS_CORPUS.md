# Tag Semantics (Corpus-Derived)

Source: `Tag files.zip` manually tagged corpus (32 usable DOCX files analyzed on 2026-02-24; 1 temp `~$` file excluded).

**Offline artifacts produced (2026-02-27):** Corpus analysis now generates three pre-built artifact files in `backend/data/`:
- `tag_semantics_knowledge.json` — zone-tag priors (`zone_tag_priors`) and tag family groupings (`tag_families`)
- `tag_transition_priors.json` — sequential tag transition probabilities (`global_transitions`)
- `style_alias_candidates.json` — publisher alias candidates with confidence ≥ 0.70

These artifacts are built offline by `backend/tools/build_semantic_knowledge.py` and are **never loaded at classification time**. They are consumed by:
- `backend/processor/rule_learner.py` — semantic enrichment of deterministic rules (`enrich_from_semantic_artifacts()`)
- `backend/tools/eval_generalization.py` — ablation evaluation predictor modes
- `backend/processor/classifier.py` — receives only generalized zone-prior hints in the prompt; never raw corpus docs

## Purpose

This document captures *how tags are applied semantically* in the tagged corpus so the engine can make better deterministic repairs and normalization decisions.

It is not a replacement for `allowed_styles.json`; it is a behavior guide for:
- `style_normalizer.py`
- `validator.py`
- list/zone normalizers
- offline rule-learning (`rule_learner.py`) and generalization evaluation (`eval_generalization.py`)

## Core Semantic Patterns

## 1. Tag Families Encode Zone + Function, Not Just Style Names

- `H*` / `H10` / `H20` / `H21`: heading hierarchy + publisher-specific heading variants
- `REF*`: reference headings/items (`REFH1`, `REFH2`, `REF-N`, `REF-U`)
- `T*` / `TH*` / `TFN` / `TSN`: table captions, headers, cells, footnotes, source notes
- `BX*`, `NBX*`, `UNT*`: box-specific title/body/list semantics
- `OBJ-*`, `KT-*`, `KP-*`, `EOC-*`, `RQ-*`, `QUES-*`, `ANS-*`: section-specific semantic list/text families

Implication:
- When repairing list position (`FIRST/MID/LAST`), preserve the semantic family prefix whenever possible.
- Example: `KT-BL-MID -> KT-BL-FIRST`, not `BL-FIRST`.

## 2. Positional List Suffixes Are Structural Semantics

The corpus uses `-FIRST/-MID/-LAST` as meaningful sequencing tags.

Observed across families:
- `BL-*`, `NL-*`, `UL-*`
- `KT-BL-*`
- `OBJ-NL-*`, `OBJ-BL-*`
- `EOC-NL-*`
- `BX*-BL-*`, `NBX-BL-*`
- `RQ-LL2-*` (nested/lettered review-question list family)
- `TBL-*`, `TNL-*` (table lists)

Implication:
- Do **not** strip positional suffixes from nested list bases like `BL2-MID` or `KT-BL2-MID`.
- Fallback to `MID` only when a corpus/publisher family lacks `FIRST`/`LAST` variants.

## 3. Publisher Raw Style Names Frequently Need Semantic Normalization

Common recurring raw forms (examples from corpus):
- `BulletList1first`, `BulletList1last`
- `NumberList1first`, `NumberList1last`
- `BulletList2`
- `EOCREF`, `EOCNLLL`, `EOCNL`
- `COKTL`
- `BX1BL`, `BX1BLF`, `BX1BLL`, `BX1UNL`, `BX1T`
- `NBX1-TXT-FLUSH`
- `TBL-MID0`, `TBL-FIRST0`, `TBL-LAST0`

Implication:
- Prefer alias / heuristic normalization before fuzzy fallback.
- Many “unknown styles” are publisher naming variants, not hallucinated tags.

## 4. Marker Paragraphs Must Remain PMI

Marker-only paragraphs (e.g. `<NOTE>`, `</NOTE>`, `<BOX>`, `</BL>`) appear in tagged corpora and should remain structural markers (`PMI`), not semantic content tags.

Implication:
- Marker handling must override model drift, even if the incoming tag appears valid.

## 5. Table Semantics Are Often Mixed With Publisher Names

The corpus includes both canonical and publisher-specific table naming conventions:
- canonical: `T1`, `T2`, `T4`, `TBL-*`, `TFN`
- publisher raw styles: `TableBody`, `TableColumnHead1`, `TB`, `Exhibit-TB-BulletList1`

Implication:
- Table normalization should infer semantic table roles rather than relying only on raw style names.
- Table list runs may span rows/columns and still need positional normalization.

## 6. Reference Semantics Are Triggered By Zone + Pattern

Reference entries are not always tagged consistently in raw input styles, but semantic output is stable:
- heading: `REFH1`/`REFH2`
- entries: `REF-N`, `REF-U`

Implication:
- Reference zone detection + entry pattern checks should dominate raw style names.

## List Handling Guidance (Priority Issue)

The corpus indicates list accuracy depends on three layers working together:

1. Raw-style normalization (publisher aliases -> canonical list family)
2. XML/metadata structure (`list_kind`, `list_position`, numbering)
3. Semantic family preservation during validator repairs

Current high-value rule:
- If a tag is already a semantic list family (`KT-BL-*`, `RQ-LL2-*`, `EOC-NL-*`, etc.), align only the positional suffix and preserve the family.

## What Has Been Done (as of 2026-03-02)

The following items from the original "Recommended Next Improvements" are now implemented:

1. **Alias generation report** — `style_alias_candidates.json` produced by `build_semantic_knowledge.py`; consumed by `eval_generalization.py` predictor chain (alias mode).
2. **Family-specific list transitions** — `tag_transition_priors.json` records `global_transitions` per source tag; used by `rule_learner.py` `enrich_from_semantic_artifacts()` to propose `prev_tag=X` candidate rules.
3. **Section-family-aware inference** — zone-prior distribution from `tag_semantics_knowledge.json` seeds candidate rules and semantic predictor in `eval_generalization.py`.
4. **Generalization evaluation** — `backend/tools/eval_generalization.py` provides book-level and publisher-level holdout evaluation with five additive ablation modes.
5. **Marker-lock diagnostic precision** — `relock_marker_classifications()` now distinguishes Case A (true `skip_llm=True` leak) from Case B (post-hoc marker detection without prior lock). Only Case A increments the `leaked_to_llm` metric and triggers a WARNING; Case B is logged at DEBUG only. PMI re-lock behavior unchanged. (ADR-030, 2026-03-02)
6. **Eval generalization metric extension** — three new metrics added to `eval_generalization.py`: `invalid_tag_rate` (% predictions not in `allowed_styles.json`), `structure_guard_fail_rate` (% structural-category mismatches on list/heading entries, simulating SG failure probability), and `table_per_tag` (per-gold-tag accuracy breakdown for TABLE-zone entries). Report extended to 120 columns; TABLE SEMANTICS DETAIL section appended. (ADR-031, 2026-03-02)

## Remaining Known Gaps

- Publisher-pair regression tests for `Cuffe`, `Taylor`, `Jensen`, `Karayalcin` are not yet automated (require DOCX input fixtures).
- `prev_tag` rules cannot fire via `apply_rules()` at classification time without explicit `prev_tag` metadata injection (see ADR-029, KNOWN_ISSUES.md).
- `structure_guard_fail_rate` is a flat-holdout simulation metric and may diverge from actual Structure Guard outcomes for paragraphs at zone boundaries where sequential context matters.
