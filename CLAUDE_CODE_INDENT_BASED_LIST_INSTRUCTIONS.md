# CLAUDE CODE INSTRUCTIONS: Indent-Based List Hierarchy Detection

## Key Understanding

**The bullet SYMBOL does not determine the level. INDENTATION determines the level.**

Any of these bullets can appear at any level:
- ● (filled circle)
- ○ (open circle)  
- ■ (filled square)
- ▲ (triangle)
- ◆ (diamond)
- ➢ (arrow)
- ✓ (checkmark)

The **indentation (tabs/spaces)** determines whether it's:
- Level 0 → BL-FIRST/MID/LAST
- Level 1 → BL2-MID  
- Level 2 → BL3-MID

---

## STEP 1: Create Indent-Based List Detector

**Claude Code Command:**
```
Create a new file backend/processor/list_hierarchy_detector.py that detects list levels based on indentation (tabs/spaces) from OOXML, not bullet symbols. The bullet symbol only confirms it's a list item.
```

**Implementation:**

```python
"""
List Hierarchy Detector - Indent-Based Level Detection

Key principle: INDENTATION determines level, not bullet symbol.

The system extracts indentation from:
1. OOXML w:ind (left indent in twips)
2. OOXML w:ilvl (indentation level from numbering)
3. Text leading whitespace (tabs/spaces) as fallback

Bullet symbols (●, ○, ■, ▲, etc.) only CONFIRM it's a list item.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

logger = logging.getLogger(__name__)

# OOXML namespace
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
OOXML_NS = {'w': W_NS}


# =============================================================================
# BULLET CHARACTERS (for detection only - NOT for level assignment)
# =============================================================================

# All recognized bullet characters - ANY of these can be at ANY level
BULLET_CHARACTERS: set[str] = {
    # Standard bullets
    '●', '•', '·',           # Filled circles
    '○', '◦', '◯',           # Open circles
    '■', '▪', '□',           # Squares
    '▲', '△', '►', '▸',      # Triangles/arrows
    '◆', '◇', '❖',           # Diamonds
    '✓', '✔', '☑',           # Checkmarks
    '➢', '➤', '→', '▶',      # Arrows
    '★', '☆',                # Stars
    '─', '–', '—', '-',      # Dashes
    
    # Wingdings (private use area)
    '\uf0b7',  # Wingdings bullet
    '\uf0a7',  # Wingdings square
    '\uf0d8',  # Wingdings arrow
    '\uf076',  # Wingdings circle
    '\uf0fc',  # Wingdings checkmark
}


@dataclass
class ListItemInfo:
    """Information about a detected list item."""
    is_list: bool = False
    bullet_char: Optional[str] = None
    
    # Level determined by INDENTATION
    indent_level: int = 0           # 0, 1, or 2
    indent_twips: int = 0           # Raw indent in twips (1/20 pt)
    indent_source: str = ""         # 'ooxml_ind', 'ooxml_ilvl', 'text_whitespace'
    
    # Style mapping
    semantic_level: int = 0         # Same as indent_level (0, 1, 2)
    style_prefix: str = "BL-"       # BL-, BL2-, BL3-
    
    # Numbering info
    is_numbered: bool = False
    number_format: Optional[str] = None
    ooxml_ilvl: Optional[int] = None
    ooxml_numId: Optional[str] = None
    
    # Context
    is_parent_trigger: bool = False
    detection_method: str = ""


# =============================================================================
# INDENTATION THRESHOLDS
# =============================================================================

# Indentation thresholds in twips (1 inch = 1440 twips)
# Based on typical Word defaults: 0.5 inch per level = 720 twips
INDENT_THRESHOLDS = {
    'level_0_max': 360,      # 0 to 0.25 inch = Level 0
    'level_1_max': 1080,     # 0.25 to 0.75 inch = Level 1
    # > 0.75 inch = Level 2
}

# Tab-based thresholds (when measuring from text)
TAB_THRESHOLDS = {
    0: 0,      # No tabs = Level 0
    1: 1,      # 1 tab = Level 1
    2: 2,      # 2+ tabs = Level 2
}


class ListHierarchyDetector:
    """
    Detect list hierarchy based on INDENTATION.
    
    Priority for indent detection:
    1. OOXML w:ind/@w:left (most accurate)
    2. OOXML w:ilvl from numPr (Word's numbering level)
    3. Text leading whitespace (fallback)
    """
    
    def __init__(self, docx_path: Optional[str | Path] = None):
        """Initialize detector with optional DOCX for OOXML parsing."""
        self.docx_path = Path(docx_path) if docx_path else None
        self._numbering_defs: Dict[str, Dict] = {}
        self._paragraph_indents: Dict[int, int] = {}  # para_index -> indent_twips
        
        if self.docx_path and self.docx_path.exists():
            self._load_ooxml_data()
    
    def _load_ooxml_data(self):
        """Load indentation and numbering data from OOXML."""
        try:
            with ZipFile(self.docx_path, 'r') as zf:
                # Load document.xml for paragraph indents
                if 'word/document.xml' in zf.namelist():
                    with zf.open('word/document.xml') as f:
                        doc_xml = etree.parse(f).getroot()
                        self._extract_paragraph_indents(doc_xml)
                
                # Load numbering.xml for numbering definitions
                if 'word/numbering.xml' in zf.namelist():
                    with zf.open('word/numbering.xml') as f:
                        num_xml = etree.parse(f).getroot()
                        self._parse_numbering_defs(num_xml)
                        
        except Exception as e:
            logger.warning(f"Failed to load OOXML data: {e}")
    
    def _extract_paragraph_indents(self, doc_xml: etree._Element):
        """Extract left indent for each paragraph from document.xml."""
        para_index = 0
        for para in doc_xml.findall('.//w:p', OOXML_NS):
            # Get w:pPr/w:ind/@w:left
            ind = para.find('.//w:pPr/w:ind', OOXML_NS)
            if ind is not None:
                left = ind.get(f'{{{W_NS}}}left')
                if left:
                    try:
                        self._paragraph_indents[para_index] = int(left)
                    except ValueError:
                        pass
            para_index += 1
    
    def _parse_numbering_defs(self, num_xml: etree._Element):
        """Parse numbering definitions to get indent per level."""
        # Parse abstract numbering
        abstract_nums = {}
        for abstract in num_xml.findall('.//w:abstractNum', OOXML_NS):
            abs_id = abstract.get(f'{{{W_NS}}}abstractNumId')
            if abs_id:
                levels = {}
                for lvl in abstract.findall('w:lvl', OOXML_NS):
                    ilvl = lvl.get(f'{{{W_NS}}}ilvl')
                    if ilvl:
                        # Get indent for this level
                        ind = lvl.find('.//w:pPr/w:ind', OOXML_NS)
                        left_indent = 0
                        if ind is not None:
                            left = ind.get(f'{{{W_NS}}}left')
                            if left:
                                try:
                                    left_indent = int(left)
                                except ValueError:
                                    pass
                        
                        # Get numFmt
                        num_fmt_elem = lvl.find('w:numFmt', OOXML_NS)
                        num_fmt = num_fmt_elem.get(f'{{{W_NS}}}val') if num_fmt_elem is not None else 'bullet'
                        
                        levels[int(ilvl)] = {
                            'indent_twips': left_indent,
                            'numFmt': num_fmt,
                        }
                abstract_nums[abs_id] = levels
        
        # Map numId -> abstractNumId -> levels
        for num in num_xml.findall('.//w:num', OOXML_NS):
            num_id = num.get(f'{{{W_NS}}}numId')
            abs_ref = num.find('w:abstractNumId', OOXML_NS)
            if num_id and abs_ref is not None:
                abs_id = abs_ref.get(f'{{{W_NS}}}val')
                if abs_id and abs_id in abstract_nums:
                    self._numbering_defs[num_id] = abstract_nums[abs_id]
    
    def detect(
        self, 
        text: str, 
        para_index: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> ListItemInfo:
        """
        Detect if paragraph is a list item and determine its level.
        
        Args:
            text: Paragraph text
            para_index: Index of paragraph (for OOXML lookup)
            metadata: Optional metadata dict with additional info
            
        Returns:
            ListItemInfo with detection results
        """
        info = ListItemInfo()
        metadata = metadata or {}
        
        if not text or not text.strip():
            return info
        
        # Step 1: Check if it's a list item (has bullet or numbering)
        bullet_char = self._detect_bullet_char(text)
        number_match = self._detect_number_prefix(text)
        has_xml_list = metadata.get('has_xml_list') or metadata.get('has_bullet') or metadata.get('has_numbering')
        
        if not bullet_char and not number_match and not has_xml_list:
            return info  # Not a list item
        
        info.is_list = True
        info.bullet_char = bullet_char
        info.is_numbered = bool(number_match) or metadata.get('has_numbering', False)
        if number_match:
            info.number_format = number_match
        
        # Step 2: Determine level from INDENTATION (priority order)
        
        # 2a: Try OOXML paragraph indent
        if para_index is not None and para_index in self._paragraph_indents:
            indent_twips = self._paragraph_indents[para_index]
            info.indent_twips = indent_twips
            info.indent_level = self._twips_to_level(indent_twips)
            info.indent_source = 'ooxml_ind'
        
        # 2b: Try OOXML ilvl from metadata
        elif metadata.get('ooxml_ilvl') is not None or metadata.get('ilvl') is not None:
            ilvl = metadata.get('ooxml_ilvl') or metadata.get('ilvl', 0)
            info.ooxml_ilvl = int(ilvl)
            info.indent_level = min(int(ilvl), 2)  # Cap at level 2
            info.indent_source = 'ooxml_ilvl'
            
            # Try to get indent from numbering definition
            num_id = metadata.get('ooxml_numId') or metadata.get('numId')
            if num_id and num_id in self._numbering_defs:
                level_def = self._numbering_defs[num_id].get(int(ilvl), {})
                info.indent_twips = level_def.get('indent_twips', 0)
        
        # 2c: Try text leading whitespace
        else:
            tabs, spaces = self._count_leading_whitespace(text)
            info.indent_level = self._whitespace_to_level(tabs, spaces)
            info.indent_source = 'text_whitespace'
        
        # Step 3: Set semantic level and style prefix
        info.semantic_level = info.indent_level
        
        if info.is_numbered:
            info.style_prefix = {0: 'NL-', 1: 'NL2-', 2: 'NL3-'}.get(info.indent_level, 'NL-')
        else:
            info.style_prefix = {0: 'BL-', 1: 'BL2-', 2: 'BL3-'}.get(info.indent_level, 'BL-')
        
        # Step 4: Check for parent trigger
        info.is_parent_trigger = self._is_parent_trigger(text)
        
        info.detection_method = f"bullet:{bullet_char or 'xml'}, indent:{info.indent_source}"
        
        return info
    
    def _detect_bullet_char(self, text: str) -> Optional[str]:
        """Detect bullet character at start of text."""
        stripped = text.lstrip()
        if not stripped:
            return None
        
        first_char = stripped[0]
        if first_char in BULLET_CHARACTERS:
            return first_char
        
        # Check for "o" + whitespace pattern (Word's circle bullet)
        if len(stripped) > 1 and stripped[0] == 'o' and stripped[1] in ' \t':
            return '○'
        
        return None
    
    def _detect_number_prefix(self, text: str) -> Optional[str]:
        """Detect numbered list prefix."""
        stripped = text.lstrip()
        
        patterns = [
            (r'^(\d+)\.\s', 'decimal'),
            (r'^(\d+)\)\s', 'decimal_paren'),
            (r'^\((\d+)\)\s', 'decimal_both'),
            (r'^([a-z])\.\s', 'lower_alpha'),
            (r'^([a-z])\)\s', 'lower_alpha_paren'),
            (r'^([A-Z])\.\s', 'upper_alpha'),
            (r'^([ivxlcdm]+)\.\s', 'lower_roman'),
            (r'^([IVXLCDM]+)\.\s', 'upper_roman'),
        ]
        
        for pattern, fmt in patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                return fmt
        
        return None
    
    def _twips_to_level(self, twips: int) -> int:
        """Convert twips indent to semantic level."""
        if twips <= INDENT_THRESHOLDS['level_0_max']:
            return 0
        elif twips <= INDENT_THRESHOLDS['level_1_max']:
            return 1
        else:
            return 2
    
    def _whitespace_to_level(self, tabs: int, spaces: int) -> int:
        """Convert whitespace count to level."""
        # 1 tab or 4 spaces = 1 level
        estimated_level = tabs + (spaces // 4)
        return min(estimated_level, 2)
    
    def _count_leading_whitespace(self, text: str) -> Tuple[int, int]:
        """Count leading tabs and spaces."""
        tabs = 0
        spaces = 0
        for char in text:
            if char == '\t':
                tabs += 1
            elif char == ' ':
                spaces += 1
            else:
                break
        return tabs, spaces
    
    def _is_parent_trigger(self, text: str) -> bool:
        """Check if this is a parent trigger item."""
        # Remove bullet/number prefix
        clean = text.lstrip()
        for char in BULLET_CHARACTERS:
            if clean.startswith(char):
                clean = clean[1:].lstrip()
                break
        
        # Remove number prefix
        clean = re.sub(r'^[\d\w]+[.)]\s*', '', clean)
        clean_lower = clean.lower().strip()
        
        PARENT_PATTERNS = [
            r'^grading\b',
            r'^work-?up\b',
            r'^diagnosis\s*:',
            r'^symptoms\s*:',
            r'^classification\s*:',
            r'^characteristics\s*:',
            r'^second-?line\s+therap',
            r'^third-?line',
            r'^differential\s+diagnosis',
            r'^management\s*:',
            r'^treatment\s*:',
            r'^types\s*:',
            r'^categories\s*:',
        ]
        
        for pattern in PARENT_PATTERNS:
            if re.match(pattern, clean_lower):
                return True
        
        # Short items ending with colon
        if len(clean) < 60 and clean.rstrip().endswith(':'):
            return True
        
        # Classification pattern: "Something (SYSTEM X.X)"
        if re.search(r'\([A-Z]+\s*[\d.]+\)\s*$', clean):
            return True
        
        return False


# =============================================================================
# PARENT CONTEXT TRACKER
# =============================================================================

class ParentContextTracker:
    """
    Track parent context for BL2 → BL3 promotion.
    
    When a Level 1 item is a "parent trigger", following Level 1 items
    may be promoted to Level 2 (BL3-*) until a Level 0 item or heading.
    """
    
    def __init__(self):
        self.parent_active = False
        self.parent_level: Optional[int] = None
    
    def update(self, item_info: ListItemInfo, is_heading: bool = False) -> int:
        """
        Update context and return adjusted semantic level.
        
        Returns:
            Adjusted level (possibly promoted)
        """
        if is_heading:
            self.reset()
            return item_info.semantic_level
        
        level = item_info.semantic_level
        
        # Level 0 resets context
        if level == 0:
            self.reset()
            if item_info.is_parent_trigger:
                self.parent_active = True
                self.parent_level = 0
            return 0
        
        # Level 1: check for promotion
        if level == 1:
            if item_info.is_parent_trigger:
                self.parent_active = True
                self.parent_level = 1
                return 1  # Parent stays at level 1
            elif self.parent_active and self.parent_level == 1:
                # Promote to level 2
                return 2
            return 1
        
        # Level 2 stays at 2
        return level
    
    def reset(self):
        """Reset parent context."""
        self.parent_active = False
        self.parent_level = None


# =============================================================================
# POSITION ASSIGNMENT (FIRST/MID/LAST)
# =============================================================================

def assign_list_positions(
    paragraphs: List[Dict],
    classifications: List[Dict]
) -> List[Dict]:
    """
    Assign FIRST/MID/LAST positions to Level 0 list items.
    
    Rules:
    - Only Level 0 items (BL-*, NL-*) get FIRST/MID/LAST
    - Level 1 and 2 are always MID
    - Group by H1 sections
    - First Level 0 in section → FIRST
    - Last Level 0 in section → LAST
    - Others → MID
    """
    para_lookup = {p['id']: p for p in paragraphs}
    clf_lookup = {c['id']: c for c in classifications}
    
    # Collect Level 0 items per H1 section
    sections: List[List[int]] = []  # List of [para_id, ...]
    current_section: List[int] = []
    
    for clf in classifications:
        tag = clf.get('tag', '')
        para_id = clf['id']
        
        # H1 starts new section
        if tag.startswith('H1'):
            if current_section:
                sections.append(current_section)
            current_section = []
            continue
        
        # Check for Level 0 list (BL- or NL- but NOT BL2/BL3/NL2/NL3)
        if (tag.startswith('BL-') or tag.startswith('NL-')) and \
           not any(tag.startswith(p) for p in ['BL2', 'BL3', 'NL2', 'NL3']):
            
            # Exclude run-in headings
            para = para_lookup.get(para_id, {})
            text = para.get('text', '').strip().lower()
            
            RUN_IN_HEADINGS = [
                'definitions', 'epidemiology', 'etiology', 'pathophysiology',
                'differential diagnosis', 'management', 'treatment', 
                'outcomes', 'prognosis', 'prevention', 'clinical significance'
            ]
            
            is_run_in = any(text.startswith(h) for h in RUN_IN_HEADINGS)
            if not is_run_in:
                current_section.append(para_id)
    
    # Don't forget last section
    if current_section:
        sections.append(current_section)
    
    # Apply positions
    for section in sections:
        if not section:
            continue
        
        n = len(section)
        for i, para_id in enumerate(section):
            clf = clf_lookup.get(para_id)
            if not clf:
                continue
            
            old_tag = clf['tag']
            
            if i == 0:
                new_tag = re.sub(r'-(FIRST|MID|LAST)$', '-FIRST', old_tag)
            elif i == n - 1:
                new_tag = re.sub(r'-(FIRST|MID|LAST)$', '-LAST', old_tag)
            else:
                new_tag = re.sub(r'-(FIRST|MID|LAST)$', '-MID', old_tag)
            
            if new_tag != old_tag:
                clf['tag'] = new_tag
                clf['position_corrected'] = True
    
    return classifications


# =============================================================================
# MAIN INTEGRATION FUNCTION
# =============================================================================

def process_list_hierarchy(
    paragraphs: List[Dict],
    docx_path: Optional[str | Path] = None
) -> List[Dict]:
    """
    Process all paragraphs to detect list hierarchy.
    
    Args:
        paragraphs: List of {'id', 'text', 'metadata'} dicts
        docx_path: Optional path to DOCX for OOXML parsing
        
    Returns:
        Paragraphs with updated metadata including list info
    """
    detector = ListHierarchyDetector(docx_path)
    context_tracker = ParentContextTracker()
    
    results = []
    
    for i, para in enumerate(paragraphs):
        text = para.get('text', '')
        metadata = para.get('metadata', {}).copy()
        
        # Detect if heading
        is_heading = metadata.get('style_name', '').lower().startswith('heading') or \
                     text.strip().lower().startswith('<h')
        
        # Detect list info
        list_info = detector.detect(text, para_index=i, metadata=metadata)
        
        if list_info.is_list:
            # Apply parent context
            adjusted_level = context_tracker.update(list_info, is_heading)
            
            # Update metadata
            metadata['is_list'] = True
            metadata['bullet_char'] = list_info.bullet_char
            metadata['semantic_level'] = adjusted_level
            metadata['indent_level'] = list_info.indent_level
            metadata['indent_twips'] = list_info.indent_twips
            metadata['indent_source'] = list_info.indent_source
            metadata['is_numbered'] = list_info.is_numbered
            metadata['is_parent_trigger'] = list_info.is_parent_trigger
            
            # Set style prefix based on adjusted level
            if list_info.is_numbered:
                metadata['list_style_prefix'] = {0: 'NL-', 1: 'NL2-', 2: 'NL3-'}.get(adjusted_level, 'NL-')
            else:
                metadata['list_style_prefix'] = {0: 'BL-', 1: 'BL2-', 2: 'BL3-'}.get(adjusted_level, 'BL-')
            
            metadata['list_kind'] = 'numbered' if list_info.is_numbered else 'bullet'
            metadata['list_position'] = 'MID'  # Will be corrected by assign_list_positions
            
            # Update has_bullet/has_numbering
            metadata['has_bullet'] = not list_info.is_numbered
            metadata['has_numbering'] = list_info.is_numbered
        
        else:
            metadata['is_list'] = False
            if is_heading:
                context_tracker.reset()
        
        results.append({
            **para,
            'metadata': metadata
        })
    
    return results


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == '__main__':
    import sys
    
    print("=" * 70)
    print("LIST HIERARCHY DETECTOR - INDENT-BASED")
    print("=" * 70)
    print("\nKey principle: INDENTATION determines level, not bullet symbol.")
    print("\nRecognized bullet characters:")
    for char in sorted(BULLET_CHARACTERS, key=lambda x: ord(x)):
        if ord(char) < 0xF000:  # Skip private use area
            print(f"  {char} (U+{ord(char):04X})")
    
    print("\nIndentation thresholds (in twips, 1440 twips = 1 inch):")
    print(f"  Level 0: 0 - {INDENT_THRESHOLDS['level_0_max']} twips")
    print(f"  Level 1: {INDENT_THRESHOLDS['level_0_max']+1} - {INDENT_THRESHOLDS['level_1_max']} twips")
    print(f"  Level 2: > {INDENT_THRESHOLDS['level_1_max']} twips")
    
    if len(sys.argv) > 1:
        from docx import Document
        
        docx_path = sys.argv[1]
        doc = Document(docx_path)
        
        paragraphs = []
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                paragraphs.append({
                    'id': i + 1,
                    'text': text,
                    'metadata': {'style_name': para.style.name if para.style else 'Normal'}
                })
        
        results = process_list_hierarchy(paragraphs, docx_path)
        
        print(f"\n{'=' * 70}")
        print(f"RESULTS FOR: {docx_path}")
        print(f"{'=' * 70}")
        
        for para in results[:40]:
            meta = para['metadata']
            if meta.get('is_list'):
                level = meta.get('semantic_level', '?')
                prefix = meta.get('list_style_prefix', '??')
                bullet = meta.get('bullet_char') or '(xml)'
                source = meta.get('indent_source', '?')
                twips = meta.get('indent_twips', 0)
                
                print(f"\n[{para['id']}] Level {level} → {prefix}*")
                print(f"    Bullet: {bullet}, Indent: {twips} twips ({source})")
                print(f"    Text: {para['text'][:60]}...")
```

