"""
STAGE 2: Gemini Classification (model set via env/config)
- Prompt Builder
- Gemini API (Single Call or Chunked)
- Response Parser with robust JSON handling

Sends entire document in one API call and extracts tags + confidence scores.
"""

import json
import re
import logging
import time
from pathlib import Path
from typing import Optional

from .llm_client import GeminiClient
from .style_list import ALLOWED_STYLES
from app.services.style_normalizer import normalize_style, normalize_tag
from app.services.grounded_retriever import get_retriever
from app.services.prediction_cache import get_cache
from .rule_learner import RuleLearner

logger = logging.getLogger(__name__)

REF_NUMBER_RE = re.compile(
    r"^\s*(?:[•●\-–—]\s*)?(?:\[\s*\d+\s*\]|\(\s*\d+\s*\)|\d+\s*[.)]|\d+\s+)"
)
REF_BULLET_RE = re.compile(r"^\s*[\u2022\u25CF\-\*\u2013\u2014]\s+")


# strict parsing helpers for model tag outputs
STRICT_TAG_RE = re.compile(r"^[A-Z0-9]+(?:[_-][A-Z0-9]+)*$")
EXTRACT_TAG_RE = re.compile(r"[A-Z0-9]+(?:[_-][A-Z0-9]+)*")

# Load system prompt
PROMPT_DIR = Path(__file__).parent.parent / 'prompts'
SYSTEM_PROMPT_PATH = PROMPT_DIR / 'system_prompt.txt'

# Timeout and retry configuration
API_TIMEOUT = 120  # seconds per API call (reduced from default 600)
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries

# Valid tags for validation - extracted from tagged documents
# 
# TAG NAMING CONVENTIONS:
# 1. Base tags: CN, CT, H1, H2, TXT, etc.
# 2. Text flow variants: TAG + number suffix (e.g., TXT1, TXT2, H11, H12)
#    - Numbers indicate text flow/column position in multi-column layouts
# 3. List position: -FIRST, -MID, -LAST (e.g., BL-FIRST, BL-MID, BL-LAST)
# 4. Nesting levels: TAG + level number (e.g., TBL2-MID, TBL3-MID for level 2, 3)
# 5. Table variants: T + column type (T2, T21, T22, T5, T6 for different column types)
#
VALID_TAGS = {
    # Document Structure
    "CN",           # Chapter Number
    "CT",           # Chapter Title
    "CAU",          # Chapter Author
    "PN",           # Part Number
    "PT",           # Part Title
    
    # Headings (H1-H6 with text flow variants)
    "H1", "H2", "H3", "H4", "H5", "H6",  # Standard Headings
    "H11", "H12",   # H1 in text flow 1, 2 (multi-column layouts)
    "H21",          # H2 in text flow 1
    "SP-H1",        # Special Heading 1
    "EOC-H1",       # End of Chapter Heading 1
    
    # Reference Headings
    "REFH1",        # Reference Heading Level 1
    "REFH2",        # Reference Heading Level 2
    "REFH2a",       # Reference Heading Level 2 Alternate
    "Ref-H1",       # Reference Heading (alternate format)
    "Ref-H2",       # Reference Heading (alternate format)
    
    # Body Text (with text flow variants)
    "TXT",          # Body Text (indented)
    "TXT1", "TXT2", "TXT3", "TXT4",  # Body text in different text flows
    "TXT-FLUSH",    # Body Text Flush (no indent, after heading)
    "TXT-FLUSH1", "TXT-FLUSH2", "TXT-FLUSH4",  # Flush text in different flows
    "TXT-DC",       # Drop Cap Text
    "TXT-AU",       # Author Text
    "T",            # Table Cell Body Text
    
    # Bulleted Lists
    "BL-FIRST",     # Bullet List First Item
    "BL-MID",       # Bullet List Middle Item
    "BL-LAST",      # Bullet List Last Item
    "UL-FIRST",     # Unordered List First (nested)
    "UL-MID",       # Unordered List Middle (nested)
    "UL-LAST",      # Unordered List Last (nested)
    
    # Numbered Lists
    "NL-FIRST",     # Numbered List First Item
    "NL-MID",       # Numbered List Middle Item
    "NL-LAST",      # Numbered List Last Item
    
    # End of Chapter Lists
    "EOC-NL-FIRST", # End of Chapter Numbered List First
    "EOC-NL-MID",   # End of Chapter Numbered List Middle
    "EOC-NL-LAST",  # End of Chapter Numbered List Last
    "EOC-LL2-MID",  # End of Chapter List Level 2 Middle
    
    # Tables - Titles (with text flow variants)
    "T1",           # Table Title
    "T11", "T12",   # Table Title in text flow 1, 2
    "UNT-T1",       # Unnumbered Table Title
    "TableCaption", # Table Caption (alternate)
    "TableCaptions",# Table Captions section header
    
    # Tables - Headers (T2x for different header types)
    "T2",           # Table Header Row
    "T2-C",         # Table Header Centered
    "T21", "T22", "T23",  # Table header variants (different column types)
    
    # Tables - Row Headers and Body Cells
    "T3",           # Table Sub-header/Category Row
    "T4",           # Table Row Header (first column)
    "T5",           # Table Body Cell (data values)
    "T6",           # Table Body Cell variant (specific data)
    "T",            # Generic Table Cell
    
    # Tables - Lists inside cells
    "TBL-FIRST",    # Table Bulleted List First
    "TBL-MID",      # Table Bulleted List Middle
    "TBL-MID0",     # Table Bulleted List Middle (variant)
    "TBL-LAST",     # Table Bulleted List Last
    "TBL-LAST1",    # Table Bulleted List Last (flow variant)
    "TBL2-MID",     # Table Bulleted List Level 2 Middle
    "TBL3-MID",     # Table Bulleted List Level 3 Middle
    "TBL4-MID",     # Table Bulleted List Level 4 Middle
    "TUL-MID",      # Table Unordered List Middle
    "TNL-FIRST",    # Table Numbered List First
    "TNL-MID",      # Table Numbered List Middle
    "TNL-LAST",     # Table Numbered List Last
    
    # Tables - Footnotes (with flow variants)
    "TFN",          # Table Footnote
    "TFN1",         # Table Footnote (flow variant)
    "TSN",          # Table Source Note
    "TableFootnote",# Table Footnote (alternate)
    
    # Figures
    "FIG-LEG",      # Figure Legend
    "FIG-SRC",      # Figure Source
    "UNFIG-SRC",    # Unnumbered Figure Source
    "FigureCaption",# Figure Caption (alternate)
    "FigureLegend", # Figure Legend (alternate)
    "FigureSource", # Figure Source (alternate)
    "PMI",          # Picture/Media Item
    
    # References
    "REF-N",        # Reference Entry (numbered)
    "REF-N0",       # Reference Entry (variant)
    
    # Chapter Outline
    "COUT-1",       # Chapter Outline Level 1
    "COUT-2",       # Chapter Outline Level 2
    
    # Equations
    "EQ-ONLY",      # Single-line Equation
    "EQ-MID",       # Multi-line Equation (middle/continuation lines)
    
    # Appendix Styles
    "APX-TYPE",     # Appendix Type Label
    "APX-TTL",      # Appendix Title
    "APX-H1",       # Appendix Heading 1
    "APX-H2",       # Appendix Heading 2
    "APX-H3",       # Appendix Heading 3
    "APX-TXT",      # Appendix Text
    "APX-TXT-FLUSH",# Appendix Text Flush
    "APX-CAU",      # Appendix Author
    "APX-REF-N",    # Appendix Reference Entry
    "APX-REFH1",    # Appendix Reference Heading
    
    # Box Styles
    "NBX1-TTL",     # Numbered Box Title
    "NBX1-TXT",     # Numbered Box Text
    "NBX1-TXT-FLUSH",# Numbered Box Text Flush
    "NBX1-BL-FIRST",# Numbered Box Bullet First
    "NBX1-BL-MID",  # Numbered Box Bullet Middle
    "NBX1-BL-LAST", # Numbered Box Bullet Last
    "NBX1-BL2-MID", # Numbered Box Bullet Level 2 Middle
    "NBX1-NL-FIRST",# Numbered Box Number List First
    "NBX1-NL-MID",  # Numbered Box Number List Middle
    "NBX1-NL-LAST", # Numbered Box Number List Last
    "NBX1-DIA-FIRST",# Numbered Box Dialog First
    "NBX1-DIA-MID", # Numbered Box Dialog Middle
    "NBX1-DIA-LAST",# Numbered Box Dialog Last
    "NBX1-UNT",     # Numbered Box Unnumbered Text
    "NBX1-UNT-T2",  # Numbered Box Unnumbered Text T2
    "NBX1-SRC",     # Numbered Box Source
    "BX1-TXT-FIRST",# Box Text First
    
    # Case Studies
    "CS-H1",        # Case Study Heading 1
    "CS-TTL",       # Case Study Title
    "CS-TXT",       # Case Study Text
    "CS-TXT-FLUSH", # Case Study Text Flush
    "CS-QUES-TXT",  # Case Study Question Text
    "CS-ANS-TXT",   # Case Study Answer Text
    
    # Learning Objectives
    "OBJ1",         # Objective Heading
    "OBJ-TXT",      # Objective Text
    "OBJ-BL-FIRST", # Objective Bullet First
    "OBJ-BL-MID",   # Objective Bullet Middle
    "OBJ-BL-LAST",  # Objective Bullet Last
    "OBJ-TXT-FLUSH",# Objective Text Flush
    "OBJ-NL-FIRST", # Objective Numbered List First
    "OBJ-NL-MID",   # Objective Numbered List Middle
    "OBJ-NL-LAST",  # Objective Numbered List Last
    
    # Special/Miscellaneous
    "SUMHD",        # Summary Heading
    "EXT-ONLY",     # Extract Only
    "INTRO",        # Introduction text
    "QUO",          # Pull Quote
    "AAHead",       # Author Affiliation Header
    "SP-TTL",       # Special/Warning Title
    "SP-TXT",       # Special/Warning Text
    
    # Additional Box styles
    "NBX-TTL",      # Numbered Box Title (general)
    "NBX-TXT-FIRST",# Numbered Box Text First
    "NBX-TXT",      # Numbered Box Text
    "NBX-UL-FIRST", # Numbered Box Unnumbered List First
    "NBX-UL-MID",   # Numbered Box Unnumbered List Middle
    "NBX-UL-LAST",  # Numbered Box Unnumbered List Last
    "NBX1-TTL",     # Numbered Box 1 Title
    "BX1-TTL",      # Box 1 Title
    "BX1-TXT-FIRST",# Box 1 Text First
    "BX1-TXT",      # Box 1 Text
    "BX1-BL-FIRST", # Box 1 Bullet First
    "BX1-BL-MID",   # Box 1 Bullet Middle
    "BX1-BL-LAST",  # Box 1 Bullet Last
    "BX2-TTL",      # Box 2 Title
    "BX2-TXT-FLUSH",# Box 2 Text Flush
    "BX2-TXT-FIRST",# Box 2 Text First  
    "BX2-TXT",      # Box 2 Text
    "BX2-TXT-LAST", # Box 2 Text Last
    "BX2-BL-FIRST", # Box 2 Bullet First
    "BX2-BL-MID",   # Box 2 Bullet Middle
    "BX2-BL-LAST",  # Box 2 Bullet Last
    "BX2-NL-FIRST", # Box 2 Numbered List First
    "BX2-NL-MID",   # Box 2 Numbered List Middle
    "BX2-NL-LAST",  # Box 2 Numbered List Last
    "BX3-TTL",      # Box 3 Title
    "BX3-TXT",      # Box 3 Text
    "BX4-TTL",      # Box 4 Title
    "BX4-TXT-FIRST",# Box 4 Text First
    "BX4-TXT",      # Box 4 Text
    
    # Additional styles from various sources
    "KEY-TXT",      # Key Terms Text
    "KEY-BL-MID",   # Key Terms Bullet Middle
    "KP-TXT",       # Key Points Text
    "KP-BL-MID",    # Key Points Bullet Middle
    "DIA",          # Dialog
    "SR",           # Source Reference
    "SRH1",         # Source Reference Heading
    "COBJ",         # Chapter Objectives
    "CO_KTL",       # Chapter Outline Key Term List
    "CTC-H1",       # CTC Heading 1
    "CTC-BL-MID",   # CTC Bullet Middle
    "DOM-TTL",      # Domain Title
    "CARD-NUM",     # Card Number
    "CJC-TTL",      # CJC Title
    "CJC-SUBTTL",   # CJC Subtitle
    "CJC-NN-TXT",   # CJC Unnumbered Text
    "NN-DIA",       # Unnumbered Dialog
    "RQ-LL2-MID",   # Review Question List Level 2 Middle
    "RQ-NL-MID",    # Review Question Numbered List Middle
    "RQ-ANS",       # Review Question Answer
    "QUES-TXT-FLUSH",# Question Text Flush
    "QUES-LL2-MID", # Question List Level 2 Middle
    "ANS-TXT",      # Answer Text
    "T4",           # Table Row Header
    "UL-FL2",       # Unordered List Flush Level 2
    "EOC_REF",      # End of Chapter Reference
    "EOC_NL",       # End of Chapter Numbered List
    "EOC_NLLL",     # End of Chapter Numbered List Last Level
    "BL2-MID",      # Bullet List Level 2 Middle
    "BL3-MID",      # Bullet List Level 3 Middle
    "TUL-MID",      # Table Unordered List Middle
    "CHAP-BM",      # Chapter Back Matter
    
    # System/Default
    "Normal",       # Normal paragraph
    "ListParagraph",# List Paragraph
    "TableList",    # Table List
}

