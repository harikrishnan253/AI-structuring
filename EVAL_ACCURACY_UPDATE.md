# Eval Accuracy Update - Summary

## Problem
The previous `tools/eval_accuracy.py` script evaluated predictions against style sequences extracted directly from manual-tagged DOCX files using brittle assumptions. This approach:
- Re-derived labels by extracting Word paragraph styles
- Didn't use the high-quality aligned ground truth dataset (ground_truth.jsonl)
- Had no visibility into alignment quality or UNMAPPED entries
- Couldn't track zone violations or coverage gaps systematically

## Solution

### 1. **Load Real Ground Truth Dataset**
Now loads `backend/data/ground_truth.jsonl` which contains:
- 11,496 carefully aligned training examples
- High-quality alignment scores (82.39% ≥ 0.85 threshold)
- Canonical gold tags from manual-tagged files
- Zone information for each paragraph
- Explicit UNMAPPED markers for entries without manual tags

```python
def load_ground_truth():
    """
    Load ground truth dataset from ground_truth.jsonl.
    Returns a dict: {doc_id: [entries sorted by para_index]}
    """
```

**Output:**
```
=== Ground Truth Dataset ===
Gold source: manual tagged files.zip
Total entries: 11496
Mapped entries: 10804 (94.0%)
UNMAPPED entries: 692 (6.0%)
Documents: 30
```

### 2. **Align by para_index, Not Re-Derivation**
New evaluation function aligns predictions to gold entries using para_index:

```python
def _evaluate_predictions_against_gold(base_name, gold_entries, prediction_blocks):
    """
    Evaluate predictions against gold standard entries aligned by para_index.

    Returns metrics: total, matches, accuracy, mismatches, coverage_gaps,
                     zone_violations, unmapped_count
    """
```

**Key Features:**
- Aligns predictions to gold entries by para_index
- Falls back to block order if para_index not in metadata
- Skips UNMAPPED entries in accuracy calculation (explicit handling)
- Identifies coverage gaps (gold entries without predictions)
- Detects zone violations (predicted tag not valid for zone)

### 3. **New Metrics Computed**

#### Accuracy
- **Total gold entries**: Count of gold entries with mapped tags (excludes UNMAPPED)
- **Matched predictions**: Predictions that match gold tag exactly
- **Accuracy**: matches / total * 100

#### Confusion Matrix
- Top mismatches: (gold_tag → predicted_tag) with counts
- Shows which gold tags are being mispredicted

#### Coverage Gaps
- Gold entries that have no prediction
- Identifies missing classifications
- Grouped by gold tag to see patterns

#### Zone Violations
- Predictions that don't match zone constraints
- Tracks: zone, gold_tag, predicted_tag, para_index
- Uses zone constraints from classifier.py

### 4. **Explicit UNMAPPED Handling**
```python
# Skip UNMAPPED entries in accuracy calculation
if gold_tag == "UNMAPPED":
    unmapped_count += 1
    continue
```

**Benefits:**
- UNMAPPED entries don't pollute accuracy metrics
- Explicit count shown in reports
- Clear understanding of dataset quality

### 5. **Skip Docs Without Gold Data**
```python
doc_id = _find_doc_id_match(base, ground_truth)
if not doc_id:
    print(f"\n[SKIP] {base}: No ground truth data found")
    continue
```

**Benefits:**
- No silent fallback to brittle heuristics
- Clear logging of skipped documents
- Only evaluates docs with real ground truth

### 6. **Enhanced Reporting**

#### Per-Document Report:
```
=== Eval Report ===
Doc: Acharya9781975261764-ch002
Total gold entries: 150
Matched predictions: 142
Accuracy: 94.67%
UNMAPPED gold entries: 5
Coverage gaps (no prediction): 2
Zone violations: 1
Reference zone blocks: 45 (trigger=REFERENCES_HEADER)
...

Top 20 mismatches (gold → predicted):
  H2 → H3: 3
  BL-MID → BL-LAST: 2
  TXT-FLUSH → TXT: 1

Top 10 coverage gaps (gold tag, no prediction):
  FIG-LEG: 1
  TSN: 1

Top 10 zone violations (predicted tag not valid for zone):
  TABLE: BL-FIRST (1x)
```

