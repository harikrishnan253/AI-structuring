# INTEGRITY INVARIANTS CONTRACT

Centralized contract for structural safety in the DOCX pipeline.

Primary code reference: `backend/processor/structural_invariants.py`

## Hard Structural Invariants (must be preserved)

1. Paragraph count and paragraph order (same paragraph index mapping)
2. List semantics at each paragraph index:
   - list item status
   - list level
   - list ID (or style-based-list sentinel semantics)
3. Heading level at each paragraph index
4. Table structure:
   - table count
   - row count
   - column count
5. Section structure:
   - section count
   - section break types

## Block Transform Contract (normalizers / locks)

Default rule for block transforms in pipeline stages:

- Preserve block count
- Preserve ordered block IDs
- Do not rewrite IDs
- Do not merge/split/skip blocks

Additional rule for style/tag-only normalizers:

- Preserve block text (only `tag` / metadata normalization allowed)

## Enforcement Points

- Pre/post block-stage assertions in `backend/processor/pipeline.py`
- Normalizer-local assertions (e.g. `backend/processor/table_title_normalizer.py`)
- Reconstruction paragraph-count guard in `backend/processor/reconstruction.py`
- Hard validation gates:
  - `backend/processor/structure_guard.py`
  - `backend/processor/integrity.py`

## Failure Diagnostics

When a violation occurs, logs should identify:

- stage name
- paragraph index (or block index)
- block ID (for block-stage transforms)
- input/output structural metadata snapshot (style/list/heading/text preview)

