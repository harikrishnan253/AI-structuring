# DOCUMENT COMPARISON ANALYSIS
## Bittner9781975243012-sec6_9: Original vs Processed vs Tagged

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **Current Accuracy** | **28.9%** (88/305 matched paragraphs) |
| **Target Accuracy** | ≥95% |
| **Gap** | 66.1 percentage points |

### Root Cause
The processed document **fails to detect list hierarchy levels**. It classifies everything as `BL-MID` when it should distinguish between:
- `BL-MID` (Level 0) - 25 items
- `BL2-MID` (Level 1) - 106 items  
- `BL3-MID` (Level 2) - 76 items

---

## DOCUMENT STATISTICS

| Document | Paragraphs | Unique Styles |
|----------|------------|---------------|
| Original | 315 | 3 |
| Processed | 315 | 13 |
| Tagged (Reference) | 308 | 13 |

---

## STYLE DISTRIBUTION COMPARISON

| Style | Processed | Tagged (Expected) | Difference |
|-------|-----------|-------------------|------------|
| **BL-FIRST** | 37 | 7 | +30 ❌ |
| **BL-MID** | 175 | 25 | +150 ❌ |
| **BL-LAST** | 7 | 7 | ✓ |
| **BL2-MID** | 0 | 106 | -106 ❌ |
| **BL3-MID** | 0 | 76 | -76 ❌ |
| CAU | 1 | 1 | ✓ |
| CN | 1 | 1 | ✓ |
| CT | 1 | 1 | ✓ |
| H1 | 7 | 7 | ✓ |
| PMI | 10 | 2 | +8 |
| SR | 61 | 72 | -11 |
| SRH1 | 1 | 1 | ✓ |

**Critical Finding:** The system produces **0 BL2-MID** and **0 BL3-MID** when it should produce 106 and 76 respectively.

---

## ERROR BREAKDOWN

| Error Type | Count | % of Errors |
|------------|-------|-------------|
| BL-MID → should be BL2-MID | 95 | 43.8% |
| BL-MID → should be BL3-MID | 73 | 33.6% |
| BL-FIRST → should be BL-MID | 18 | 8.3% |
| REF-N → should be SR | 11 | 5.1% |
| BL-FIRST → should be BL2-MID | 6 | 2.8% |
| BL-FIRST → should be BL-LAST | 6 | 2.8% |
| Other | 8 | 3.7% |
| **Total Errors** | **217** | **100%** |

**77.4% of all errors are BL-MID misclassified as BL2-MID or BL3-MID**

---

## BULLET CHARACTER ANALYSIS

### Tagged Document (Reference) - CORRECT PATTERNS

| First Character | Unicode | Count | Styles |
|-----------------|---------|-------|--------|
| **▲** Triangle | U+25B2 | 36 | BL-MID (24), BL-FIRST (6), BL-LAST (6) |
| **o** lowercase | U+006F | 133 | BL2-MID (106), BL3-MID (27) |
| **●** Wingdings bullet | U+F0B7 | 47 | BL3-MID (44), BL-FIRST/MID/LAST (3) |
| **■** Wingdings square | U+F0A7 | 5 | BL3-MID (5) |
| **1-9** Numbers | U+0031-0039 | 72 | SR (72) |
| **<** Marker tags | U+003C | 13 | H1 (7), PMI (2), CN/CT/CAU (3), SRH1 (1) |

### Processed Document - INCORRECT PATTERNS

| First Character | Count | Styles Assigned |
|-----------------|-------|-----------------|
| Various letters (A-Z, a-z) | 200+ | BL-MID, BL-FIRST, SR |
| **<** Marker tags | 21 | PMI (10), H1 (7), CN/CT/CAU |

**Problem:** The processed document sees the TEXT content (starting with letters like "Grade", "Colitis", etc.) instead of the BULLET CHARACTERS.

---

## ROOT CAUSE ANALYSIS

### The Core Issue

