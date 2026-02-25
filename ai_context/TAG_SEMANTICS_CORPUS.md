# Tag Semantics (Corpus-Derived)

Source: `Tag files.zip` manually tagged corpus (32 usable DOCX files analyzed on 2026-02-24; 1 temp `~$` file excluded).

## Purpose

This document captures *how tags are applied semantically* in the tagged corpus so the engine can make better deterministic repairs and normalization decisions.

It is not a replacement for `allowed_styles.json`; it is a behavior guide for:
- `style_normalizer.py`
- `validator.py`
- list/zone normalizers
- future rule-learning / grounded heuristics

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

## Recommended Next Improvements

1. Add a corpus-mined alias generation report (frequency-ranked unknown styles -> proposed canonical tag).
2. Learn family-specific list transitions (`FIRST -> MID* -> LAST`) from the tagged corpus.
3. Add section-family-aware list position inference (`KT`, `OBJ`, `EOC`, `RQ`, `ANS`) when `list_position` metadata is weak.
4. Add DOCX-pair regressions for recurring list-heavy publishers (`Cuffe`, `Taylor`, `Jensen`, `Karayalcin`).
