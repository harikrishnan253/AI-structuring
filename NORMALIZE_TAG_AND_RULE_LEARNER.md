# Normalize Tag & Rule Learner Implementation - Summary

## Status: 🟡 IN PROGRESS (2/7 tasks complete)

---

## Goal
Fix the "complete mess" outputs by making the classifier grounded on manual-tagged ground truth and hard-constrained to allowed_styles.json.

## Completed Tasks

### ✅ Task 1: Implement normalize_tag() Function

**File:** `backend/app/services/style_normalizer.py`

**Changes:**
1. Added `normalize_tag()` public API function that enforces membership in allowed_styles.json
2. Enhanced `normalize_style()` with:
   - Illegal prefix stripping: BX4-, NBX1-, TBL-
   - SK_H1-SK_H6 → TH1-TH6 semantic mapping
   - Similarity-based fallback using `difflib.SequenceMatcher`
   - Hierarchical fallback logic for headings, lists, references, figures, tables
3. Added `_find_closest_style()` helper function for intelligent fallback
4. Loaded allowed_styles.json for membership validation

**Key Features:**
```python
def normalize_tag(tag: str, meta: dict | None = None) -> str:
    """
    Public API for normalizing tags with full membership enforcement.

    - Strips illegal prefixes (BX4-, NBX1-, TBL-, SK_ except SK_H1-SK_H6 → TH1-TH6)
    - Expands aliases (T-DIR → T, Cn → CN, etc.)
    - Enforces membership in allowed_styles.json
    - Returns closest valid style if not in allowed_styles
    """
```

**Fallback Hierarchy:**
- Headings: H3 → H2 → H1 → TXT
- Bullet lists: BL-MID → BL → TXT
- Numbered lists: NL-MID → NL → TXT
- References: REF-U → REF-N → TXT
- Figures: FIG-LEG → TXT
- Tables: T → TXT
- Ultimate fallback: TXT

**Updated Files:**
- `backend/app/services/style_normalizer.py` (enhanced with normalize_tag())
- `backend/config/style_aliases.json` (added T-DIR → T, Cn → CN, Ct → CT, Pn → PN, Pt → PT)
- `backend/processor/classifier.py` (integrated normalize_tag() in _force_invalid_to_txt())

**Integration:**
Updated classifier's `_force_invalid_to_txt()` to:
1. Apply basic alias mapping (`_map_tag_alias`)
2. Apply `normalize_tag()` with membership enforcement
3. Fall back to grounded retrieval if still generic (TXT)
4. Validate grounded tags through `normalize_tag()` again

---

### ✅ Task 2: Create Rule Learner Module

**File:** `backend/processor/rule_learner.py` (NEW - 588 lines)

**Components:**

#### 1. FeatureExtractor Class
Extracts deterministic features from paragraph text:
- **Text characteristics**: length, word_count, is_empty, is_short, is_long
- **Numbering patterns**: has_number_prefix, has_letter_prefix, has_roman_prefix, has_bullet
- **Formatting**: is_all_caps, starts_with_digit, ends_with_period, ends_with_colon
- **Content patterns**: looks_like_heading, looks_like_caption, looks_like_reference, looks_like_footnote
- **Zone and context**: zone, is_in_table, is_in_box, is_in_back_matter, list_kind, list_position

Regex patterns used:
```python
NUMBERED_RE = r"^\s*(\d+[\.\)]|\(\d+\)|\[\d+\])\s+"
LETTERED_RE = r"^\s*([a-z][\.\)]|\([a-z]\))\s+"
ROMAN_RE = r"^\s*([ivxlcdm]+[\.\)]|\([ivxlcdm]+\))\s+"
BULLET_RE = r"^\s*[\u2022\u25CF\-\*\u2013\u2014]\s+"
ALL_CAPS_RE = r"^[A-Z\s\d\-,.:;!?\'\"]+$"
```

#### 2. DocumentAligner Class
Aligns paragraphs between original and manually-tagged documents:
- Uses `difflib.SequenceMatcher` for robust text similarity
- Default similarity threshold: 0.85
- Greedy alignment algorithm (finds best match for each original paragraph)
- Normalizes text (whitespace, NBSP, case) before comparison
- Tracks used tagged paragraphs to avoid double-matching

#### 3. RuleLearner Class
Learns deterministic if-then rules from aligned documents:
- Loads ground truth from `ground_truth.jsonl`
- Extracts training examples with features and labels
- Learns rules with configurable min_support and min_confidence
- Stores rules in `learned_rules.json`
- Applies rules to predict tags for new text
- Generates human-readable reports

**Rule Format:**
```json
{
  "condition": "has_number_prefix",
  "predicted_tag": "NL-FIRST",
  "support": 150,
  "total": 180,
  "confidence": 0.833
}
```

**CLI Usage:**
```bash
# Train rules from ground truth
python -m processor.rule_learner --train

# Generate report of learned rules
python -m processor.rule_learner --report

# Set log level
python -m processor.rule_learner --train --log-level DEBUG
```

**Output Files:**
- `backend/data/learned_rules.json` - Learned rules (overwritten on each training run)

**Report Format:**
```
================================================================================
LEARNED RULES REPORT
================================================================================

Total rules: 247

Top 50 rules by confidence:
--------------------------------------------------------------------------------
  1. IF has_number_prefix                           THEN NL-FIRST          (conf=92.3%, support=150/162)
  2. IF has_bullet                                   THEN BL-FIRST          (conf=89.1%, support=234/262)
  3. IF looks_like_heading                           THEN H3                (conf=85.7%, support=120/140)
  ...

--------------------------------------------------------------------------------
Tag Statistics:
--------------------------------------------------------------------------------

TXT (1234 examples):
  - length: 850 (68.9%)
  - word_count: 720 (58.3%)
  - ends_with_period: 980 (79.4%)

H3 (567 examples):
  - looks_like_heading: 485 (85.5%)
  - is_short: 450 (79.4%)
  - ends_with_colon: 120 (21.2%)
...
```