# Prefer the official StyleList if available
if ALLOWED_STYLES:
    VALID_TAGS = ALLOWED_STYLES

# =============================================================================
# ZONE-BASED STYLE CONSTRAINTS
# Defines which styles are valid for each document zone.
# Supports wildcard matching (e.g., 'NBX-TXT*' matches 'NBX-TXT', 'NBX-TXT-FIRST')
# =============================================================================

ZONE_STYLE_CONSTRAINTS = {
    'METADATA': ['PMI'],
    'FRONT_MATTER': [
        'CN', 'CT', 'CST', 'CAU', 'CHAP',
        'OBJ1', 'OBJ-*',
        'COUT-1', 'COUT-2', 'KT1', 'KT-*',
        'TXT', 'TXT-*', 'H1', 'H2', 'H3', 'H11', 'H12',
        'BL-*', 'NL-*', 'UL-*',
        'BX1-*', 'BX2-*', 'BX3-*', 'BX4-*',
        'PMI', 'QUO', 'TSN',
        'SR*', 'REF*', 'REFH*',
    ],
    'TABLE': [
        'T', 'T1', 'T2', 'T2-C', 'T3', 'T4', 'T5', 'TD',
        'TH1', 'TH2', 'TH3', 'TH4', 'TH5', 'TH6',
        'TBL-FIRST', 'TBL-MID', 'TBL-LAST', 'TBL2-MID',
        'TNL-FIRST', 'TNL-MID', 'TUL-MID',
        'TFN', 'TSN',
        'PMI',
    ],
    'BOX_NBX': [
        'NBX-*', 'Box-01-*',
        'H1', 'H2', 'H3',
        'TXT', 'TXT-*', 'BL-*', 'NL-*', 'UL-*',
        'PMI',
    ],
    'BOX_BX1': ['BX1-*', 'H1', 'H2', 'H3', 'TXT', 'TXT-*', 'BL-*', 'NL-*', 'UL-*', 'PMI'],
    'BOX_BX2': ['BX2-*', 'H1', 'H2', 'H3', 'TXT', 'TXT-*', 'BL-*', 'NL-*', 'UL-*', 'PMI'],
    'BOX_BX3': ['BX3-*', 'H1', 'H2', 'H3', 'TXT', 'TXT-*', 'BL-*', 'NL-*', 'UL-*', 'PMI'],
    'BOX_BX4': ['BX4-*', 'H1', 'H2', 'H3', 'TXT', 'TXT-*', 'BL-*', 'NL-*', 'UL-*', 'PMI'],
    'BACK_MATTER': [
        'REF-N', 'REF-U', 'REFH1', 'REFH2', 'SR', 'SRH1',
        'EOC-*',
        'BL-*', 'NL-*', 'UL-*',
        'GLOS-*', 'IDX-*', 'APX-*',
        'PMI',
    ],
    'BODY': None,  # No constraints - full style range
}


def validate_style_for_zone(style: str, zone: str) -> bool:
    """
    Check if a style is valid for a given zone.
    
    Args:
        style: The style tag to validate
        zone: The context zone (FRONT_MATTER, BODY, TABLE, BOX_*, BACK_MATTER)
    
    Returns:
        True if style is valid for zone, False otherwise
    """
    valid_styles = ZONE_STYLE_CONSTRAINTS.get(zone)
    if valid_styles is None:
        return True  # BODY or unknown zone has no constraints
    
    # Check exact match or wildcard match
    for valid in valid_styles:
        if valid.endswith('*'):
            # Wildcard match (e.g. 'NBX-BL-*' matches 'NBX-BL-MID')
            prefix = valid[:-1]
            if style.startswith(prefix):
                return True
        elif style == valid:
            return True
            
    return False

# Maximum paragraphs per API call to avoid token limits
MAX_PARAGRAPHS_PER_CHUNK = 75  # Reduced from 100 for faster, more reliable processing

# Confidence threshold for Flash fallback
FLASH_FALLBACK_THRESHOLD = 75  # Items below this confidence get re-evaluated by Flash