---

## STEP 2: Update Ingestion to Use Indent-Based Detection

**Claude Code Command:**
```
Modify backend/processor/ingestion.py to use the indent-based ListHierarchyDetector. Import and call process_list_hierarchy after extracting paragraphs.
```

**Add to ingestion.py:**

```python
# Add import at top
from .list_hierarchy_detector import (
    ListHierarchyDetector,
    ParentContextTracker, 
    process_list_hierarchy,
    BULLET_CHARACTERS
)

# Modify extract_paragraphs method:

def extract_paragraphs(self, docx_path: str | Path) -> list[dict]:
    """Extract paragraphs with indent-based list hierarchy detection."""
    docx_path = Path(docx_path)
    doc = Document(docx_path)
    
    # First pass: extract raw paragraphs
    raw_paragraphs = []
    para_id = 1
    current_zone = 'BODY'
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        # Detect zone
        current_zone, box_type = self._detect_zone(text, current_zone, is_table=False)
        
        # Get basic metadata
        metadata = self._extract_metadata(para)
        metadata['context_zone'] = current_zone
        if box_type:
            metadata['box_type'] = box_type
        
        raw_paragraphs.append({
            'id': para_id,
            'text': text,
            'text_truncated': self._truncate(text),
            'metadata': metadata,
        })
        para_id += 1
    
    # Second pass: apply indent-based list hierarchy detection
    paragraphs = process_list_hierarchy(raw_paragraphs, docx_path)
    
    logger.info(f"Extracted {len(paragraphs)} paragraphs with list hierarchy detection")
    
    return paragraphs
```