---

## Pending Tasks

### 🟡 Task 3: Update Classifier to "Grounded-First" Approach
- [ ] Apply learned rules BEFORE calling LLM
- [ ] Use RAG over manual-tagged set for few-shot examples
- [ ] Enforce strict output schema from allowed_styles.json
- [ ] Add post-processor to strip illegal prefixes from LLM output

### 🟡 Task 4: Fix Reference Section Detection
- [ ] Learn reference signatures from tagged docs (SR/SR2/REF-* transitions)
- [ ] Make trigger conservative (not just citation_density)
- [ ] Use grounded patterns instead of heuristics

### 🟡 Task 5: Update Validator with Semantic Remapping
- [ ] Add semantic remapping before downgrading (SK_H3 → TH3, not → T)
- [ ] Use similarity-based fallback from normalize_tag()
- [ ] Preserve meaningful distinctions

### 🟡 Task 6: Add Comprehensive Tests
- [ ] Test normalize_tag() prefix stripping
- [ ] Test normalize_tag() alias expansion
- [ ] Test normalize_tag() membership enforcement
- [ ] Test normalize_tag() similarity fallback
- [ ] Test reference-zone trigger logic
- [ ] Test allowed_styles enforcement in classifier

### 🟡 Task 7: Run Evaluation
- [ ] Run eval_accuracy.py before changes (baseline)
- [ ] Run eval_accuracy.py after changes
- [ ] Show improvements in accuracy, zone violations, coverage gaps

---

## Technical Details

### Files Created
1. `backend/processor/rule_learner.py` (NEW - 588 lines)

### Files Modified
1. `backend/app/services/style_normalizer.py` - Added normalize_tag() and _find_closest_style()
2. `backend/config/style_aliases.json` - Added T-DIR, Cn, Ct, Pn, Pt aliases
3. `backend/processor/classifier.py` - Integrated normalize_tag() in _force_invalid_to_txt()

### Syntax Validation
All files pass Python syntax check:
```bash
python -m py_compile app/services/style_normalizer.py processor/classifier.py processor/rule_learner.py
✅ No errors
```

---

## Non-Negotiable Rules Enforced

### ✅ Enforced
1. **Never invent styles**: normalize_tag() only returns styles from allowed_styles.json
2. **Strip illegal prefixes**: BX4-, NBX1-, TBL-, SK_ (except SK_H1-SK_H6)
3. **Semantic mapping**: SK_H1-SK_H6 → TH1-TH6 (table headings)
4. **Membership enforcement**: All tags validated against allowed_styles.json
5. **Similarity fallback**: Uses difflib.SequenceMatcher when tag not in allowed_styles

### 🟡 Partially Enforced (Pending Tasks 3-7)
6. **Never combine/prefix styles**: Need to add post-processor in classifier
7. **Grounded-first approach**: Need to apply rules before LLM
8. **Conservative reference detection**: Need to implement learned signatures
9. **Semantic remapping in validator**: Need to update validator logic

---

## Impact Summary

### Before normalize_tag()
```python
# LLM outputs: "BX4-TXT", "SK_H3", "TBL-H2", "T-DIR", "InvalidStyle123"
# Classifier: Keeps as-is or downgrades to TXT blindly
```

### After normalize_tag()
```python
# Input: "BX4-TXT" → Output: "TXT" (prefix stripped)
# Input: "SK_H3" → Output: "TH3" (semantic mapping)
# Input: "TBL-H2" → Output: "H2" (prefix stripped, then closest match)
# Input: "T-DIR" → Output: "T" (alias expansion)
# Input: "InvalidStyle123" → Output: "TXT" (similarity fallback to closest valid style)
```

### Rule Learner Benefits
- **Deterministic**: Rules are learned from ground truth, not heuristics
- **Explainable**: Each prediction comes with a rule (IF condition THEN tag)
- **Fast**: Rule application is O(1) lookup, no LLM call needed
- **Grounded**: Rules only predict tags that exist in manual-tagged training data
- **Reportable**: Human-readable reports show which features predict which tags

---

## Next Steps

1. **Integrate rules into classifier** (Task 3)
   - Load learned_rules.json at initialization
   - Apply rules before LLM call
   - Skip LLM if rule matches with high confidence

2. **Fix reference detection** (Task 4)
   - Learn SR/REFH1 transition patterns from ground truth
   - Replace citation_density heuristic with learned signatures

3. **Update validator** (Task 5)
   - Replace generic downgrading (→ T) with semantic remapping (SK_H3 → TH3)
   - Use normalize_tag() for fallback instead of hardcoded TXT

4. **Add tests** (Task 6)
   - Unit tests for normalize_tag()
   - Integration tests for classifier + rules
   - Tests for reference detection

5. **Evaluate improvements** (Task 7)
   - Run eval_accuracy.py to measure accuracy gains
   - Track reduction in zone violations
   - Measure coverage gap improvements

---

**Summary:** Successfully implemented normalize_tag() with prefix stripping, alias expansion, and membership enforcement. Created comprehensive rule learner module that learns deterministic if-then rules from ground truth. Integrated normalize_tag() into classifier for robust tag validation. Next: Apply rules before LLM, fix reference detection, and evaluate improvements.