class GeminiClassifier:
    """
    Document style classifier using Gemini API with hybrid model support.
    
    Primary: Gemini 2.5 Flash-Lite (fast, cost-effective)
    Fallback: Gemini 2.5 Flash (higher quality for low-confidence items)
    
    Handles large documents by chunking if necessary.
    Tracks token usage for cost monitoring.
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-pro",
        fallback_model_name: str = "gemini-2.5-flash",
        fallback_threshold: int = FLASH_FALLBACK_THRESHOLD,
        enable_fallback: bool = True,
        system_prompt_override: str | None = None,
        fallback_prompt_override: str | None = None,
    ):
        """
        Initialize the classifier with optional Flash fallback.

        Args:
            api_key: Google AI API key
            model_name: Primary Gemini model (default: gemini-2.5-pro)
            fallback_model_name: Fallback model for low-confidence items (default: gemini-2.5-flash)
            fallback_threshold: Confidence threshold below which to use fallback
            enable_fallback: Whether to enable the fallback system
        """
        # Load system prompt
        system_prompt = system_prompt_override or self._load_system_prompt()

        # Primary model (gemini-2.5-pro - high quality)
        self.model = GeminiClient(
            api_key=api_key,
            model_name=model_name,
            temperature=0.1,
            top_p=0.95,
            max_output_tokens=65536,
            system_instruction=system_prompt,
            max_retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY,
            timeout=API_TIMEOUT,
        )
        self.primary_model_name = model_name

        # Fallback model (gemini-2.5-flash - faster)
        self.fallback_model = None
        self.fallback_model_name = fallback_model_name
        self.fallback_threshold = fallback_threshold
        self.enable_fallback = enable_fallback

        if enable_fallback:
            # Load fallback-specific system prompt (more detailed for difficult cases)
            fallback_prompt = fallback_prompt_override or self._get_fallback_system_prompt()
            self.fallback_model = GeminiClient(
                api_key=api_key,
                model_name=fallback_model_name,
                temperature=0.05,  # Lower temperature for more consistent output
                top_p=0.9,
                max_output_tokens=16384,
                system_instruction=fallback_prompt,
                max_retries=MAX_RETRIES,
                retry_delay=RETRY_DELAY,
                timeout=60,  # Shorter timeout for fallback
            )
            logger.info(f"Fallback model enabled: {fallback_model_name} (threshold: {fallback_threshold}%)")

        # Store timeout for use in API calls
        self.api_timeout = API_TIMEOUT
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY

        # Token usage tracking for fallback (separate from primary model)
        self.fallback_input_tokens = 0
        self.fallback_output_tokens = 0

        # Statistics
        self.fallback_calls = 0
        self.items_improved = 0

        # Grounded retriever for few-shot examples
        try:
            self.retriever = get_retriever()
            logger.info(f"Loaded ground truth retriever with {len(self.retriever.examples)} examples")
        except Exception as e:
            logger.warning(f"Failed to load ground truth retriever: {e}")
            self.retriever = None

        # Prediction cache to avoid repeated API calls
        try:
            self.cache = get_cache()
            logger.info(f"Initialized prediction cache")
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {e}")
            self.cache = None

        # Rule learner for deterministic classification before LLM
        try:
            self.rule_learner = RuleLearner()
            self.rule_learner.load_rules()
            if self.rule_learner.rules:
                logger.info(f"Loaded {len(self.rule_learner.rules)} deterministic rules")
            else:
                logger.info("No learned rules found - will use LLM for all predictions")
        except Exception as e:
            logger.warning(f"Failed to load rule learner: {e}")
            self.rule_learner = None

        # Statistics for rule-based predictions
        self.rule_predictions = 0
        self.llm_predictions = 0

        logger.info(f"Initialized Gemini classifier with model: {model_name}, timeout: {API_TIMEOUT}s")
    
    def _apply_rules(
        self,
        paragraphs: list[dict],
        min_confidence: float = 0.80
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """
        Apply learned deterministic rules to paragraphs before LLM classification.

        Args:
            paragraphs: List of paragraph dicts with text and metadata
            min_confidence: Minimum confidence threshold for rule prediction

        Returns:
            Tuple of (rule_predictions, llm_needed, all_results_so_far)
            - rule_predictions: List of predictions made by rules
            - llm_needed: List of paragraphs that still need LLM classification
            - all_results_so_far: Combined list with rule predictions filled in
        """
        if not self.rule_learner or not self.rule_learner.rules:
            # No rules available, all paragraphs need LLM
            return [], paragraphs, []

        rule_predictions = []
        llm_needed = []
        all_results = []

        for para in paragraphs:
            para_id = para.get('id')
            text = para.get('text', '')
            metadata = para.get('metadata', {})

            # Try to predict using rules
            predicted_tag = self.rule_learner.apply_rules(text, metadata)

            if predicted_tag:
                # Find the rule that matched to get its confidence
                features = self.rule_learner.feature_extractor.extract_features(text, metadata)
                matched_rule = None

                for rule in self.rule_learner.rules:
                    if self.rule_learner._feature_matches(features, rule["condition"]):
                        matched_rule = rule
                        break

                rule_confidence = matched_rule["confidence"] if matched_rule else 0.8

                # Only use rule if confidence is high enough
                if rule_confidence >= min_confidence:
                    result = {
                        "id": para_id,
                        "tag": predicted_tag,
                        "confidence": int(rule_confidence * 100),
                        "reasoning": f"Rule: {matched_rule['condition']}" if matched_rule else "Rule-based",
                        "rule_based": True,
                    }
                    rule_predictions.append(result)
                    all_results.append(result)
                    self.rule_predictions += 1
                    continue

            # No high-confidence rule match, needs LLM
            llm_needed.append(para)
            # Placeholder for LLM result (will be filled later)
            all_results.append({
                "id": para_id,
                "tag": "TXT",  # Temporary placeholder
                "confidence": 0,
                "rule_based": False,
            })

        if rule_predictions:
            logger.info(
                f"Rule-based classification: {len(rule_predictions)}/{len(paragraphs)} paragraphs "
                f"({len(rule_predictions)/len(paragraphs)*100:.1f}% coverage)"
            )

        return rule_predictions, llm_needed, all_results

    def _get_fallback_system_prompt(self) -> str:
        """Get specialized system prompt for fallback model - focused on difficult cases."""
        return """You are an expert document style classifier specializing in DIFFICULT CASES.

You are being called because another AI was uncertain about these paragraphs. 
Your task is to make the FINAL determination with high confidence.

CLASSIFICATION RULES:
1. Analyze context carefully - what comes before and after matters
2. Consider document structure and flow
3. Use zone constraints strictly (styles must match their zone)
4. When uncertain between two options, use these tiebreakers:
   - Lists: Check if bullet/number present → BL-*/NL-*, otherwise → UL-*
   - First para after heading → TXT-FLUSH (no indent)
   - Middle of paragraph block → TXT (with indent)
   - Table cells: Header row → T2, First column → T4, Body → T
   - List position: Single item → use -FIRST, check neighbors for -MID/-LAST

OUTPUT FORMAT:
Return a JSON array with your classifications:
[{"id": 1, "tag": "STYLE-TAG", "confidence": 95, "reasoning": "Brief explanation"}]

