"""
Universal Style Handler
=======================
Works with ANY Edwards textbook format by:
1. Loading official 400 tags dynamically
2. Extracting tags from document text when present
3. Minimal normalization (preserves AI classifications)
4. Zero data loss guarantee
5. Client-agnostic processing

This module can be integrated into any existing system.
"""

import re
import logging
from pathlib import Path
from typing import Set, Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TagValidationResult:
    """Result of tag validation."""
    is_valid: bool
    normalized_tag: str
    confidence: float
    reason: str


class UniversalStyleHandler:
    """
    Universal handler for document styles across all formats.
    
    Key principles:
    1. Load official tags from file (not hardcoded)
    2. Extract tags from document text when present
    3. Validate AI classifications against official list
    4. Minimal normalization (case, zone markers only)
    5. Never modify content - only apply styles
    """
    
    def __init__(self, tags_file: Optional[Path] = None):
        """
        Initialize universal style handler.
        
        Args:
            tags_file: Path to official Tags.txt file
        """
        self.official_tags = self._load_official_tags(tags_file)
        self.zone_markers = self._get_zone_markers()
        self.normalization_cache: Dict[str, str] = {}
        self.tag_extraction_stats = {
            'extracted_from_text': 0,
            'ai_classified': 0,
            'normalized': 0,
            'fallback_used': 0
        }
        
        logger.info(f"✓ Universal Style Handler initialized with {len(self.official_tags)} official tags")
    
    def _load_official_tags(self, tags_file: Optional[Path]) -> Set[str]:
        """
        Load official tags from file with robust fallback.
        
        Tries multiple locations and provides comprehensive fallback.
        """
        # Try multiple possible locations
        possible_paths = []
        
        if tags_file:
            possible_paths.append(tags_file)
        
        # Common locations relative to this file
        base_dir = Path(__file__).parent
        possible_paths.extend([
            base_dir.parent / 'Tags.txt',
            base_dir / 'Tags.txt',
            base_dir.parent.parent / 'Tags.txt',
            Path('Tags.txt'),
            Path('backend/Tags.txt'),
        ])
        
        # Try each path
        for path in possible_paths:
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        tags = set()
                        for line in f:
                            tag = line.strip()
                            if tag and not tag.startswith('#'):
                                tags.add(tag)
                    
                    logger.info(f"✓ Loaded {len(tags)} official tags from: {path}")
                    return tags
                    
                except Exception as e:
                    logger.warning(f"Could not load {path}: {e}")
                    continue
        
        # Fallback: Comprehensive core tag set
        logger.warning("Tags.txt not found, using comprehensive fallback set")
        return self._get_fallback_tags()
    
    def _get_fallback_tags(self) -> Set[str]:
        """Comprehensive fallback tag set covering all major patterns."""
        return {
            # Structure
            'CN', 'CT', 'CAU', 'CHAP', 'PN', 'PT', 'PART',
            'SN', 'ST', 'SAU', 'SECTION', 'UN', 'UT', 'UAU', 'UNIT',
            'CST', 'PST', 'SST', 'UST',  # Subtitles
            
            # Headings
            'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
            'H1-BL', 'H2 after H1', 'H3 after H2',  # Special heading variants
            'SP1', 'SP2',  # Special headings
            
            # Reference/Bibliography Headings
            'REFH1', 'REFH2', 'REFH2a', 'REF-H1', 'REF-H2',
            'SRH1', 'SRH2', 'BIBH1', 'BIBH2',
            'RQ-H1', 'RQ-H2',  # Review Questions
            
            # Body Text
            'TXT', 'TXT-FLUSH', 'TXT-DC', 'TXT-SPACE ABOVE',
            'INTRO', 'PTXT', 'PTXT-DC', 'STXT', 'STXT-DC', 'UTXT',
            
            # Lists - Bulleted
            'BL-FIRST', 'BL-MID', 'BL-LAST',
            'BL2-MID', 'BL3-MID', 'BL4-MID', 'BL5-MID', 'BL6-MID',
            
            # Lists - Numbered
            'NL-FIRST', 'NL-MID', 'NL-LAST',
            'NL-MID following L1',
            
            # Lists - Unnumbered
            'UL-FIRST', 'UL-MID', 'UL-LAST',
            
            # Multi-column lists
            'MCUL-FIRST', 'MCUL-MID', 'MCUL-LAST',
            
            # Tables
            'T', 'T1', 'T2', 'T2-C', 'T3', 'T4', 'T5',
            'T-DIR', 'TBL', 'TFN', 'TN', 'TMATH',
            'TNL-FIRST', 'TNL-MID', 'TUL-FIRST', 'TUL-MID',
            'TFN-FIRST', 'TFN-MID', 'TFN-LAST',
            'TFN-BL-FIRST', 'TFN-BL-MID', 'TFN-BL-LAST',
            
            # Unnumbered Tables
            'UNT', 'UNT-BL', 'UNT-FN', 'UNT-TTL', 'UNT-UL',
            'UNT-NL-FIRST', 'UNT-NL-MID', 'UNT-T2', 'UNT-T3',
            
            # Figures
            'FIG-LEG', 'FIG-CRED', 'UNFIG',
            
            # References
            'REF-N', 'REF-N-FIRST', 'REF-U', 'SR', 'BIB',
            
            # Boxes (BX1 prefix) - Most common box styles
            'BX1-TTL', 'BX1-TXT', 'BX1-TXT-FIRST', 'BX1-TXT-DC', 'BX1-TYPE',
            'BX1-H1', 'BX1-H2', 'BX1-H3', 'BX1-L1',
            'BX1-BL-FIRST', 'BX1-BL-MID', 'BX1-BL-LAST', 'BX1-BL2-MID',
            'BX1-NL-FIRST', 'BX1-NL-MID', 'BX1-NL-LAST',
            'BX1-UL-FIRST', 'BX1-UL-MID', 'BX1-UL-LAST',
            'BX1-EQ-FIRST', 'BX1-EQ-MID', 'BX1-EQ-LAST', 'BX1-EQ-ONLY',
            'BX1-EXT-ONLY', 'BX1-FN', 'BX1-QUO', 'BX1-QUO-AU',
            'BX1-MCUL-FIRST', 'BX1-MCUL-MID', 'BX1-MCUL-LAST',
            'BX1-OUT1-FIRST', 'BX1-OUT1-MID', 'BX1-OUT2', 'BX1-OUT2-LAST', 'BX1-OUT3',
            
            # Numbered Boxes (NBX prefix)
            'NBX-TTL', 'NBX-TXT', 'NBX-TXT-FIRST', 'NBX-TXT-DC', 'NBX-TYPE',
            'NBX-H1', 'NBX-H2', 'NBX-H3', 'NBX-L1',
            'NBX-BL-FIRST', 'NBX-BL-MID', 'NBX-BL-LAST', 'NBX-BL2-MID',
            'NBX-NL-FIRST', 'NBX-NL-MID', 'NBX-NL-LAST',
            'NBX-UL-FIRST', 'NBX-UL-MID', 'NBX-UL-LAST',
            'NBX-EQ-FIRST', 'NBX-EQ-MID', 'NBX-EQ-LAST', 'NBX-EQ-ONLY',
            'NBX-EXT-ONLY', 'NBX-FN', 'NBX-QUO', 'NBX-QUO-AU',
            'NBX-MCUL-FIRST', 'NBX-MCUL-MID', 'NBX-MCUL-LAST',
            'NBX-OUT1-FIRST', 'NBX-OUT1-MID', 'NBX-OUT2', 'NBX-OUT2-LAST', 'NBX-OUT3',
            
            # Chapter Outline
            'COUT-1', 'COUT-2', 'COUTH1',
            'COUT-BL', 'COUT-NL-FIRST', 'COUT-NL-MID',
            
            # Part/Section/Unit Outlines
            'POUT-1', 'POUT-2', 'POUTH1',
            'SOUT-1', 'SOUT-2', 'SOUTH1', 'SOUT-NL-FIRST', 'SOUT-NL-MID',
            'UOUT-1', 'UOUT-2', 'UOUTH1',
            
            # Objectives
            'OBJ1', 'OBJ-TXT',
            'OBJ-BL-FIRST', 'OBJ-BL-MID', 'OBJ-BL-LAST',
            'OBJ-NL-FIRST', 'OBJ-NL-MID', 'OBJ-NL-LAST',
            'OBJ-UL-FIRST', 'OBJ-UL-MID', 'OBJ-UL-LAST',
            
            # Key Terms/Points
            'KT1', 'KT-TXT',
            'KT-BL-FIRST', 'KT-BL-MID', 'KT-BL-LAST',
            'KT-NL-FIRST', 'KT-NL-MID', 'KT-NL-LAST',
            'KT-UL-FIRST', 'KT-UL-MID', 'KT-UL-LAST',
            'KP1',
            'KP-BL-FIRST', 'KP-BL-MID', 'KP-BL-LAST',
            'KP-NL-FIRST', 'KP-NL-MID', 'KP-NL-LAST',
            
            # Exercises
            'EXER-H1', 'EXER-TTL', 'EXER-DIR',
            'EXER-AB-NL-FIRST', 'EXER-AB-NL-MID',
            'EXER-MC-NL-FIRST', 'EXER-MC-NL-MID',
            'EXER-MC-NL2-FIRST', 'EXER-MC-NL2-MID',
            'EXER-TF-NL-FIRST', 'EXER-TF-NL-MID',
            'EXER-SA-NL-FIRST', 'EXER-SA-NL-MID',
            
            # Review Questions
            'RQ-NL-FIRST', 'RQ-NL-MID', 'RQ-NL-LAST',
            
            # Questions/Answers
            'QUES-NL-FIRST', 'QUES-NL-MID',
            'QUES-SUB-FIRST', 'QUES-SUB-MID', 'QUES-SUB-LAST',
            'ANS-NL-FIRST', 'ANS-NL-MID',
            
            # Special Elements
            'FN', 'FN-LAST', 'FN-BL-FIRST', 'FN-BL-MID', 'FN-BL-LAST',
            'EXT-FIRST', 'EXT-MID', 'EXT-LAST', 'EXT-ONLY',
            'QUO', 'QUOA', 'COQ', 'COQA', 'PQUOTE', 'SQUOTE', 'UQUOTE',
            'PMI', 'CAU', 'CPAU', 'PAU', 'DED', 'DED-AU',
            
            # Equations
            'EQ-FIRST', 'EQ-MID', 'EQ-LAST', 'EQ-ONLY',
            'EQN-FIRST', 'EQN-MID', 'EQN-LAST', 'EQN-ONLY',
            
            # Outlines
            'OUT1-FIRST', 'OUT1-MID', 'OUT1-LAST',
            'OUT2-FIRST', 'OUT2-MID', 'OUT2-LAST',
            'OUT3-FIRST', 'OUT3-MID',
            
            # Examples
            'EX-H1', 'EX-NL-FIRST', 'EX-NL-MID', 'EX-NL-LAST',
            
            # Dialogue
            'DIA-FIRST', 'DIA-MID', 'DIA-LAST',
            
            # Sidebar
            'SBT', 'SBTXT',
            'SBBL-FIRST', 'SBBL-MID', 'SBBL-LAST',
            'SBNL-FIRST', 'SBNL-MID',
            'SBUL', 'SBUL-FIRST',
            
            # List Headers
            'L1', 'L2',
            
            # Frontmatter/Backmatter
            'HTTLPG-TTL', 'HTTLPG-SUBTTL', 'HTTLPG-ED',
            'TTLPG-TTL', 'TTLPG-SUBTTL', 'TTLPG-ED', 'TTLPG-VOL',
            'TTLPG-AU', 'TTLPG-AU-AFFIL',
            'CPY', 'FM-TTL', 'FM-AU', 'FM-AU-AFFIL',
            'CONTRIB-AU', 'CONTRIB-AU-AFFIL',
            'REV-AU', 'REV-AU-AFFIL',
            'BM-TTL',
            
            # Table of Contents
            'TOC-FM', 'TOC-UN', 'TOC-UT', 'TOC-SN', 'TOC-ST',
            'TOC-CN', 'TOC-CT', 'TOC-CAU',
            'TOC-H1', 'TOC-H2',
            'TOC-BM-FIRST', 'TOC-BM',
            
            # Appendix
            'APX', 'APXN', 'APXT', 'APXST', 'APXAU',
            'APXH1', 'APXH2', 'APXH3',
            'APX-TXT', 'APX-TXT-FLUSH',
            
            # Glossary
            'GLOS-UL-FIRST', 'GLOS-UL-MID',
            'GLOS-NL-FIRST', 'GLOS-NL-MID',
            'GLOS-BL-FIRST', 'GLOS-BL-MID',
            
            # Index
            'IDX-TXT', 'IDX-ALPHA', 'IDX-1', 'IDX-2', 'IDX-3',
            
            # Acknowledgments
            'ACK1', 'ACKTXT',
            
            # Folios
            'FOLIO-RECTO', 'FOLIO-VERSO', 'DF',
            
            # Running Heads
            'RHR', 'RHV',
            
            # Web/Point
            'WEBTXT', 'WL1', 'POINT-BLURB',
            
            # Other
            'SUMHD', 'POC', 'POC-FIRST', 'POS', 'SOC', 'SOC-FIRST', 'SOS',
            'UOC', 'UOC-FIRST', 'UOS',
            'Normal',  # Word default
        }
    
    def _get_zone_markers(self) -> Set[str]:
        """Get all zone markers that should be filtered."""
        return {
            'front-open', 'front-close', 'FRONT-OPEN', 'FRONT-CLOSE',
            'body-open', 'body-close', 'BODY-OPEN', 'BODY-CLOSE',
            'ref-open', 'ref-close', 'REF-OPEN', 'REF-CLOSE',
            'float-open', 'float-close', 'FLOAT-OPEN', 'FLOAT-CLOSE',
            'COUT', '/COUT', 'FM', 'BM',  # Structure markers
        }
    
    def extract_tag_from_text(self, text: str) -> Optional[str]:
        """
        Extract tag from paragraph text if present.
        
        Looks for patterns like:
        - <H1>Title</H1>
        - <TAG>content
        - [TAG] content
        
        Args:
            text: Paragraph text
        
        Returns:
            Extracted tag or None
        """
        if not text:
            return None
        
        text = text.strip()
        
        # Pattern 1: <TAG> at start
        match = re.match(r'^<([A-Za-z0-9][A-Za-z0-9._\s-]*)>', text)
        if match:
            tag = match.group(1).strip()
            self.tag_extraction_stats['extracted_from_text'] += 1
            return tag
        
        # Pattern 2: [TAG] at start
        match = re.match(r'^\[([A-Za-z0-9][A-Za-z0-9._\s-]*)\]', text)
        if match:
            tag = match.group(1).strip()
            self.tag_extraction_stats['extracted_from_text'] += 1
            return tag
        
        return None
    
    def normalize_tag(self, tag: str, context: Optional[Dict] = None) -> str:
        """
        Normalize tag to official style name.
        
        Process:
        1. Check cache
        2. Exact match in official list
        3. Case normalization
        4. Zone marker filtering
        5. Special pattern mappings
        6. Intelligent fallback
        
        Args:
            tag: Raw tag from extraction or AI
            context: Optional context (paragraph number, etc.)
        
        Returns:
            Normalized official tag name
        """
        if not tag:
            return "TXT"
        
        # Cache check
        if tag in self.normalization_cache:
            return self.normalization_cache[tag]
        
        # Clean
        original_tag = tag
        tag = tag.strip().strip('<>[]').strip()
        
        if not tag:
            return "TXT"
        
        # 1. Exact match
        if tag in self.official_tags:
            self.normalization_cache[original_tag] = tag
            return tag
        
        # 2. Case normalization
        tag_upper = tag.upper()
        if tag_upper in self.official_tags:
            self.normalization_cache[original_tag] = tag_upper
            self.tag_extraction_stats['normalized'] += 1
            return tag_upper
        
        tag_lower = tag.lower()
        if tag_lower in self.official_tags:
            self.normalization_cache[original_tag] = tag_lower
            self.tag_extraction_stats['normalized'] += 1
            return tag_lower
        
        # Try title case
        tag_title = tag.title()
        if tag_title in self.official_tags:
            self.normalization_cache[original_tag] = tag_title
            self.tag_extraction_stats['normalized'] += 1
            return tag_title
        
        # 3. Zone markers - filter
        if tag in self.zone_markers or tag.lower() in self.zone_markers:
            logger.debug(f"Filtered zone marker: {tag}")
            return "TXT"
        
        # 4. Special mappings based on common patterns
        result = self._apply_special_mappings(tag)
        if result != tag:
            self.normalization_cache[original_tag] = result
            self.tag_extraction_stats['normalized'] += 1
            return result
        
        # 5. Pattern-based fallback
        result = self._intelligent_fallback(tag)
        self.normalization_cache[original_tag] = result
        self.tag_extraction_stats['fallback_used'] += 1
        
        if result != 'TXT':
            logger.debug(f"Unknown tag '{tag}' mapped to '{result}'")
        
        return result
    
    def _apply_special_mappings(self, tag: str) -> str:
        """Apply special known mappings."""
        
        # Direct mappings
        mappings = {
            'H2 after H1': 'H2',
            'H3 after H2': 'H3',
            'REF': 'REFH1' if 'REFH1' in self.official_tags else 'SRH1',
            'Ref-H1': 'REFH1',
            'Ref-H2': 'REFH2',
        }
        
        if tag in mappings:
            return mappings[tag]
        
        # Figure legend patterns
        if re.match(r'^fig\d+-\d+\.\d+$', tag, re.IGNORECASE):
            return 'FIG-LEG'
        
        # Figure/table references in text (not styles)
        if re.match(r'^(FIG|TAB)\d+\.\d+$', tag):
            logger.debug(f"Figure/table reference {tag} in text, not a style")
            return 'TXT'
        
        # Table title patterns
        if re.match(r'^TAB[\s\d\.]+-?\d*$', tag):
            return 'T1'
        
        # Draft figure patterns
        if re.match(r'^DFIG\d{1,2}\.\d+$', tag):
            return 'FIG-LEG'
        
        return tag
    
    def _intelligent_fallback(self, tag: str) -> str:
        """Intelligent fallback for unknown tags."""
        
        tag_upper = tag.upper()
        
        # Heading pattern
        if re.match(r'^H\d$', tag_upper):
            return 'H1'
        
        # List patterns
        if 'BL' in tag_upper:
            if 'FIRST' in tag_upper:
                return 'BL-FIRST'
            if 'LAST' in tag_upper:
                return 'BL-LAST'
            return 'BL-MID'
        
        if 'NL' in tag_upper:
            if 'FIRST' in tag_upper:
                return 'NL-FIRST'
            if 'LAST' in tag_upper:
                return 'NL-LAST'
            return 'NL-MID'
        
        if 'UL' in tag_upper:
            if 'FIRST' in tag_upper:
                return 'UL-FIRST'
            if 'LAST' in tag_upper:
                return 'UL-LAST'
            return 'UL-MID'
        
        # Table pattern
        if tag.startswith('T') and len(tag) <= 3:
            return 'T'
        
        # Text pattern
        if 'TXT' in tag_upper or 'TEXT' in tag_upper:
            return 'TXT'
        
        # Box patterns
        if 'BX' in tag_upper:
            if 'TTL' in tag_upper:
                return 'BX1-TTL'
            return 'BX1-TXT'
        
        # Ultimate fallback
        logger.debug(f"No pattern match for '{tag}', using TXT")
        return 'TXT'
    
    def validate_tag(self, tag: str) -> TagValidationResult:
        """
        Validate and provide detailed result.
        
        Args:
            tag: Tag to validate
        
        Returns:
            TagValidationResult with details
        """
        if not tag:
            return TagValidationResult(
                is_valid=False,
                normalized_tag='TXT',
                confidence=0.5,
                reason='Empty tag'
            )
        
        # Check if it's official
        if tag in self.official_tags:
            return TagValidationResult(
                is_valid=True,
                normalized_tag=tag,
                confidence=1.0,
                reason='Exact match in official list'
            )
        
        # Try normalization
        normalized = self.normalize_tag(tag)
        
        if normalized in self.official_tags:
            confidence = 0.95 if normalized != tag else 1.0
            return TagValidationResult(
                is_valid=True,
                normalized_tag=normalized,
                confidence=confidence,
                reason='Normalized to official tag'
            )
        
        # Fallback was used
        return TagValidationResult(
            is_valid=False,
            normalized_tag=normalized,
            confidence=0.7,
            reason='Used intelligent fallback'
        )
    
    def get_stats(self) -> Dict:
        """Get handler statistics."""
        return {
            'official_tags_count': len(self.official_tags),
            'cache_size': len(self.normalization_cache),
            'extraction_stats': self.tag_extraction_stats.copy(),
            'sample_official_tags': sorted(list(self.official_tags))[:20],
        }
    
    def log_summary(self):
        """Log summary of processing."""
        stats = self.get_stats()
        logger.info("="*60)
        logger.info("Universal Style Handler Summary")
        logger.info("="*60)
        logger.info(f"Official tags loaded: {stats['official_tags_count']}")
        logger.info(f"Tags extracted from text: {stats['extraction_stats']['extracted_from_text']}")
        logger.info(f"Tags normalized: {stats['extraction_stats']['normalized']}")
        logger.info(f"Fallbacks used: {stats['extraction_stats']['fallback_used']}")
        logger.info(f"Cache entries: {stats['cache_size']}")
        logger.info("="*60)


# Standalone function for backward compatibility
_global_handler: Optional[UniversalStyleHandler] = None

def normalize_style_name(tag: str) -> str:
    """
    Backward compatible normalize function.
    
    Uses global handler instance.
    """
    global _global_handler
    if _global_handler is None:
        _global_handler = UniversalStyleHandler()
    
    return _global_handler.normalize_tag(tag)


def get_global_handler() -> UniversalStyleHandler:
    """Get or create global handler instance."""
    global _global_handler
    if _global_handler is None:
        _global_handler = UniversalStyleHandler()
    return _global_handler