#### Overall Summary:
```
============================================================
=== OVERALL SUMMARY ===
============================================================

--- DEV SET ---
Total gold entries: 450
Matched predictions: 420
Accuracy: 93.33%
Coverage gaps: 8
Zone violations: 12

DEV Top 30 mismatches (gold → predicted):
  H2 → H3: 15
  BL-MID → BL-LAST: 10
  ...

DEV Top 20 coverage gaps (gold tag, no prediction):
  FIG-LEG: 3
  TSN: 2

DEV Top 20 zone violations:
  TABLE: BL-FIRST (5x)
  BACK_MATTER: T (4x)

------------------------------------------------------------
--- HELDOUT SET ---
Total gold entries: 200
Matched predictions: 185
Accuracy: 92.50%
...
```

## Benefits

### Before (Brittle Assumptions):
- ❌ Re-derived labels from DOCX styles
- ❌ No ground truth alignment quality visibility
- ❌ No UNMAPPED handling
- ❌ No zone violation tracking
- ❌ No coverage gap analysis
- ❌ Inconsistent with training data

### After (Real Ground Truth):
- ✅ Uses aligned ground truth dataset (ground_truth.jsonl)
- ✅ Shows alignment quality (94.0% mapped)
- ✅ Explicit UNMAPPED handling
- ✅ Zone violation detection
- ✅ Coverage gap analysis
- ✅ Consistent with training data
- ✅ Clear gold source attribution

## Files Modified

1. **`tools/eval_accuracy.py`**
   - Added `load_ground_truth()` function
   - Added `_find_doc_id_match()` helper
   - Added `_evaluate_predictions_against_gold()` evaluation function
   - Updated `_print_report()` to show new metrics
   - Updated `main()` to use ground truth instead of DOCX extraction
   - Added zone violation detection with constraints from classifier.py

## Usage

```bash
cd c:\Users\harikrishnam\Desktop\AI-structuring-main
python tools/eval_accuracy.py
```

**Expected Output:**
1. Ground truth dataset statistics
2. Per-document evaluation reports
3. Overall DEV and HELDOUT summaries
4. Accuracy, confusion matrix, coverage gaps, zone violations

## Technical Details

### Ground Truth Structure
```json
{
  "doc_id": "Acharya9781975261764-ch002_tag",
  "para_index": 0,
  "text": "Chapter 2",
  "gold_tag": "CN",
  "canonical_gold_tag": "CN",
  "alignment_score": 1.0,
  "notes": "pair_method:exact_stem; tag_map:direct; zone:body",
  "zone": "body"
}
```

### Alignment Logic
1. Ground truth entries indexed by doc_id
2. Predictions indexed by para_index (or block order fallback)
3. For each gold entry:
   - Skip if UNMAPPED
   - Look up prediction by para_index
   - Compare canonical_gold_tag vs normalized predicted tag
   - Check zone constraints if applicable

### Zone Constraints
From `backend/processor/classifier.py`:
- TABLE: T, TD, TH1-TH6, T-DIR, TN, TSN, etc.
- BOX/BOX1-4: BX*-TXT, BX*-H, BX*-BL-*
- BACK_MATTER: REF-N, REF-U, REFH1, UNFIG-LEG, TSN, etc.

## Validation

### Test Syntax:
```bash
python -m py_compile tools/eval_accuracy.py
```
✅ No syntax errors

### Run Full Evaluation:
```bash
python tools/eval_accuracy.py
```

**Expected:**
- Loads 11,496 ground truth entries
- Processes 5+ selected documents (DEV + HELDOUT)
- Shows per-document accuracy reports
- Shows overall DEV and HELDOUT summaries
- No crashes or errors

## Impact

### Accuracy Evaluation
- **Before**: Compared against Word styles (brittle, inconsistent)
- **After**: Compared against canonical gold tags from ground truth (robust, consistent)

### Metric Visibility
- **Before**: Only total/matches/mismatches
- **After**: Accuracy, confusion matrix, coverage gaps, zone violations, UNMAPPED counts

### Reproducibility
- **Before**: Depends on DOCX extraction behavior
- **After**: Depends on stable ground truth dataset

### Debugging
- **Before**: Hard to identify specific issues
- **After**: Clear visibility into coverage gaps, zone violations, alignment quality

---

**Summary:** The evaluation script now uses the real ground truth dataset produced from manual-tagged files, providing accurate, reproducible, and comprehensive evaluation metrics for the AI style classifier.