IMPORTANT:
- Be MORE confident than the primary model
- Your confidence should typically be 85-99%
- Include brief reasoning for every item
- Focus on the MOST LIKELY correct answer"""
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from file or use embedded default."""
        if SYSTEM_PROMPT_PATH.exists():
            with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # Embedded minimal prompt as fallback
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """Return default system prompt."""
        return """You are an expert document style classifier for academic publishing.
        
Classify each paragraph with the correct style tag. Output a valid JSON array:
[{"id": 1, "tag": "CN", "confidence": 99}, ...]

IMPORTANT: 
- Output ONLY valid JSON, no markdown code fences
- Include ALL paragraphs in your response
- Include "reasoning" field only for confidence < 85

Common tags: CN (chapter number), CT (chapter title), H1-H6 (headings), 
TXT (body text), TXT-FLUSH (first para after heading), BL-FIRST/MID/LAST (bullets),
NL-FIRST/MID/LAST (numbered lists), REF-N (references), T1 (table title),
T2 (table header), T4 (row header), T (table cell), TBL-MID (table bullet), TFN (table footnote), FIG-LEG (figure legend)."""
    
    def build_user_prompt(
        self,
        paragraphs: list[dict],
        document_name: str,
        document_type: str = "Academic Document",
        chunk_info: str = ""
    ) -> str:
        """
        Build the user prompt for classification with context zone hints.
        """
        # Import zone validation functions
        # from .ingestion import ZONE_VALID_STYLES, get_zone_style_summary  <-- REMOVED per zone constraints plan

        
        # Format paragraphs with zone context hints
        lines = []
        for para in paragraphs:
            text = para.get('text', '')
            metadata = para.get('metadata', {})
            
            # Prepend visual cue for LLM if metadata indicates list but text doesn't show it
            # This helps detection of automatic Word lists that don't have bullets in .text
            if metadata.get('has_bullet') and not text.lstrip().startswith(('•', '-', '*', '●', '○', '▪')):
                text = f"• {text}"
            elif metadata.get('has_numbering') and not re.match(r'^\s*[\d\w]+\.', text):
                text = f"1. {text}"
            
            # Handle generic XML list items (ambiguous type)
            if metadata.get('has_xml_list'):
                # Don't modify text, just add to context
                # This prevents forcing NL/BL bias
                # But we'll add it to context_parts below
                pass
            context_parts = []
            
            # Add context zone hint (primary identifier)
            context_zone = metadata.get('context_zone', 'BODY')
            if context_zone != 'BODY':
                context_parts.append(context_zone)
            
            # Add table-specific context
            if metadata.get('is_table'):
                table_idx = metadata.get('table_index', 0)
                row_idx = metadata.get('row_index', 0)
                cell_idx = metadata.get('cell_index', 0)
                is_header = metadata.get('is_header_row', False)
                is_first_col = metadata.get('is_first_column', False)
                inferred = metadata.get('inferred_style', '')
                
                # Build table hint
                table_hints = [f"TABLE{table_idx+1}"]
                if is_header:
                    table_hints.append("HEADER_ROW")
                elif is_first_col:
                    table_hints.append("FIRST_COL")
                else:
                    table_hints.append(f"R{row_idx}C{cell_idx}")
                
                if inferred:
                    table_hints.append(f"likely:{inferred}")
                
                context_parts.append(",".join(table_hints))
            
            # Add box type if present
            box_type = metadata.get('box_type')
            if box_type:
                context_parts.append(f"box:{box_type}")
            
            # Add generic list hint
            if metadata.get('has_xml_list'):
                context_parts.append("LIST_ITEM")

            # Add list/caption/source hints from block extraction
            list_kind = metadata.get('list_kind')
            list_pos = metadata.get('list_position')
            if list_kind:
                if list_pos:
                    context_parts.append(f"LIST:{list_kind},{list_pos}")
                else:
                    context_parts.append(f"LIST:{list_kind}")

            caption_type = metadata.get('caption_type')
            if caption_type:
                context_parts.append(f"CAPTION:{caption_type}")

            if metadata.get('source_line'):
                context_parts.append("SOURCE_LINE")

            if metadata.get('box_marker'):
                context_parts.append(f"BOX_MARKER:{metadata['box_marker']}")
            
            # Build context hint string
            if context_parts:
                context_hint = f" [{' | '.join(context_parts)}]"
            else:
                context_hint = ""
            
            lines.append(f"[{para['id']}]{context_hint} {text}")
        
        formatted_paragraphs = "\n".join(lines)
        
        # Count zones and collect unique zones
        zone_counts = {}
        for p in paragraphs:
            zone = p.get('metadata', {}).get('context_zone', 'BODY')
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
        
        # Build enhanced zone instructions with specific valid styles
        zone_notes = []
        
        # Helper to format valid styles for prompt
        def format_valid_styles(zone_name):
            constraints = ZONE_STYLE_CONSTRAINTS.get(zone_name)
            if not constraints:
                return "Full range (H1-H6, TXT, BL-*, NL-*, etc.)"
            return ", ".join(constraints)

        if zone_counts.get('METADATA', 0) > 0:
            zone_notes.append(f"- METADATA ({zone_counts['METADATA']} items): Pre-press info")
            zone_notes.append(f"  VALID STYLES: {format_valid_styles('METADATA')}")
        
        if zone_counts.get('FRONT_MATTER', 0) > 0:
            zone_notes.append(f"- FRONT_MATTER ({zone_counts['FRONT_MATTER']} items): Chapter opener/objectives")
            zone_notes.append(f"  VALID STYLES: {format_valid_styles('FRONT_MATTER')}")
        
        if zone_counts.get('TABLE', 0) > 0:
            zone_notes.append(f"- TABLE ({zone_counts['TABLE']} items): Table cell content")
            zone_notes.append(f"  VALID STYLES: {format_valid_styles('TABLE')}")
        
        # Check for box zones
        box_zones = [z for z in zone_counts.keys() if z.startswith('BOX_')]
        for bz in sorted(box_zones):
            prefix = bz.replace('BOX_', '')
            zone_notes.append(f"- {bz} ({zone_counts[bz]} items): Box content")
            
            # Use specific constraints if defined, otherwise fallback to prefix matching hint
            if bz in ZONE_STYLE_CONSTRAINTS:
                 zone_notes.append(f"  VALID STYLES: {format_valid_styles(bz)}")
            else:
                 zone_notes.append(f"  VALID STYLES: {prefix}-* styles")
        
        if zone_counts.get('BACK_MATTER', 0) > 0:
            zone_notes.append(f"- BACK_MATTER ({zone_counts['BACK_MATTER']} items): References/end-of-chapter")
            zone_notes.append(f"  VALID STYLES: {format_valid_styles('BACK_MATTER')}")
        
        if zone_counts.get('BODY', 0) > 0:
            zone_notes.append(f"- BODY ({zone_counts['BODY']} items): Main chapter content")
            zone_notes.append(f"  VALID STYLES: Full range (H1-H6, TXT, BL-*, NL-*, FIG-*, etc.)")
        
        zone_section = ""
        if zone_notes:
            zone_section = "\nCONTEXT ZONES DETECTED:\n" + "\n".join(zone_notes) + "\n\n⚠️ IMPORTANT: Use ONLY styles valid for each paragraph's zone. Zone violations will be flagged.\n"
        
        # === GROUNDED FEW-SHOT EXAMPLES ===
        # Retrieve similar examples from ground truth for few-shot prompting
        grounded_examples_section = ""
        if self.retriever:
            try:
                # Get diverse examples for context
                # Try to retrieve examples similar to first few paragraphs
                sample_texts = [p.get('text', '')[:200] for p in paragraphs[:3]]
                sample_text = " ".join(sample_texts)

                # Get examples: prefer similar content from any book
                examples = self.retriever.retrieve_examples(
                    text=sample_text,
                    k=10,  # Get 10 diverse examples
                    zone=paragraphs[0].get('metadata', {}).get('context_zone') if paragraphs else None
                )

                if examples:
                    grounded_examples_section = "\n" + self.retriever.format_examples_for_prompt(examples) + "\n"
                    logger.debug(f"Injected {len(examples)} grounded examples into prompt")
            except Exception as e:
                logger.warning(f"Failed to retrieve grounded examples: {e}")

        allowed_tags = ", ".join(sorted(VALID_TAGS))
        prompt = f"""Document: {document_name}
Document Type: {document_type}
Total Paragraphs in this batch: {len(paragraphs)}
{chunk_info}{zone_section}{grounded_examples_section}
IMPORTANT: Return a complete JSON array with ALL {len(paragraphs)} paragraphs classified.
IMPORTANT: Return ONLY one of these tags exactly (case-sensitive): {allowed_tags}
IMPORTANT: The `tag` value must be only the exact style token, with no punctuation, labels, or commentary.
IMPORTANT: Learn from the GROUND TRUTH EXAMPLES above - they show real manual-tagged patterns from similar books.
IMPORTANT: If unsure, choose TXT.

---

Classify each paragraph below:

{formatted_paragraphs}"""

        return prompt

    def _sanitize_raw_tag(self, tag: str) -> str:
        """
        Strictly sanitize raw model tag output before canonical normalization.
        """
        raw = str(tag or "").strip()
        if not raw:
            return "TXT"
        upper = raw.upper()
        if STRICT_TAG_RE.fullmatch(upper):
            return upper

        candidates = EXTRACT_TAG_RE.findall(upper)
        if candidates:
            for candidate in candidates:
                normalized = normalize_style(candidate)
                if normalized in VALID_TAGS:
                    return candidate
            return candidates[0]
        return "TXT"

    def _map_tag_alias(self, tag: str, meta: dict | None = None, text: str = "") -> str:
        """
        Map known model aliases/invalid variants to allowed canonical tags.
        """
        mapped = normalize_style(self._sanitize_raw_tag(tag), meta=meta)
        original_mapped = mapped

        zone = (meta or {}).get("context_zone", "")
        in_ref_zone = bool((meta or {}).get("is_reference_zone")) or zone == "REFERENCE"
        numbered = bool(REF_NUMBER_RE.match((text or "").strip()))
        bulleted = bool(REF_BULLET_RE.match((text or "").strip()))

        table_heading_map = {
            "SK_H1": "TH1", "SK_H2": "TH2", "SK_H3": "TH3", "SK_H4": "TH4",
            "TBL-H1": "TH1", "TBL-H2": "TH2", "TBL-H3": "TH3", "TBL-H4": "TH4",
        }
        if zone == "TABLE" and mapped in table_heading_map:
            candidate = table_heading_map[mapped]
            if candidate in VALID_TAGS:
                return candidate

        if in_ref_zone and (mapped.startswith("UL-") or mapped.startswith("BL-") or mapped.startswith("NL-")):
            candidate = "REF-U" if bulleted else "REF-N"
            if candidate in VALID_TAGS:
                return candidate

        if mapped == "BIBITEM":
            if in_ref_zone:
                candidate = "REF-U" if bulleted else "REF-N"
                if candidate in VALID_TAGS:
                    return candidate
            for candidate in ("REF-U", "REF-N", "TXT"):
                if candidate in VALID_TAGS:
                    return candidate

        if mapped == "COUT":
            for candidate in ("COUT-1", "COUT-2", "TXT"):
                if candidate in VALID_TAGS:
                    return candidate

        # Common shorthand / malformed aliases.
        if mapped == "HH":
            return "H1" if "H1" in VALID_TAGS else "TXT"
        if mapped == "REF":
            candidate = "REF-U" if bulleted else "REF-N"
            if candidate in VALID_TAGS:
                return candidate
        if mapped == "TYPE":
            if zone.startswith("BOX_"):
                zone_prefix = zone[len("BOX_"):]
                candidate = f"{zone_prefix}-TYPE"
                if candidate in VALID_TAGS:
                    return candidate
            if zone == "TABLE":
                return "T" if "T" in VALID_TAGS else mapped
        if mapped == "TTL":
            if zone.startswith("BOX_"):
                zone_prefix = zone[len("BOX_"):]
                candidate = f"{zone_prefix}-TTL"
                if candidate in VALID_TAGS:
                    return candidate
            if zone == "TABLE":
                for candidate in ("T1", "T2", "T"):
                    if candidate in VALID_TAGS:
                        return candidate

        # Normalize table list spellings sometimes produced by models.
        tbl_list = re.fullmatch(r"TBL-(BL|NL|UL)-(FIRST|MID|LAST)", mapped)
        if tbl_list:
            list_kind, pos = tbl_list.groups()
            if list_kind == "BL":
                candidate = f"TBL-{pos}"
            elif list_kind == "NL":
                candidate = f"TNL-{pos}"
            else:
                candidate = f"TUL-{pos}"
            if candidate in VALID_TAGS:
                return candidate
            if list_kind == "BL" and "TBL-MID" in VALID_TAGS:
                return "TBL-MID"
            if list_kind == "NL" and "TNL-MID" in VALID_TAGS:
                return "TNL-MID"
            if list_kind == "UL" and "TUL-MID" in VALID_TAGS:
                return "TUL-MID"
        if mapped == "TBL-TXT":
            for candidate in ("T", "TD", "TXT"):
                if candidate in VALID_TAGS:
                    return candidate
        if mapped == "BL-TXT":
            for candidate in ("BL-MID", "TXT"):
                if candidate in VALID_TAGS:
                    return candidate

        for vendor_prefix in ("EFP-", "EYU-"):
            if mapped.startswith(vendor_prefix):
                remainder = mapped[len(vendor_prefix):]
                if remainder.startswith("BX-"):
                    candidate = f"BX4-{remainder[3:]}"
                    if candidate in VALID_TAGS:
                        return candidate
                if remainder in VALID_TAGS:
                    return remainder
                # Bare box name without subtype (e.g., EFP-BX → TXT)
                if remainder == "BX":
                    for candidate in ("TXT",):
                        if candidate in VALID_TAGS:
                            return candidate

        # Numeric-prefixed shorthand from model output (e.g., 1-TTL, 2-TXT-FLUSH).
        # If we are in a box zone, use that zone's prefix as the canonical family.
        m_short = re.fullmatch(r"\d+-([A-Z0-9-]+)", mapped)
        if m_short:
            mapped = m_short.group(1)
            if zone.startswith("BOX_"):
                zone_prefix = zone[len("BOX_"):]
                candidate = f"{zone_prefix}-{mapped}"
                if candidate in VALID_TAGS:
                    return candidate

        # When a model emits bare subtype tokens inside a box zone (e.g., TTL),
        # map to that zone family (e.g., BOX_BX2 + TTL -> BX2-TTL).
        if zone.startswith("BOX_"):
            zone_prefix = zone[len("BOX_"):]
            candidate = f"{zone_prefix}-{mapped}"
            if candidate in VALID_TAGS:
                return candidate

        # No zone hint available: try numeric prefix directly as BX family.
        m_num = re.fullmatch(r"(\d+)-([A-Z0-9-]+)", original_mapped)
        if m_num:
            candidate = f"BX{m_num.group(1)}-{m_num.group(2)}"
            if candidate in VALID_TAGS:
                return candidate
        if mapped.isdigit() and zone.startswith("BOX_"):
            zone_prefix = zone[len("BOX_"):]
            for suffix in ("TTL", "TYPE", "TXT"):
                candidate = f"{zone_prefix}-{suffix}"
                if candidate in VALID_TAGS:
                    return candidate

        # Zone-aware coercion to avoid invalid/non-actionable tags.
        if zone == "TABLE":
            if mapped.startswith(("BX", "NBX", "KT-", "KP-", "OBJ-")):
                if mapped.endswith("-FIRST") and "TBL-FIRST" in VALID_TAGS:
                    return "TBL-FIRST"
                if mapped.endswith("-LAST") and "TBL-LAST" in VALID_TAGS:
                    return "TBL-LAST"
                if mapped.endswith("-MID") and "TBL-MID" in VALID_TAGS:
                    return "TBL-MID"
                return "T" if "T" in VALID_TAGS else mapped
            if mapped.startswith("H") and mapped[1:].isdigit():
                for candidate in ("TH1", "T2", "T"):
                    if candidate in VALID_TAGS:
                        return candidate

        if zone == "BACK_MATTER" and mapped not in {"SR", "SRH1"}:
            if mapped.startswith(("FIG-", "T", "TFN", "TSN", "REF", "H")):
                candidate = "REF-U" if bulleted else "REF-N"
                if candidate in VALID_TAGS:
                    return candidate

        if mapped in VALID_TAGS:
            return mapped

        return mapped

    def _apply_alias_mappings(self, results: list[dict], meta_by_id: dict | None = None, text_by_id: dict | None = None) -> list[dict]:
        for r in results:
            rid = r.get("id")
            meta = meta_by_id.get(rid) if meta_by_id else None
            text = text_by_id.get(rid, "") if text_by_id else ""
            mapped = self._map_tag_alias(r.get("tag", ""), meta=meta, text=text)
            r["tag"] = mapped
        return results
    
    def classify(
        self,
        paragraphs: list[dict],
        document_name: str,
        document_type: str = "Academic Document"
    ) -> list[dict]:
        """
        Classify all paragraphs in a document.
        - Applies deterministic rules first (grounded-first approach)
        - Checks cache for already classified paragraphs
        - Sends only uncertain paragraphs to LLM
        - Automatically chunks large documents
        - Validates results against zone constraints and ground truth
        - Uses Flash fallback for low-confidence items
        - Caches predictions for future reuse
        """
        total_paragraphs = len(paragraphs)

        # === CACHE CHECK ===
        # Check cache for already classified paragraphs
        cached_results: dict[int, dict] = {}
        uncached_paragraphs: list[dict] = []

        if self.cache:
            for para in paragraphs:
                para_id = para.get('id')
                text = para.get('text', '')
                zone = para.get('metadata', {}).get('context_zone', 'BODY')

                cached = self.cache.get(
                    doc_id=document_name,
                    para_index=para_id,
                    text=text,
                    zone=zone
                )

                if cached:
                    cached_results[para_id] = cached
                else:
                    uncached_paragraphs.append(para)

            if cached_results:
                logger.info(f"Cache: {len(cached_results)} cached, {len(uncached_paragraphs)} need classification")

            # If all cached, return immediately
            if not uncached_paragraphs:
                logger.info("All paragraphs found in cache, skipping API call")
                return sorted(cached_results.values(), key=lambda x: x['id'])

            # Use uncached paragraphs for classification
            paragraphs = uncached_paragraphs
            total_paragraphs = len(paragraphs)

        # === RULE-BASED CLASSIFICATION (GROUNDED-FIRST) ===
        # Apply deterministic rules before calling LLM
        rule_predictions, llm_needed, partial_results = self._apply_rules(paragraphs, min_confidence=0.80)

        # Keep reference to all original paragraphs for caching later
        all_original_paragraphs = {p['id']: p for p in paragraphs}

        # If all paragraphs handled by rules, return early
        if not llm_needed:
            logger.info(f"All {len(paragraphs)} paragraphs classified by rules (100% coverage), skipping LLM")
            self.llm_predictions += 0

            # Still need to validate and cache
            results = self.validate_zone_constraints(rule_predictions, paragraphs)

            # Cache rule predictions
            if self.cache:
                for result in results:
                    para_id = result.get('id')
                    para = all_original_paragraphs.get(para_id)
                    if para:
                        self.cache.set(
                            doc_id=document_name,
                            para_index=para_id,
                            text=para.get('text', ''),
                            prediction=result,
                            zone=para.get('metadata', {}).get('context_zone', 'BODY')
                        )

            # Merge with cached results if any
            if cached_results:
                all_results = list(cached_results.values()) + results
                all_results.sort(key=lambda x: x['id'])
                return all_results

            return results

        # Some paragraphs still need LLM classification
        logger.info(f"LLM needed for {len(llm_needed)}/{total_paragraphs} paragraphs after rule filtering")
        paragraphs = llm_needed  # Only classify these with LLM
        total_paragraphs = len(paragraphs)
        
        # Check if we need to chunk
        if total_paragraphs <= MAX_PARAGRAPHS_PER_CHUNK:
            # Single API call
            results = self._classify_chunk(paragraphs, document_name, document_type)
        else:
            # Chunk the document
            logger.info(f"Large document ({total_paragraphs} paragraphs), processing in chunks")
            all_results = []
            
            for i in range(0, total_paragraphs, MAX_PARAGRAPHS_PER_CHUNK):
                chunk = paragraphs[i:i + MAX_PARAGRAPHS_PER_CHUNK]
                chunk_num = i // MAX_PARAGRAPHS_PER_CHUNK + 1
                total_chunks = (total_paragraphs + MAX_PARAGRAPHS_PER_CHUNK - 1) // MAX_PARAGRAPHS_PER_CHUNK
                
                chunk_info = f"Chunk {chunk_num} of {total_chunks} (paragraphs {chunk[0]['id']} to {chunk[-1]['id']})"
                logger.info(f"Processing {chunk_info}")
                
                chunk_results = self._classify_chunk(
                    chunk, 
                    document_name, 
                    document_type,
                    chunk_info
                )
                all_results.extend(chunk_results)
            
            # Validate all results
            results = self._validate_results(all_results, total_paragraphs)
        
        # Post-validate against zone constraints
        results = self.validate_zone_constraints(results, paragraphs)
        
        # Log zone violation summary
        violations = [r for r in results if r.get('zone_violation')]
        if violations:
            logger.warning(f"Zone validation: {len(violations)} violations detected out of {len(results)} paragraphs")
            for v in violations[:5]:  # Show first 5
                logger.warning(f"  Para {v['id']}: '{v['tag']}' not valid for zone '{v.get('expected_zone')}'")
            if len(violations) > 5:
                logger.warning(f"  ... and {len(violations) - 5} more")
        else:
            logger.info("Zone validation: All styles valid for their zones")
        
        # === MERGE LLM RESULTS WITH RULE PREDICTIONS ===
        # Track LLM prediction count
        self.llm_predictions += len(results)

        # Merge LLM results with rule predictions
        if rule_predictions:
            # Build lookup for LLM results by ID
            llm_results_by_id = {r['id']: r for r in results}

            # Combine: use rule predictions where available, LLM results for the rest
            combined_results = []
            for rule_pred in rule_predictions:
                combined_results.append(rule_pred)

            # Add LLM results for paragraphs not covered by rules
            for llm_result in results:
                # Only add if not already present in rule predictions
                if not any(r['id'] == llm_result['id'] for r in rule_predictions):
                    combined_results.append(llm_result)

            # Sort by ID
            combined_results.sort(key=lambda x: x['id'])
            results = combined_results

            logger.info(
                f"Classification complete: {len(rule_predictions)} by rules, "
                f"{len(results) - len(rule_predictions)} by LLM"
            )

        # === FLASH FALLBACK FOR LOW-CONFIDENCE ITEMS ===
        if self.enable_fallback and self.fallback_model:
            # Build complete paragraph list for fallback processing
            all_paras_for_fallback = [all_original_paragraphs[r['id']] for r in results if r['id'] in all_original_paragraphs]
            results = self._process_fallback(results, all_paras_for_fallback, document_name)

        # === CACHE PREDICTIONS ===
        # Save new predictions to cache (both rule and LLM predictions)
        if self.cache:
            for result in results:
                para_id = result.get('id')
                para = all_original_paragraphs.get(para_id)

                if para:
                    self.cache.set(
                        doc_id=document_name,
                        para_index=para_id,
                        text=para.get('text', ''),
                        prediction=result,
                        zone=para.get('metadata', {}).get('context_zone', 'BODY')
                    )

            cache_stats = self.cache.get_stats()
            logger.info(f"Cache stats: {cache_stats}")

        # === MERGE WITH CACHED RESULTS ===
        # Combine newly classified with cached results
        if cached_results:
            all_results = list(cached_results.values()) + results
            all_results.sort(key=lambda x: x['id'])
            return all_results

        return results
    
    def _process_fallback(
        self,
        results: list[dict],
        paragraphs: list[dict],
        document_name: str
    ) -> list[dict]:
        """
        Process low-confidence items through Flash fallback model.
        
        Args:
            results: Initial classification results
            paragraphs: Original paragraphs with metadata
            document_name: Document name for logging
            
        Returns:
            Updated results with fallback improvements
        """
        # Find low-confidence items
        low_confidence = [
            (i, r) for i, r in enumerate(results) 
            if r.get('confidence', 100) < self.fallback_threshold
        ]
        
        if not low_confidence:
            logger.info("Flash fallback: No low-confidence items to process")
            return results
        
        logger.info(f"Flash fallback: Processing {len(low_confidence)} low-confidence items (threshold: {self.fallback_threshold}%)")
        
        # Build paragraph lookup
        para_by_id = {p['id']: p for p in paragraphs}
        
        # Group items for batch processing (max 30 items per call for focused analysis)
        batch_size = 30
        improved_count = 0
        
        for batch_start in range(0, len(low_confidence), batch_size):
            batch = low_confidence[batch_start:batch_start + batch_size]
            
            # Build focused prompt for these specific items
            fallback_prompt = self._build_fallback_prompt(batch, results, para_by_id, document_name)
            
            try:
                # Call Flash model
                fallback_results = self._call_fallback_model(fallback_prompt, len(batch))
                
                # Merge improved results
                for fb_result in fallback_results:
                    item_id = fb_result.get('id')
                    
                    # Find original result index
                    for orig_idx, orig_result in low_confidence:
                        if results[orig_idx].get('id') == item_id:
                            old_conf = results[orig_idx].get('confidence', 0)
                            new_conf = fb_result.get('confidence', 0)
                            old_tag = results[orig_idx].get('tag', '')
                            new_tag = fb_result.get('tag', '')
                            
                            # Update if fallback has higher confidence or different tag
                            if new_conf > old_conf or new_tag != old_tag:
                                results[orig_idx]['tag'] = new_tag
                                results[orig_idx]['confidence'] = new_conf
                                results[orig_idx]['fallback_used'] = True
                                results[orig_idx]['original_tag'] = old_tag
                                results[orig_idx]['original_confidence'] = old_conf
                                
                                if fb_result.get('reasoning'):
                                    results[orig_idx]['reasoning'] = f"[Flash] {fb_result['reasoning']}"
                                
                                if new_tag != old_tag:
                                    improved_count += 1
                                    logger.debug(f"  Para {item_id}: {old_tag} ({old_conf}%) → {new_tag} ({new_conf}%)")
                            break
                
            except Exception as e:
                logger.warning(f"Flash fallback batch failed: {e}")
                continue
        
        self.fallback_calls += 1
        self.items_improved += improved_count
        
        logger.info(f"Flash fallback complete: {improved_count} items improved out of {len(low_confidence)} processed")
        
        return results
    
    def _build_fallback_prompt(
        self,
        batch: list[tuple],
        results: list[dict],
        para_by_id: dict,
        document_name: str
    ) -> str:
        """Build focused prompt for Flash fallback model."""
        lines = []
        
        for orig_idx, result in batch:
            item_id = result.get('id')
            para = para_by_id.get(item_id, {})
            
            text = para.get('text', '')
            zone = para.get('metadata', {}).get('context_zone', 'BODY')
            current_tag = result.get('tag', 'TXT')
            current_conf = result.get('confidence', 0)
            reasoning = result.get('reasoning', '')
            
            # Get context (previous and next paragraphs)
            prev_result = results[orig_idx - 1] if orig_idx > 0 else None
            next_result = results[orig_idx + 1] if orig_idx < len(results) - 1 else None
            
            context_info = ""
            if prev_result:
                context_info += f"BEFORE: [{prev_result.get('tag')}] "
            if next_result:
                context_info += f"AFTER: [{next_result.get('tag')}]"
            
            # Build item entry
            lines.append(f"""
[ID: {item_id}]
Zone: {zone}
Current: {current_tag} ({current_conf}%)
{f'Reason: {reasoning}' if reasoning else ''}
{f'Context: {context_info}' if context_info else ''}
Text: {text}
""")
        
        prompt = f"""Document: {document_name}

The following {len(batch)} paragraphs received LOW CONFIDENCE scores from the primary classifier.
Please re-analyze each and provide your best classification.

Focus on:
1. Zone constraints (style must match the zone)
2. Context from neighboring paragraphs
3. Text patterns (bullets, numbers, headings, etc.)

---
{''.join(lines)}
---

Return a JSON array with your classifications for all {len(batch)} items:
[{{"id": ID, "tag": "STYLE", "confidence": 85-99, "reasoning": "brief reason"}}]"""
        
        return prompt
    
    def _call_fallback_model(self, prompt: str, expected_count: int) -> list[dict]:
        """Call the Flash fallback model."""
        logger.debug(f"Calling Flash fallback model for {expected_count} items")

        response = self.fallback_model.generate_content(prompt, timeout=60)

        # Track fallback token usage (accumulate across calls)
        last_usage = self.fallback_model.get_last_usage()
        if last_usage:
            input_tokens = last_usage.get('input_tokens', 0)
            output_tokens = last_usage.get('output_tokens', 0)
            self.fallback_input_tokens += input_tokens
            self.fallback_output_tokens += output_tokens
            logger.debug(f"Flash fallback tokens - Input: {input_tokens}, Output: {output_tokens}")

        # Parse response
        results = self._parse_json_response(response.text, expected_count)
        return results

    def _generate_content(self, prompt: str):
        """
        Wrapper for model generation (allows test mocking).
        """
        return self.model.generate_content(prompt, timeout=self.api_timeout)

    def _find_invalid_tags(
        self,
        results: list[dict],
        meta_by_id: dict | None = None,
        text_by_id: dict | None = None
    ) -> set[str]:
        invalid = set()
        for r in results:
            rid = r.get("id")
            meta = meta_by_id.get(rid) if meta_by_id else None
            text = text_by_id.get(rid, "") if text_by_id else ""
            tag = self._map_tag_alias(r.get("tag", ""), meta=meta, text=text)
            if tag and tag not in VALID_TAGS:
                invalid.add(tag)
        return invalid

    def _force_invalid_to_txt(
        self,
        results: list[dict],
        meta_by_id: dict | None = None,
        text_by_id: dict | None = None
    ) -> list[dict]:
        """
        Normalize and validate tags using normalize_tag() with membership enforcement.
        Falls back to grounded retrieval if normalize_tag() returns a generic fallback.
        """
        for r in results:
            rid = r.get("id")
            meta = meta_by_id.get(rid) if meta_by_id else None
            text = text_by_id.get(rid, "") if text_by_id else ""
            raw_tag = r.get("tag", "")

            # First, apply basic alias mapping
            mapped_tag = self._map_tag_alias(raw_tag, meta=meta, text=text)

            # Then, apply normalize_tag() which enforces membership in allowed_styles.json
            normalized_tag = normalize_tag(mapped_tag, meta=meta)

            # If normalize_tag() returned a generic fallback (TXT) and we have grounded retrieval,
            # try to find a better match from ground truth
            if normalized_tag in {"TXT", "TXT-FLUSH"} and self.retriever and text and mapped_tag not in VALID_TAGS:
                try:
                    # Retrieve most similar example from ground truth
                    zone = (meta or {}).get("context_zone", "BODY")
                    similar = self.retriever.retrieve_examples(
                        text=text,
                        k=1,  # Get top-1 most similar
                        zone=zone
                    )

                    if similar and similar[0].get('similarity_score', 0) > 0.7:
                        grounded_tag = similar[0].get("canonical_gold_tag", "TXT")
                        # Validate grounded tag is in allowed_styles
                        validated_grounded = normalize_tag(grounded_tag, meta=meta)
                        if validated_grounded != "TXT" or grounded_tag == "TXT":
                            normalized_tag = validated_grounded
                            logger.debug(f"Invalid tag '{raw_tag}' -> grounded fallback '{normalized_tag}' (similarity: {similar[0].get('similarity_score', 0):.3f})")
                except Exception as e:
                    logger.warning(f"Grounded fallback failed: {e}")

            # Update tag with normalized/validated version
            if normalized_tag != raw_tag:
                r["tag"] = normalized_tag
                r["confidence"] = min(int(r.get("confidence", 50)), 60)
                r["reasoning"] = f"Normalized '{raw_tag}' -> '{normalized_tag}'"
            else:
                r["tag"] = normalized_tag

        return results
    
    def _classify_chunk(
        self,
        paragraphs: list[dict],
        document_name: str,
        document_type: str,
        chunk_info: str = ""
    ) -> list[dict]:
        """
        Classify a chunk of paragraphs.
        Retries are handled by GeminiClient internally.
        """
        user_prompt = self.build_user_prompt(paragraphs, document_name, document_type, chunk_info)

        logger.info(f"Sending {len(paragraphs)} paragraphs to Gemini API")

        # Make API call (retries handled internally by GeminiClient)
        response = self._generate_content(user_prompt)
        logger.info("Received response from Gemini API")

        # Log token usage (tracked by GeminiClient)
        last_usage = self.model.get_last_usage()
        total_usage = self.model.get_token_usage()

        if last_usage:
            logger.info(
                f"Token Usage - Input: {last_usage['input_tokens']:,}, "
                f"Output: {last_usage['output_tokens']:,}, "
                f"Total: {last_usage['total_tokens']:,}"
            )
            logger.info(
                f"Cumulative Tokens - Input: {total_usage['total_input_tokens']:,}, "
                f"Output: {total_usage['total_output_tokens']:,}, "
                f"Total: {total_usage['total_tokens']:,}"
            )
        else:
            logger.warning("Token usage metadata not available in response")

        # Parse JSON response with robust handling
        results = self._parse_json_response(response.text, len(paragraphs))
        meta_by_id = {p.get("id"): p.get("metadata", {}) for p in paragraphs}
        text_by_id = {p.get("id"): p.get("text", "") for p in paragraphs}
        results = self._apply_alias_mappings(results, meta_by_id=meta_by_id, text_by_id=text_by_id)

        # Self-heal if invalid tags detected
        invalid = self._find_invalid_tags(results, meta_by_id, text_by_id)
        if invalid:
            logger.warning(f"Invalid tags detected: {sorted(invalid)}. Retrying once with correction.")
            correction_prompt = (
                user_prompt
                + "\n\nINVALID TAGS FOUND: "
                + ", ".join(sorted(invalid))
                + "\nReturn corrected JSON using ONLY allowed tags."
            )
            response = self._generate_content(correction_prompt)
            results = self._parse_json_response(response.text, len(paragraphs))
            results = self._apply_alias_mappings(results, meta_by_id=meta_by_id, text_by_id=text_by_id)
            invalid = self._find_invalid_tags(results, meta_by_id, text_by_id)
            if invalid:
                logger.warning(f"Invalid tags persist after retry: {sorted(invalid)}. Using grounded fallback.")
                results = self._force_invalid_to_txt(results, meta_by_id, text_by_id)

        # Validate results for this chunk
        validated = self._validate_results(results, len(paragraphs), paragraphs[0]['id'])

        # Ensure no invalid tags remain after validation
        for r in validated:
            meta = meta_by_id.get(r.get("id")) if meta_by_id else None
            text = text_by_id.get(r.get("id"), "") if text_by_id else ""
            tag = self._map_tag_alias(r.get("tag", ""), meta=meta, text=text)
            if tag and tag not in VALID_TAGS:
                r["tag"] = "TXT"
                r["confidence"] = min(int(r.get("confidence", 50)), 50)
                r["reasoning"] = f"Invalid tag '{tag}' downgraded to TXT"
            else:
                r["tag"] = tag

        logger.info(f"Classified {len(validated)} paragraphs")
        return validated
    
    def _parse_json_response(self, response_text: str, expected_count: int) -> list[dict]:
        """
        Parse JSON response with multiple fallback strategies.
        """
        # Strategy 1: Direct parse
        try:
            results = json.loads(response_text)
            if isinstance(results, list):
                return results
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract JSON array from text
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                results = json.loads(json_match.group())
                if isinstance(results, list):
                    return results
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Fix truncated JSON
        try:
            fixed = self._fix_truncated_json(response_text)
            results = json.loads(fixed)
            if isinstance(results, list):
                logger.warning(f"Fixed truncated JSON, got {len(results)} items")
                return results
        except json.JSONDecodeError:
            pass
        
        # Strategy 4: Parse individual objects
        try:
            results = self._parse_individual_objects(response_text)
            if results:
                logger.warning(f"Parsed {len(results)} individual objects from malformed JSON")
                return results
        except Exception:
            pass
        
        # All strategies failed
        logger.error(f"Failed to parse JSON response: {response_text[:500]}...")
        raise ValueError(f"Failed to parse response as JSON after all strategies")
    
    def _fix_truncated_json(self, text: str) -> str:
        """
        Attempt to fix truncated JSON array.
        """
        # Remove any markdown code fences
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        
        # Ensure it starts with [
        if not text.startswith('['):
            start = text.find('[')
            if start != -1:
                text = text[start:]
            else:
                return '[]'
        
        # If it doesn't end with ], try to fix
        if not text.rstrip().endswith(']'):
            # Find the last complete object
            last_complete = text.rfind('},')
            if last_complete != -1:
                text = text[:last_complete + 1] + ']'
            else:
                # Try to find last }
                last_brace = text.rfind('}')
                if last_brace != -1:
                    text = text[:last_brace + 1] + ']'
                else:
                    return '[]'
        
        return text
    
    def _parse_individual_objects(self, text: str) -> list[dict]:
        """
        Parse individual JSON objects from malformed response.
        """
        results = []
        
        # Find all JSON-like objects
        pattern = r'\{\s*"id"\s*:\s*(\d+)\s*,\s*"tag"\s*:\s*"([^"]+)"\s*,\s*"confidence"\s*:\s*(\d+)'
        
        for match in re.finditer(pattern, text):
            results.append({
                "id": int(match.group(1)),
                "tag": match.group(2),
                "confidence": int(match.group(3))
            })
        
        return results
    
    def _validate_results(
        self, 
        results: list[dict], 
        expected_count: int,
        start_id: int = 1
    ) -> list[dict]:
        """
        Validate and clean classification results.
        """
        validated = []
        
        # Comprehensive style mapping from common source formats to WK Template
        STYLE_MAP = {
            # Chapter openers
            "CHAPTERNUMBER": "CN", "CHAPTER NUMBER": "CN", "CHAP-NUM": "CN",
            "CHAPTERTITLE": "CT", "CHAPTER TITLE": "CT", "CHAP-TITLE": "CT",
            "CHAPTERAUTHOR": "CAU", "CHAPTER AUTHOR": "CAU",
            "CHAPTERTITLEFOOTNOTE": "TFN",
            
            # Headings - various source formats
            "HEAD1": "H1", "HEAD-1": "H1", "HEADING1": "H1", "HEADING 1": "H1",
            "HEAD2": "H2", "HEAD-2": "H2", "HEADING2": "H2", "HEADING 2": "H2",
            "HEAD3": "H3", "HEAD-3": "H3", "HEADING3": "H3", "HEADING 3": "H3",
            "HEAD4": "H4", "HEAD-4": "H4", "HEADING4": "H4", "HEADING 4": "H4",
            "HEAD5": "H5", "HEAD-5": "H5", "HEADING5": "H5", "HEADING 5": "H5",
            "BHEAD AFTER HEAD": "H2",
            "SPECIALHEADING2": "H2",
            
            # Body text variations
            "PARA-FL": "TXT-FLUSH", "PARAFL": "TXT-FLUSH", "PARA FL": "TXT-FLUSH",
            "PARAFIRSTLINE-IND": "TXT", "PARA-FIRSTLINE-IND": "TXT",
            "TX": "TXT", "TXFL": "TXT-FLUSH", "TXL": "TXT",
            "BODYTEXT": "TXT", "BODY TEXT": "TXT", "BODY-TEXT": "TXT",
            "PARAGRAPH": "TXT", "PARA": "TXT", "TEXT": "TXT",
            
            # Lists - unordered/bullet
            "UC-ALPHATLIST1": "UL-FIRST", "UC-ALPHALIST1": "UL-MID",
            "BULLETLIST1": "BL-MID", "BULLET LIST 1": "BL-MID",
            "BULLETLIST1_FIRST": "BL-FIRST", "BULLETLIST1_LAST": "BL-LAST",
            "BULLETLIST2": "BL2-MID",
            "LC-ALPHALIST3": "UL-MID", "LC-ROMANLIST4": "UL-MID",
            
            # Lists - numbered
            "NUMBERLIST1": "NL-MID", "NUMBER LIST 1": "NL-MID",
            "NUMBERLIST2": "NL-MID", "NUMBER LIST 2": "NL-MID",
            
            # References
            "REFERENCE-ALPHABETICAL": "REF-N", "REFERENCEALPHABETICAL": "REF-N",
            "REFERENCE-NUMBERED": "REF-N", "REFERENCENUMBERED": "REF-N",
            "REF-U": "REF-N", "EOC_REF": "REF-N",
            
            # Figures and tables
            "FIGURELEGEND": "FIG-LEG", "FIGURE LEGEND": "FIG-LEG",
            "FIGURECAPTION": "FIG-LEG", "FIGURE CAPTION": "FIG-LEG",
            "FIGURESOURCE": "TSN", "FIG-SRC": "TSN", "UNFIG-SRC": "TSN",
            "TABLECAPTION": "T1", "TABLE CAPTION": "T1", "TABLECAPTIONS": "PMI",
            "TABLEFOOTNOTE": "TFN", "TABLE FOOTNOTE": "TFN",
            "UNT-T1": "T1",  # Unnumbered table title
            "TABLETITLE": "T1", "TABLE TITLE": "T1",
            "TABLEHEADER": "T2", "TABLE HEADER": "T2",
            "TABLEBODY": "T", "TABLE BODY": "T",
            "TABLESOURCE": "TSN", "TABLE SOURCE": "TSN",
            "TABLECELL": "T", "TABLE CELL": "T",
            # Table cell content styles from training data
            "GT": "T",  # Generic table cell
            "UNT": "T",  # Unnumbered table text
            "UNT-T2": "T2",  # Unnumbered table header
            "UNT-BL-MID": "TBL-MID",  # Unnumbered table bullet
            "TABLECOLUMNHEAD1": "T2",  # Table column header
            
            # Box/special content - NBX styles (keep in NBX format)
            "NBX-BL-MID": "NBX-BL-MID", "NBX-BL-FIRST": "NBX-BL-FIRST", "NBX-BL-LAST": "NBX-BL-LAST",
            "NBX-H1": "H1", "NBX-H2": "H2",
            "NBX-UL-MID": "NBX-UL-MID", "NBX-UL-FIRST": "NBX-UL-FIRST", "NBX-UL-LAST": "NBX-UL-LAST",
            "BOX-01-BULLETLIST1": "BX1-BL-MID",
            
            # Box type mappings
            "NOTE": "NBX-TTL", "CLINICAL PEARL": "BX1-TTL", "RED FLAG": "BX2-TTL",
            "TIP": "BX1-TTL", "WARNING": "BX2-TTL", "ALERT": "BX2-TTL",
            
            # Source/citation mappings
            "CITATION": "TSN", "SOURCE": "TSN", "FIG-SRC": "TSN",
            
            # Case study and special
            "CASESTUDY-DIALOGUE": "TXT", "CASESTUDY-UL-FL1": "UL-FIRST",
            
            # End of chapter
            "EOC_NL": "EOC-NL-MID", "EOC_NLLL": "EOC-NL-MID",
            "EOC-NUMBERLIST1": "EOC-NL-MID", "EOC-BULLETLIST2": "EOC-NL-MID",
            "EOC-PARA-FL": "TXT-FLUSH",
            
            # Metadata/instructions and markers
            "METADATA": "PMI", "<METADATA>": "PMI", "</METADATA>": "PMI",
            "<NOTE>": "PMI", "</NOTE>": "PMI",
            "<CLINICAL PEARL>": "PMI", "</CLINICAL PEARL>": "PMI",
            "<RED FLAG>": "PMI", "</RED FLAG>": "PMI",
            "<BOX>": "PMI", "</BOX>": "PMI",
            "<TIP>": "PMI", "</TIP>": "PMI",
            
            # Normal/default
            "NORMAL": "TXT", "DEFAULT": "TXT", "STANDARD": "TXT",
        }
        
        for result in results:
            # Ensure required fields
            if "id" not in result or "tag" not in result:
                continue
            
            # Validate tag
            tag = result["tag"]
            original_tag = tag
            
            if normalize_style(tag) not in VALID_TAGS:
                tag = self._map_tag_alias(tag)
            if normalize_style(tag) not in VALID_TAGS:
                # Try uppercase
                tag_upper = tag.upper().replace(" ", "").replace("_", "-")
                if normalize_style(tag_upper) in VALID_TAGS:
                    tag = tag_upper
                else:
                    # Check style map
                    tag_lookup = tag.upper().replace("-", " ").replace("_", " ")
                    tag_lookup_dash = tag.upper().replace(" ", "-").replace("_", "-")
                    
                    if tag_lookup in STYLE_MAP:
                        tag = STYLE_MAP[tag_lookup]
                    elif tag_lookup_dash in STYLE_MAP:
                        tag = STYLE_MAP[tag_lookup_dash]
                    elif tag.upper() in STYLE_MAP:
                        tag = STYLE_MAP[tag.upper()]
                    else:
                        # Try common underscore fixes
                        tag_fixes = {
                            "TXT_FLUSH": "TXT-FLUSH",
                            "BL_FIRST": "BL-FIRST",
                            "BL_MID": "BL-MID",
                            "BL_LAST": "BL-LAST",
                            "NL_FIRST": "NL-FIRST",
                            "NL_MID": "NL-MID",
                            "NL_LAST": "NL-LAST",
                            "UL_FIRST": "UL-FIRST",
                            "UL_MID": "UL-MID",
                            "UL_LAST": "UL-LAST",
                        }
                        tag = tag_fixes.get(tag.upper(), "TXT")
                        result["confidence"] = min(result.get("confidence", 50), 50)
                        result["reasoning"] = f"Unknown tag '{original_tag}' mapped to {tag}"
            
            validated.append({
                "id": result["id"],
                "tag": tag,
                "confidence": result.get("confidence", 85),
                "reasoning": result.get("reasoning")
            })
        
        # Check for missing paragraphs
        found_ids = {r["id"] for r in validated}
        end_id = start_id + expected_count
        
        for i in range(start_id, end_id):
            if i not in found_ids:
                validated.append({
                    "id": i,
                    "tag": "TXT",
                    "confidence": 0,
                    "reasoning": "Missing from API response"
                })
        
        # Sort by ID
        validated.sort(key=lambda x: x["id"])
        
        return validated
    
    def validate_zone_constraints(
        self,
        results: list[dict],
        paragraphs: list[dict]
    ) -> list[dict]:
        """
        Post-validate classification results against zone constraints.
        Flags zone violations with reduced confidence for editor review.
        
        Args:
            results: Classification results from AI
            paragraphs: Original paragraphs with zone metadata
            
        Returns:
            Results with zone violation flags added
        """
        # from .ingestion import validate_style_for_zone, ZONE_VALID_STYLES  <-- REMOVED per zone constraints plan

        
        # Build paragraph lookup by ID
        para_by_id = {p['id']: p for p in paragraphs}
        
        for result in results:
            para_id = result.get('id')
            para = para_by_id.get(para_id)
            
            if not para:
                continue
            
            zone = para.get('metadata', {}).get('context_zone', 'BODY')
            style = result.get('tag', '')
            text = para.get('text', '')
            meta = para.get('metadata', {})
            
            # Skip BODY zone (no restrictions)
            if zone == 'BODY':
                continue
            
            # Check if style is valid for zone
            if not validate_style_for_zone(style, zone):
                # First try alias remap with zone/text context.
                remapped = self._map_tag_alias(style, meta=meta, text=text)
                if remapped and validate_style_for_zone(remapped, zone):
                    result['tag'] = remapped
                    continue

                # Deterministic zone fallback to reduce noisy invalid outputs.
                fallback = None
                if zone == 'TABLE':
                    text_lower = (text or "").strip().lower()
                    if text_lower.startswith(("note", "source")):
                        fallback = "TFN"
                    elif bool(REF_BULLET_RE.match((text or "").strip())):
                        fallback = "TBL-MID"
                    elif bool(REF_NUMBER_RE.match((text or "").strip())):
                        fallback = "TNL-MID"
                    else:
                        fallback = "T"
                elif zone == 'BACK_MATTER':
                    fallback = "REF-U" if bool(REF_BULLET_RE.match((text or "").strip())) else "REF-N"
                elif zone == 'METADATA':
                    fallback = "PMI"
                else:
                    fallback = "TXT"

                if fallback and validate_style_for_zone(fallback, zone):
                    result['tag'] = fallback
                    original_confidence = result.get('confidence', 85)
                    result['confidence'] = min(original_confidence, 70)
                    continue

                # Flag as zone violation
                result['zone_violation'] = True
                result['expected_zone'] = zone
                
                # Get expected styles for this zone
                expected = ZONE_STYLE_CONSTRAINTS.get(zone, [])
                if expected:
                    # Suggest first few valid styles
                    suggestions = expected[:5]
                    result['zone_suggestions'] = suggestions
                
                # Reduce confidence to flag for review
                original_confidence = result.get('confidence', 85)
                result['confidence'] = min(original_confidence, 60)
                
                # Add reasoning
                existing_reason = result.get('reasoning', '')
                zone_reason = f"Zone violation: '{style}' not valid for {zone}"
                if existing_reason:
                    result['reasoning'] = f"{existing_reason}; {zone_reason}"
                else:
                    result['reasoning'] = zone_reason
        
        return results
    
    def get_token_usage(self) -> dict:
        """
        Get token usage statistics including fallback model.

        Returns:
            Dict with token usage details for primary and fallback models
        """
        # Get token usage from primary model client
        primary_usage = self.model.get_token_usage()

        # Get fallback model usage if enabled
        fallback_usage = {}
        if self.enable_fallback and self.fallback_model:
            fallback_usage = {
                'input_tokens': self.fallback_input_tokens,
                'output_tokens': self.fallback_output_tokens,
            }

        return {
            # Primary model usage
            'input_tokens': primary_usage['total_input_tokens'],
            'output_tokens': primary_usage['total_output_tokens'],
            'total_tokens': primary_usage['total_tokens'],
            'last_call': self.model.get_last_usage(),
            # Fallback model usage
            'fallback': {
                'enabled': self.enable_fallback,
                'model': self.fallback_model_name if self.enable_fallback else None,
                'threshold': self.fallback_threshold,
                'calls': self.fallback_calls,
                'items_improved': self.items_improved,
                'input_tokens': fallback_usage.get('input_tokens', 0),
                'output_tokens': fallback_usage.get('output_tokens', 0),
            },
            # Rule-based prediction statistics
            'rule_based': {
                'predictions': self.rule_predictions,
                'llm_predictions': self.llm_predictions,
                'total_predictions': self.rule_predictions + self.llm_predictions,
                'rule_coverage': (
                    self.rule_predictions / (self.rule_predictions + self.llm_predictions)
                    if (self.rule_predictions + self.llm_predictions) > 0
                    else 0.0
                ),
            },
            # Combined totals
            'combined_input_tokens': primary_usage['total_input_tokens'] + fallback_usage.get('input_tokens', 0),
            'combined_output_tokens': primary_usage['total_output_tokens'] + fallback_usage.get('output_tokens', 0),
        }