---

## STEP 3: Update Classifier for Semantic Level

**Claude Code Command:**
```
Modify backend/processor/classifier.py to add a _classify_from_indent_level method that uses the detected semantic_level and list_style_prefix for high-confidence rule-based classification
```

**Add to GeminiClassifier class:**

```python
def _classify_from_indent_level(self, para: Dict) -> Optional[Dict]:
    """
    Classify list items using indent-based semantic level.
    Called BEFORE LLM for high-confidence predictions.
    """
    metadata = para.get('metadata', {})
    
    if not metadata.get('is_list'):
        return None
    
    semantic_level = metadata.get('semantic_level')
    list_prefix = metadata.get('list_style_prefix')
    zone = metadata.get('context_zone', 'BODY')
    is_numbered = metadata.get('is_numbered', False)
    
    if semantic_level is None or list_prefix is None:
        return None
    
    # Zone-specific conversions
    if zone == 'TABLE':
        if is_numbered:
            prefix = {0: 'TNL-', 1: 'TNL2-', 2: 'TNL3-'}.get(semantic_level, 'TNL-')
        else:
            prefix = {0: 'TBL-', 1: 'TBL2-', 2: 'TBL3-'}.get(semantic_level, 'TBL-')
        list_prefix = prefix
        
    elif zone == 'BACK_MATTER':
        if is_numbered:
            return {
                'id': para['id'],
                'tag': 'REF-N',
                'confidence': 95,
                'source': 'indent_rule',
            }
        else:
            return {
                'id': para['id'],
                'tag': 'SR',
                'confidence': 95,
                'source': 'indent_rule',
            }
    
    elif zone.startswith('BOX_'):
        box_prefix = zone.replace('BOX_', '')
        if is_numbered:
            prefix = {0: f'{box_prefix}-NL-', 1: f'{box_prefix}-NL2-', 2: f'{box_prefix}-NL3-'}.get(semantic_level, f'{box_prefix}-NL-')
        else:
            prefix = {0: f'{box_prefix}-BL-', 1: f'{box_prefix}-BL2-', 2: f'{box_prefix}-BL3-'}.get(semantic_level, f'{box_prefix}-BL-')
        list_prefix = prefix
    
    # Position (MID default, corrected later for Level 0)
    position = 'MID'
    
    tag = f"{list_prefix}{position}"
    
    # Build confidence based on detection source
    indent_source = metadata.get('indent_source', 'unknown')
    if indent_source == 'ooxml_ind':
        confidence = 94  # High - direct OOXML indent
    elif indent_source == 'ooxml_ilvl':
        confidence = 92  # Good - OOXML numbering level
    else:
        confidence = 88  # Lower - text whitespace fallback
    
    return {
        'id': para['id'],
        'tag': tag,
        'confidence': confidence,
        'source': 'indent_rule',
        'semantic_level': semantic_level,
        'indent_source': indent_source,
    }
```