The processed document **strips or loses the bullet characters** during processing. 

**Tagged document sees:**
```
▲  Definitions                    → BL-FIRST (triangle = Level 0)
   o  Grading diarrhea (CTCAE)    → BL2-MID  (circle = Level 1)
      ●  Grade 1: Increase...      → BL3-MID  (bullet = Level 2)
```

**Processed document sees:**
```
Definitions                        → BL-FIRST (no bullet detected)
Grading diarrhea (CTCAE)          → BL-MID   (no bullet detected)
Grade 1: Increase...              → BL-MID   (no bullet detected)
```

### Why Bullets Are Lost

1. **python-docx text extraction** may not preserve Wingdings/Symbol font characters
2. **The bullet characters are in private use area** (F0B7, F0A7) which require special font handling
3. **OOXML numPr** may not be being read correctly for visual bullet character

---

## CORRECT HIERARCHY MAPPING (from Tagged Document)

```
LEVEL 0 (BL-*):
├── First character: ▲ (U+25B2 Triangle)
├── Styles: BL-FIRST, BL-MID, BL-LAST
├── Examples: "Definitions", "Epidemiology", "Key Pathophysiology"
└── Count: 36 items

LEVEL 1 (BL2-*):  
├── First character: o (U+006F lowercase o)
├── Style: BL2-MID only
├── Examples: "Grading diarrhea", "Work-up", "Second-line therapies"
└── Count: 106 items

LEVEL 2 (BL3-*):
├── First characters: 
│   ├── ● (U+F0B7 Wingdings bullet) - 44 items
│   ├── o (U+006F lowercase o) - 27 items (context-dependent!)
│   └── ■ (U+F0A7 Wingdings square) - 5 items
├── Style: BL3-MID only
├── Examples: "Grade 1:", "Grade 2:", "Infliximab", "Vedolizumab"
└── Count: 76 items
```

### Important Discovery: Context-Dependent Level

The **lowercase 'o'** (U+006F) can be either:
- **BL2-MID** (106 times) - when directly under ▲ triangle
- **BL3-MID** (27 times) - when under another 'o' that ends with ":"

This is the **Parent Context Pattern** we identified earlier!

---

## PARENT CONTEXT EXAMPLES (from Tagged)

```
[10] BL2-MID:  o  Grading diarrhea (CTCAE 5.0)     ← PARENT (ends implicitly)
[11] BL3-MID:  ●  Grade 1: Increase of <4...       ← CHILD (promoted by parent)
[12] BL3-MID:  ●  Grade 2: Increase of four...     ← CHILD
...

[30] BL2-MID:  o  Work-up (imaging and clinical assessment):  ← PARENT (ends with ":")
[31] BL3-MID:  o  Review concomitant medications...            ← CHILD (same 'o' but Level 2!)
[32] BL3-MID:  o  Blood (CBC, CMP, and TSH)...                 ← CHILD
...

[39] BL2-MID:  o  Second-line therapies for refractory...     ← PARENT
[40] BL3-MID:  o  Infliximab (preferred)                       ← CHILD
[41] BL3-MID:  o  Vedolizumab                                  ← CHILD
```

---

## SOLUTION REQUIREMENTS

### 1. Read Bullet Characters from OOXML

Extract from `numbering.xml`:
```xml
<w:abstractNum>
  <w:lvl w:ilvl="0">
    <w:numFmt w:val="bullet"/>
    <w:lvlText w:val="▲"/>  <!-- Triangle for Level 0 -->
  </w:lvl>
  <w:lvl w:ilvl="1">
    <w:numFmt w:val="bullet"/>
    <w:lvlText w:val="o"/>   <!-- Circle for Level 1 -->
  </w:lvl>
  <w:lvl w:ilvl="2">
    <w:numFmt w:val="bullet"/>
    <w:lvlText w:val=""/>  <!-- Wingdings bullet for Level 2 -->
  </w:lvl>
</w:abstractNum>
```

### 2. Level Detection Logic