def classify_document(
    paragraphs: list[dict],
    document_name: str,
    api_key: str,
    document_type: str = "Academic Document",
    enable_fallback: bool = True,
    fallback_threshold: int = FLASH_FALLBACK_THRESHOLD
) -> tuple[list[dict], dict]:
    """
    Convenience function to classify a document with hybrid model support.
    
    Args:
        paragraphs: List of paragraph dicts
        document_name: Source document name
        api_key: Google AI API key
        document_type: Type of document
        enable_fallback: Whether to use Flash fallback for low-confidence items
        fallback_threshold: Confidence threshold for fallback (default: 75%)
        
    Returns:
        Tuple of (classification results, token usage dict)
    """
    classifier = GeminiClassifier(
        api_key, 
        enable_fallback=enable_fallback,
        fallback_threshold=fallback_threshold
    )
    results = classifier.classify(paragraphs, document_name, document_type)
    token_usage = classifier.get_token_usage()
    return results, token_usage


def classify_blocks(
    blocks: list[dict],
    document_name: str,
    api_key: str,
    document_type: str = "Academic Document",
    enable_fallback: bool = True,
    fallback_threshold: int = FLASH_FALLBACK_THRESHOLD
) -> tuple[list[dict], dict]:
    """
    Classify extracted blocks (block-level input).
    Blocks use the same schema as paragraphs with added metadata.
    """
    classifier = GeminiClassifier(
        api_key,
        enable_fallback=enable_fallback,
        fallback_threshold=fallback_threshold
    )
    results = classifier.classify(blocks, document_name, document_type)
    token_usage = classifier.get_token_usage()
    return results, token_usage