**Modify classify() to call it first:**

```python
def classify(self, paragraphs, document_name, document_type="Academic Document"):
    results = []
    llm_queue = []
    
    for para in paragraphs:
        # Priority 1: Indent-based list classification
        indent_result = self._classify_from_indent_level(para)
        if indent_result and indent_result.get('confidence', 0) >= 88:
            results.append(indent_result)
            self.rule_predictions += 1
            continue
        
        # Priority 2: Pattern rules (markers, zones)
        pattern_result = self._apply_pattern_rules(para)
        if pattern_result and pattern_result.get('confidence', 0) >= 85:
            results.append(pattern_result)
            self.rule_predictions += 1
            continue
        
        # Queue for LLM
        llm_queue.append(para)
    
    # Batch LLM classification
    if llm_queue:
        llm_results = self._classify_with_llm(llm_queue, document_name, document_type)
        results.extend(llm_results)
    
    results.sort(key=lambda x: x['id'])
    return results
```

---

## STEP 4: Add Position Correction to Validator

**Claude Code Command:**
```
Import assign_list_positions in backend/processor/validator.py and call it at the end of validate_and_repair
```

```python
# Add import
from .list_hierarchy_detector import assign_list_positions

# In validate_and_repair, add before return:
def validate_and_repair(...):
    # ... existing repair logic ...
    
    # Correct FIRST/MID/LAST positions for Level 0 lists
    repaired = assign_list_positions(blocks, repaired)
    
    return repaired
```

---

## SUMMARY

### Key Principle
**INDENTATION determines list level, NOT bullet symbol.**

Any bullet (●, ○, ■, ▲, etc.) can be at any level.

### Indentation → Level Mapping
| Indent (twips) | Indent (inches) | Level | Style |
|----------------|-----------------|-------|-------|
| 0 - 360 | 0 - 0.25" | 0 | BL-FIRST/MID/LAST |
| 361 - 1080 | 0.25" - 0.75" | 1 | BL2-MID |
| > 1080 | > 0.75" | 2 | BL3-MID |

### Detection Priority
1. **OOXML w:ind/@w:left** (most accurate)
2. **OOXML w:ilvl** from numPr
3. **Text whitespace** (tabs/spaces) fallback

### Files to Create/Modify
| File | Action |
|------|--------|
| `backend/processor/list_hierarchy_detector.py` | **CREATE** |
| `backend/processor/ingestion.py` | **MODIFY** |
| `backend/processor/classifier.py` | **MODIFY** |
| `backend/processor/validator.py` | **MODIFY** |