```python
def detect_level(paragraph, parent_context):
    first_char = get_first_visible_char(paragraph)
    first_char_hex = f'{ord(first_char):04X}'
    
    # Level 0: Triangle
    if first_char_hex == '25B2':  # ▲
        return 0, reset_parent_context()
    
    # Level 2: Wingdings bullet or square
    if first_char_hex in ('F0B7', 'F0A7'):  # ● or ■
        return 2, parent_context
    
    # Level 1 or 2: lowercase 'o'
    if first_char_hex == '006F':  # o
        if parent_context.is_active:
            return 2, parent_context  # Promoted by parent
        else:
            # Check if this is a parent trigger
            if is_parent_trigger(paragraph.text):
                return 1, activate_parent_context()
            return 1, parent_context
    
    return None, parent_context  # Not a list item
```

### 3. Parent Trigger Detection

```python
PARENT_TRIGGERS = [
    r'grading\b',
    r'work-?up\b', 
    r'second-?line\s+therap',
    r'third-?line',
    r'specific\s+recommend',
    r'characteristics\s*:',
    r'diagnosis\s*:',
    r'symptoms\s*:',
]

def is_parent_trigger(text):
    clean = text.lower().strip()
    
    # Check patterns
    for pattern in PARENT_TRIGGERS:
        if re.match(pattern, clean):
            return True
    
    # Short items ending with colon
    if len(clean) < 60 and clean.endswith(':'):
        return True
    
    # Classification pattern: "Something (SYSTEM X.X)"
    if re.search(r'\([A-Z]+\s*[\d.]+\)\s*$', text):
        return True
    
    return False
```

---

## EXPECTED ACCURACY IMPROVEMENT

| Metric | Current | After Fix |
|--------|---------|-----------|
| Overall Accuracy | 28.9% | **~95%+** |
| BL2-MID Detection | 0% | ~95% |
| BL3-MID Detection | 0% | ~95% |
| Position Accuracy | ~50% | ~95% |

### Breakdown by Fix

| Fix | Errors Resolved | Accuracy Gain |
|-----|-----------------|---------------|
| Detect BL2-MID from 'o' char | 95 | +31% |
| Detect BL3-MID from ●/■/context | 73 | +24% |
| Fix BL-FIRST/MID/LAST positions | 24 | +8% |
| Fix SR vs REF-N | 11 | +4% |
| **Total** | **203** | **+67%** |

---

## FILES TO MODIFY

1. **`backend/processor/list_hierarchy_detector.py`** (CREATE)
   - OOXML bullet character extraction
   - Level detection from character
   - Parent context tracking

2. **`backend/processor/ingestion.py`** (MODIFY)
   - Integrate bullet detection
   - Add semantic_level to metadata

3. **`backend/processor/classifier.py`** (MODIFY)  
   - Use semantic_level for high-confidence classification
   - Bypass LLM for list items with detected levels

4. **`backend/processor/validator.py`** (MODIFY)
   - Add FIRST/MID/LAST position correction

---

## TEST CASES

### Test 1: Triangle Detection
```
Input:  "▲\tDefinitions"
Output: semantic_level=0, style_prefix="BL-"
```

### Test 2: Circle at Level 1
```
Input:  "o\tGrading diarrhea (CTCAE 5.0)"
Parent: None
Output: semantic_level=1, style_prefix="BL2-", is_parent_trigger=True
```

### Test 3: Circle Promoted to Level 2
```
Input:  "o\tReview concomitant medications..."
Parent: Active (from "Work-up:")
Output: semantic_level=2, style_prefix="BL3-"
```

### Test 4: Wingdings Bullet
```
Input:  "●\tGrade 1: Increase of <4 stools"
Output: semantic_level=2, style_prefix="BL3-"
```

### Test 5: Numbered Reference
```
Input:  "1.\tBrahmer JR, Abu-Sbeih H..."
Zone:   BACK_MATTER
Output: style="SR"
```