def classify_blocks_with_prompt(
    blocks: list[dict],
    document_name: str,
    api_key: str,
    document_type: str = "Academic Document",
    enable_fallback: bool = True,
    fallback_threshold: int = FLASH_FALLBACK_THRESHOLD,
    model_name: str | None = None,
    system_prompt_override: str | None = None,
    fallback_prompt_override: str | None = None,
) -> tuple[list[dict], dict]:
    """
    Classify extracted blocks using a prompt override and/or model override.
    """
    classifier = GeminiClassifier(
        api_key,
        model_name=model_name or "gemini-2.5-flash-lite",
        enable_fallback=enable_fallback,
        fallback_threshold=fallback_threshold,
        system_prompt_override=system_prompt_override,
        fallback_prompt_override=fallback_prompt_override,
    )
    results = classifier.classify(blocks, document_name, document_type)
    token_usage = classifier.get_token_usage()
    return results, token_usage


if __name__ == "__main__":
    import os
    
    # Test with sample data
    API_KEY = os.environ.get("GOOGLE_API_KEY", "")
    
    if not API_KEY:
        print("Set GOOGLE_API_KEY environment variable")
    else:
        sample = [
            {"id": 1, "text": "CHAPTER 1"},
            {"id": 2, "text": "Introduction to Exercise Science"},
            {"id": 3, "text": "OBJECTIVES"},
            {"id": 4, "text": "After reading this chapter, you should be able to:"},
            {"id": 5, "text": "• Define exercise science"},
            {"id": 6, "text": "• Describe career opportunities"},
        ]
        
        results = classify_document(sample, "test.docx", API_KEY)
        print(json.dumps(results, indent=2))
