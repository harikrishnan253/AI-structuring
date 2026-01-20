"""
STAGE 4: Document Reconstruction
- Style Applicator (applies Word paragraph styles)
- DOCX Builder
- Review Report Generator

Applies proper Word styles to paragraphs for professional output.
NO CONTENT MODIFICATION - only styles and formatting are applied.
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Style definitions with formatting properties - extracted from tagged documents
# Note: Text flow variants (TXT1, TXT2, H11, H12, etc.) inherit from base styles
STYLE_DEFINITIONS = {
    # Document Structure
    "CN": {"font_size": 24, "bold": True, "alignment": "center", "space_after": 6},
    "CT": {"font_size": 28, "bold": True, "alignment": "center", "space_after": 12},
    "CAU": {"font_size": 10, "italic": True, "alignment": "center", "space_after": 6},
    "PN": {"font_size": 10, "alignment": "center"},
    "PT": {"font_size": 14, "bold": True, "alignment": "center"},
    
    # Headings
    "H1": {"font_size": 16, "bold": True, "space_before": 12, "space_after": 6},
    "H2": {"font_size": 14, "bold": True, "space_before": 10, "space_after": 4},
    "H3": {"font_size": 12, "bold": True, "space_before": 8, "space_after": 4},
    "H4": {"font_size": 11, "bold": True, "space_before": 6, "space_after": 2},
    "H5": {"font_size": 11, "bold": True, "italic": True, "space_before": 6, "space_after": 2},
    "H6": {"font_size": 10, "bold": True, "space_before": 4, "space_after": 2},
    "SP-H1": {"font_size": 14, "bold": True, "caps": True, "space_before": 12, "space_after": 6},
    "EOC-H1": {"font_size": 14, "bold": True, "space_before": 12, "space_after": 6},
    # Heading text flow variants
    "H11": {"font_size": 16, "bold": True, "space_before": 12, "space_after": 6},
    "H12": {"font_size": 16, "bold": True, "space_before": 12, "space_after": 6},
    "H21": {"font_size": 14, "bold": True, "space_before": 10, "space_after": 4},
    
    # Reference Headings
    "REFH1": {"font_size": 14, "bold": True, "space_before": 12, "space_after": 6},
    "REFH2": {"font_size": 12, "bold": True, "space_before": 8, "space_after": 4},
    "REFH2a": {"font_size": 12, "bold": True, "space_before": 8, "space_after": 4},
    "Ref-H1": {"font_size": 14, "bold": True, "space_before": 12, "space_after": 6},
    "Ref-H2": {"font_size": 12, "bold": True, "space_before": 8, "space_after": 4},
    
    # Body Text
    "TXT": {"font_size": 11, "first_line_indent": 0.5, "space_after": 6},
    "TXT-FLUSH": {"font_size": 11, "space_after": 6},
    "TXT-DC": {"font_size": 11, "space_after": 6},  # Drop cap would need special handling
    "TXT-AU": {"font_size": 10, "italic": True, "space_after": 6},
    "T": {"font_size": 10, "space_after": 2},  # Table cell body text
    # Body text flow variants
    "TXT1": {"font_size": 11, "first_line_indent": 0.5, "space_after": 6},
    "TXT2": {"font_size": 11, "first_line_indent": 0.5, "space_after": 6},
    "TXT3": {"font_size": 11, "first_line_indent": 0.5, "space_after": 6},
    "TXT4": {"font_size": 11, "first_line_indent": 0.5, "space_after": 6},
    "TXT-FLUSH1": {"font_size": 11, "space_after": 6},
    "TXT-FLUSH2": {"font_size": 11, "space_after": 6},
    "TXT-FLUSH4": {"font_size": 11, "space_after": 6},
    
    # Bulleted Lists
    "BL-FIRST": {"font_size": 11, "left_indent": 0.5, "space_after": 2, "bullet": True},
    "BL-MID": {"font_size": 11, "left_indent": 0.5, "space_after": 2, "bullet": True},
    "BL-LAST": {"font_size": 11, "left_indent": 0.5, "space_after": 6, "bullet": True},
    "UL-FIRST": {"font_size": 11, "left_indent": 0.75, "space_after": 2, "bullet": True},
    "UL-MID": {"font_size": 11, "left_indent": 0.75, "space_after": 2, "bullet": True},
    "UL-LAST": {"font_size": 11, "left_indent": 0.75, "space_after": 6, "bullet": True},
    
    # Numbered Lists
    "NL-FIRST": {"font_size": 11, "left_indent": 0.5, "space_after": 2, "numbered": True},
    "NL-MID": {"font_size": 11, "left_indent": 0.5, "space_after": 2, "numbered": True},
    "NL-LAST": {"font_size": 11, "left_indent": 0.5, "space_after": 6, "numbered": True},
    
    # End of Chapter Lists
    "EOC-NL-FIRST": {"font_size": 11, "left_indent": 0.5, "space_after": 2, "numbered": True},
    "EOC-NL-MID": {"font_size": 11, "left_indent": 0.5, "space_after": 2, "numbered": True},
    "EOC-NL-LAST": {"font_size": 11, "left_indent": 0.5, "space_after": 6, "numbered": True},
    "EOC-LL2-MID": {"font_size": 11, "left_indent": 0.75, "space_after": 2},
    
    # Tables - Titles
    "T1": {"font_size": 10, "bold": True, "space_before": 6, "space_after": 2},
    "T11": {"font_size": 10, "bold": True, "space_before": 6, "space_after": 2},
    "T12": {"font_size": 10, "bold": True, "space_before": 6, "space_after": 2},
    
    # Tables - Headers
    "T2": {"font_size": 10, "bold": True, "alignment": "center"},
    "T2-C": {"font_size": 10, "bold": True, "alignment": "center"},
    "T21": {"font_size": 10, "bold": True},  # Category/row headers
    "T22": {"font_size": 10, "bold": True, "alignment": "center"},  # Column headers
    "T23": {"font_size": 10, "bold": True, "alignment": "center"},  # Specific headers
    
    # Tables - Body Cells
    "T3": {"font_size": 10, "bold": True},  # Row header/subhead
    "T5": {"font_size": 10},  # Table body cell (data values)
    "T6": {"font_size": 10},  # Table body cell variant
    
    # Tables - Lists inside cells
    "TBL-FIRST": {"font_size": 10, "left_indent": 0.25, "space_after": 2, "bullet": True},
    "TBL-MID": {"font_size": 10, "left_indent": 0.25, "bullet": True},
    "TBL-MID0": {"font_size": 10, "left_indent": 0.25, "bullet": True},
    "TBL-LAST": {"font_size": 10, "left_indent": 0.25, "space_after": 4, "bullet": True},
    "TBL-LAST1": {"font_size": 10, "left_indent": 0.25, "space_after": 4, "bullet": True},
    "TBL2-MID": {"font_size": 10, "left_indent": 0.5, "bullet": True},
    "TBL3-MID": {"font_size": 10, "left_indent": 0.75, "bullet": True},
    "TBL4-MID": {"font_size": 10, "left_indent": 1.0, "bullet": True},
    "TUL-MID": {"font_size": 10, "left_indent": 0.25, "bullet": True},
    
    # Tables - Footnotes
    "TFN": {"font_size": 9, "italic": True, "space_before": 2},
    "TFN1": {"font_size": 9, "italic": True, "space_before": 2},
    "TSN": {"font_size": 9, "space_before": 2},
    
    # Figures
    "FIG-LEG": {"font_size": 10, "space_before": 6, "space_after": 6},
    "PMI": {"font_size": 9, "italic": True},
    
    # References
    "REF-N": {"font_size": 10, "hanging_indent": 0.5, "space_after": 2},
    "REF-N0": {"font_size": 10, "hanging_indent": 0.5, "space_after": 2},
    
    # Chapter Outline
    "COUT-1": {"font_size": 11, "left_indent": 0.25, "space_after": 2},
    "COUT-2": {"font_size": 11, "left_indent": 0.5, "space_after": 2},
    
    # Equations
    "EQ-ONLY": {"font_size": 11, "alignment": "center", "space_before": 6, "space_after": 6},
    "EQ-MID": {"font_size": 11, "alignment": "center", "space_after": 4},  # Multi-line equation continuation
    
    # Appendix Styles
    "APX-TYPE": {"font_size": 12, "bold": True, "caps": True, "space_before": 12, "space_after": 4},
    "APX-TTL": {"font_size": 14, "bold": True, "space_after": 6},
    "APX-H1": {"font_size": 16, "bold": True, "space_before": 12, "space_after": 6},
    "APX-H2": {"font_size": 14, "bold": True, "space_before": 10, "space_after": 4},
    "APX-H3": {"font_size": 12, "bold": True, "space_before": 8, "space_after": 4},
    "APX-TXT": {"font_size": 11, "first_line_indent": 0.5, "space_after": 6},
    "APX-TXT-FLUSH": {"font_size": 11, "space_after": 6},
    "APX-CAU": {"font_size": 10, "italic": True, "space_after": 6},
    "APX-REF-N": {"font_size": 10, "hanging_indent": 0.5, "space_after": 2},
    "APX-REFH1": {"font_size": 14, "bold": True, "space_before": 12, "space_after": 6},
    
    # Box Content
    "NBX1-TTL": {"font_size": 12, "bold": True, "space_after": 4},
    "NBX1-TXT": {"font_size": 10, "first_line_indent": 0.25, "space_after": 4},
    "NBX1-TXT-FLUSH": {"font_size": 10, "space_after": 4},
    "NBX1-BL-FIRST": {"font_size": 10, "left_indent": 0.5, "space_after": 2, "bullet": True},
    "NBX1-BL-MID": {"font_size": 10, "left_indent": 0.5, "space_after": 2, "bullet": True},
    "NBX1-BL-LAST": {"font_size": 10, "left_indent": 0.5, "space_after": 4, "bullet": True},
    "NBX1-BL2-MID": {"font_size": 10, "left_indent": 0.75, "space_after": 2, "bullet": True},
    "NBX1-NL-FIRST": {"font_size": 10, "left_indent": 0.5, "space_after": 2, "numbered": True},
    "NBX1-NL-MID": {"font_size": 10, "left_indent": 0.5, "space_after": 2, "numbered": True},
    "NBX1-NL-LAST": {"font_size": 10, "left_indent": 0.5, "space_after": 4, "numbered": True},
    "NBX1-DIA-FIRST": {"font_size": 10, "left_indent": 0.5, "space_after": 2},
    "NBX1-DIA-MID": {"font_size": 10, "left_indent": 0.5, "space_after": 2},
    "NBX1-DIA-LAST": {"font_size": 10, "left_indent": 0.5, "space_after": 4},
    "NBX1-UNT": {"font_size": 10, "space_after": 4},
    "NBX1-UNT-T2": {"font_size": 10, "bold": True, "space_after": 2},
    "NBX1-SRC": {"font_size": 9, "italic": True, "space_after": 4},
    "BX1-TXT-FIRST": {"font_size": 10, "space_after": 4},
    
    # Case Studies
    "CS-H1": {"font_size": 14, "bold": True, "space_before": 10, "space_after": 4},
    "CS-TTL": {"font_size": 12, "bold": True, "space_after": 4},
    "CS-TXT": {"font_size": 10, "first_line_indent": 0.25, "space_after": 4},
    "CS-TXT-FLUSH": {"font_size": 10, "space_after": 4},
    "CS-QUES-TXT": {"font_size": 10, "bold": True, "space_after": 2},
    "CS-ANS-TXT": {"font_size": 10, "space_after": 4},
    
    # Learning Objectives
    "OBJ1": {"font_size": 12, "bold": True, "space_after": 4},
    "OBJ-TXT": {"font_size": 10, "space_after": 4},
    "OBJ-BL-FIRST": {"font_size": 10, "left_indent": 0.5, "space_after": 2, "bullet": True},
    "OBJ-BL-MID": {"font_size": 10, "left_indent": 0.5, "space_after": 2, "bullet": True},
    "OBJ-BL-LAST": {"font_size": 10, "left_indent": 0.5, "space_after": 4, "bullet": True},
    
    # Special/Miscellaneous
    "SUMHD": {"font_size": 12, "bold": True, "space_before": 8, "space_after": 4},
    "EXT-ONLY": {"font_size": 10, "italic": True, "left_indent": 0.5, "space_after": 6},
}


class DocumentReconstructor:
    """
    Apply style tags to document and generate outputs.
    Uses proper Word paragraph styles instead of XML markers.
    """
    
    def __init__(self, output_dir: str | Path):
        """
        Initialize the reconstructor.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def _get_or_create_style(self, doc: Document, style_name: str) -> None:
        """
        Get existing style or create a new one with proper formatting.
        
        Args:
            doc: Document object
            style_name: Name of the style to get/create
        """
        styles = doc.styles
        
        # Check if style already exists
        try:
            existing_style = styles[style_name]
            return  # Style exists, use it
        except KeyError:
            pass  # Style doesn't exist, create it
        
        # Get style definition
        style_def = STYLE_DEFINITIONS.get(style_name, {})
        
        # Create new paragraph style
        try:
            new_style = styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
            new_style.base_style = styles['Normal']
            
            # Apply font formatting
            font = new_style.font
            font.size = Pt(style_def.get('font_size', 11))
            font.bold = style_def.get('bold', False)
            font.italic = style_def.get('italic', False)
            font.all_caps = style_def.get('caps', False)
            
            if 'color' in style_def:
                font.color.rgb = RGBColor.from_string(style_def['color'])
            
            # Apply paragraph formatting
            para_format = new_style.paragraph_format
            
            if 'alignment' in style_def:
                alignment_map = {
                    'left': WD_ALIGN_PARAGRAPH.LEFT,
                    'center': WD_ALIGN_PARAGRAPH.CENTER,
                    'right': WD_ALIGN_PARAGRAPH.RIGHT,
                    'justify': WD_ALIGN_PARAGRAPH.JUSTIFY,
                }
                para_format.alignment = alignment_map.get(style_def['alignment'], WD_ALIGN_PARAGRAPH.LEFT)
            
            if 'space_before' in style_def:
                para_format.space_before = Pt(style_def['space_before'])
            
            if 'space_after' in style_def:
                para_format.space_after = Pt(style_def['space_after'])
            
            if 'first_line_indent' in style_def:
                para_format.first_line_indent = Inches(style_def['first_line_indent'])
            
            if 'left_indent' in style_def:
                para_format.left_indent = Inches(style_def['left_indent'])
            
            if 'hanging_indent' in style_def:
                para_format.first_line_indent = Inches(-style_def['hanging_indent'])
                para_format.left_indent = Inches(style_def['hanging_indent'])
            
            logger.debug(f"Created style: {style_name}")
            
        except Exception as e:
            logger.warning(f"Could not create style '{style_name}': {e}")
    
    def apply_styles(
        self,
        source_path: str | Path,
        classifications: list[dict],
        output_name: Optional[str] = None
    ) -> Path:
        """
        Apply classification tags as proper Word paragraph styles.
        Handles both body paragraphs and table cell content.
        ENSURES NO CONTENT IS REMOVED OR MODIFIED - only styles are applied.
        
        Args:
            source_path: Path to original DOCX
            classifications: List of classification results
            output_name: Optional output filename
            
        Returns:
            Path to styled output file
        """
        source_path = Path(source_path)
        doc = Document(source_path)
        
        # Create classification lookup
        clf_lookup = {c["id"]: c for c in classifications}
        
        # Pre-create all needed styles
        unique_tags = set(c["tag"] for c in classifications)
        for tag in unique_tags:
            self._get_or_create_style(doc, tag)
        
        # CONTENT INTEGRITY: Count all content BEFORE processing
        original_body_paras = sum(1 for p in doc.paragraphs if p.text.strip())
        original_table_cells = 0
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        original_table_cells += 1
        
        logger.info(f"Content integrity check: {original_body_paras} body paragraphs, {original_table_cells} table cells")
        
        # Track paragraph index (excluding empty ones)
        # This must match the order in ingestion.py:
        # 1. First all body paragraphs
        # 2. Then all table cell content
        para_id = 1
        body_count = 0
        table_count = 0
        
        # STEP 1: Process body paragraphs (STYLE ONLY - no text modification)
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            clf = clf_lookup.get(para_id)
            if clf:
                tag = clf["tag"]
                confidence = clf.get("confidence", 85)
                
                # Apply the style ONLY - do NOT modify text content
                try:
                    para.style = tag
                    logger.debug(f"Applied style '{tag}' to paragraph {para_id}")
                    body_count += 1
                except KeyError:
                    logger.warning(f"Style '{tag}' not found for paragraph {para_id}")
                
                # For low confidence items, add a comment or highlight
                if confidence < 85:
                    self._highlight_for_review(para, tag, confidence)
            
            para_id += 1
        
        # STEP 2: Process table cells (STYLE ONLY - no text modification)
        # Table content was extracted after body paragraphs in ingestion
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    # Get cell text (combined from all paragraphs in cell)
                    cell_text = cell.text.strip()
                    if not cell_text:
                        continue
                    
                    clf = clf_lookup.get(para_id)
                    if clf:
                        tag = clf["tag"]
                        confidence = clf.get("confidence", 85)
                        
                        # Apply style to all paragraphs in the cell (STYLE ONLY)
                        for cell_para in cell.paragraphs:
                            if cell_para.text.strip():
                                try:
                                    cell_para.style = tag
                                    table_count += 1
                                except KeyError:
                                    logger.warning(f"Style '{tag}' not found for table cell {para_id}")
                                
                                # Add review marker if low confidence
                                if confidence < 85:
                                    self._highlight_for_review(cell_para, tag, confidence)
                    
                    para_id += 1
        
        logger.info(f"Applied styles: {body_count} body paragraphs, {table_count} table cells")
        
        # CONTENT INTEGRITY: Verify content count AFTER processing
        final_body_paras = sum(1 for p in doc.paragraphs if p.text.strip())
        final_table_cells = 0
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        final_table_cells += 1
        
        # Verify no content was lost
        if final_body_paras != original_body_paras:
            logger.error(f"CONTENT INTEGRITY VIOLATION: Body paragraph count changed from {original_body_paras} to {final_body_paras}")
            raise ValueError(f"Content integrity check failed: body paragraph count mismatch")
        
        if final_table_cells != original_table_cells:
            logger.error(f"CONTENT INTEGRITY VIOLATION: Table cell count changed from {original_table_cells} to {final_table_cells}")
            raise ValueError(f"Content integrity check failed: table cell count mismatch")
        
        logger.info(f"✓ Content integrity verified: {final_body_paras} body paragraphs, {final_table_cells} table cells preserved")
        
        # Generate output filename
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"{source_path.stem}_tagged_{timestamp}.docx"
        
        output_path = self.output_dir / output_name
        doc.save(output_path)
        
        logger.info(f"Saved styled document to {output_path}")
        return output_path
    
    def _highlight_for_review(self, para, tag: str, confidence: int):
        """
        Add visual indicator for paragraphs needing review.
        Uses background highlighting instead of inline text to preserve content integrity.
        
        Args:
            para: Paragraph object
            tag: Applied tag
            confidence: Confidence score
        """
        # Use yellow background highlight instead of adding text
        # This preserves the original content while flagging for review
        try:
            for run in para.runs:
                # Apply yellow highlight to indicate needs review
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW
        except Exception as e:
            logger.debug(f"Could not apply highlight: {e}")
    
    def apply_tags_with_markers(
        self,
        source_path: str | Path,
        classifications: list[dict],
        output_name: Optional[str] = None
    ) -> Path:
        """
        Apply tags as text markers (XML-style) at start of paragraphs.
        Handles both body paragraphs and table cell content.
        Legacy method for backward compatibility.
        
        Args:
            source_path: Path to original DOCX
            classifications: List of classification results
            output_name: Optional output filename
            
        Returns:
            Path to tagged output file
        """
        source_path = Path(source_path)
        doc = Document(source_path)
        
        # Create classification lookup
        clf_lookup = {c["id"]: c for c in classifications}
        
        # Track paragraph index
        para_id = 1
        body_count = 0
        table_count = 0
        
        # STEP 1: Process body paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            clf = clf_lookup.get(para_id)
            if clf:
                tag = clf["tag"]
                confidence = clf.get("confidence", 85)
                
                # Insert tag at the beginning of paragraph
                if para.runs:
                    first_run = para.runs[0]
                    
                    if confidence < 85:
                        tag_text = f"<{tag}*> "
                    else:
                        tag_text = f"<{tag}> "
                    
                    first_run.text = tag_text + first_run.text
                else:
                    if confidence < 85:
                        para.text = f"<{tag}*> {text}"
                    else:
                        para.text = f"<{tag}> {text}"
                
                body_count += 1
            
            para_id += 1
        
        # STEP 2: Process table cells
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if not cell_text:
                        continue
                    
                    clf = clf_lookup.get(para_id)
                    if clf:
                        tag = clf["tag"]
                        confidence = clf.get("confidence", 85)
                        
                        # Add tag to first paragraph in cell
                        for cell_para in cell.paragraphs:
                            if cell_para.text.strip():
                                if cell_para.runs:
                                    first_run = cell_para.runs[0]
                                    if confidence < 85:
                                        first_run.text = f"<{tag}*> " + first_run.text
                                    else:
                                        first_run.text = f"<{tag}> " + first_run.text
                                else:
                                    if confidence < 85:
                                        cell_para.text = f"<{tag}*> {cell_para.text}"
                                    else:
                                        cell_para.text = f"<{tag}> {cell_para.text}"
                                table_count += 1
                                break  # Only tag first paragraph in cell
                    
                    para_id += 1
        
        logger.info(f"Applied markers: {body_count} body paragraphs, {table_count} table cells")
        
        # Generate output filename
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"{source_path.stem}_tagged_{timestamp}.docx"
        
        output_path = self.output_dir / output_name
        doc.save(output_path)
        
        logger.info(f"Saved tagged document with markers to {output_path}")
        return output_path
    
    def generate_review_report(
        self,
        document_name: str,
        filtered_results: dict,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Generate a review report document for flagged items.
        """
        doc = Document()
        
        # Title
        title = doc.add_heading("Pre-Editor Review Report", level=0)
        
        # Document info
        doc.add_paragraph(f"Source Document: {document_name}")
        doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc.add_paragraph()
        
        # Summary section
        doc.add_heading("Summary", level=1)
        summary = filtered_results.get("summary", {})
        
        summary_table = doc.add_table(rows=4, cols=2)
        summary_table.style = 'Table Grid'
        
        rows_data = [
            ("Total Paragraphs", str(summary.get("total_paragraphs", 0))),
            ("Auto-Applied", str(summary.get("auto_applied", 0))),
            ("Needs Review", str(summary.get("needs_review", 0))),
            ("Auto-Apply Rate", f"{summary.get('auto_apply_percentage', 0):.1f}%"),
        ]
        
        for i, (label, value) in enumerate(rows_data):
            summary_table.rows[i].cells[0].text = label
            summary_table.rows[i].cells[1].text = value
        
        doc.add_paragraph()
        
        # Items needing review
        needs_review = filtered_results.get("needs_review", [])
        
        if needs_review:
            doc.add_heading("Items Requiring Review", level=1)
            doc.add_paragraph(
                f"The following {len(needs_review)} items have confidence below 85% "
                "and require human review. Look for red markers [TAG? %] in the document."
            )
            doc.add_paragraph()
            
            for item in needs_review:
                para = doc.add_paragraph()
                run = para.add_run(f"Paragraph {item['id']}")
                run.bold = True
                
                doc.add_paragraph(f"Text: \"{item.get('original_text', '')[:100]}...\"" 
                                if len(item.get('original_text', '')) > 100 
                                else f"Text: \"{item.get('original_text', '')}\"")
                
                confidence = item.get('confidence', 0)
                tag = item.get('tag', 'Unknown')
                doc.add_paragraph(f"Suggested Tag: {tag} (Confidence: {confidence}%)")
                
                if item.get('reasoning'):
                    doc.add_paragraph(f"Reasoning: {item['reasoning']}")
                
                if item.get('alternatives'):
                    doc.add_paragraph(f"Alternative Tags: {', '.join(item['alternatives'])}")
                
                doc.add_paragraph()
        else:
            doc.add_heading("All Items Auto-Applied", level=1)
            doc.add_paragraph(
                "All paragraphs were classified with high confidence (≥85%). "
                "No manual review required."
            )
        
        # Save report
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"review_report_{timestamp}.docx"
        
        output_path = self.output_dir / output_name
        doc.save(output_path)
        
        logger.info(f"Saved review report to {output_path}")
        return output_path
    
    def generate_json_output(
        self,
        document_name: str,
        classifications: list[dict],
        filtered_results: dict,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Generate JSON output with all classification data.
        """
        output_data = {
            "document_name": document_name,
            "processed_at": datetime.now().isoformat(),
            "summary": filtered_results.get("summary", {}),
            "classifications": classifications,
            "flagged_items": filtered_results.get("needs_review", []),
        }
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"classification_results_{timestamp}.json"
        
        output_path = self.output_dir / output_name
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        logger.info(f"Saved JSON results to {output_path}")
        return output_path
    
    def generate_html_report(
        self,
        document_name: str,
        classifications: list[dict],
        filtered_results: dict,
        output_name: Optional[str] = None
    ) -> Path:
        """
        Generate an interactive HTML report of classification results.
        This provides a user-friendly view of the results.
        """
        from .html_report import generate_html_report
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"classification_report_{timestamp}.html"
        
        output_path = self.output_dir / output_name
        
        generate_html_report(
            document_name,
            classifications,
            filtered_results,
            output_path
        )
        
        logger.info(f"Saved HTML report to {output_path}")
        return output_path


def reconstruct_document(
    source_path: str | Path,
    classifications: list[dict],
    filtered_results: dict,
    output_dir: str | Path,
    use_markers: bool = False,  # Changed default to False for style-based output
    output_base: str = None  # Custom output base name
) -> dict:
    """
    Convenience function to generate all outputs.
    
    Args:
        source_path: Path to original DOCX
        classifications: Classification results
        filtered_results: Filtered results dict
        output_dir: Output directory
        use_markers: If True, use XML markers; if False, use Word styles (default)
        output_base: Base name for output files (e.g., "chapter1_processed")
        
    Returns:
        Dict with paths to all output files
    """
    source_path = Path(source_path)
    reconstructor = DocumentReconstructor(output_dir)
    
    # Use custom base name or generate from source
    if output_base is None:
        output_base = f"{source_path.stem}_processed"
    
    # Generate output filenames
    tagged_name = f"{output_base}.docx"
    report_name = f"{output_base}_review.docx"
    json_name = f"{output_base}_results.json"
    html_name = f"{output_base}_report.html"
    
    # Generate tagged document
    if use_markers:
        tagged_path = reconstructor.apply_tags_with_markers(
            source_path, classifications, tagged_name
        )
    else:
        tagged_path = reconstructor.apply_styles(
            source_path, classifications, tagged_name
        )
    
    # Generate review report (DOCX)
    report_path = reconstructor.generate_review_report(
        source_path.name,
        filtered_results,
        report_name
    )
    
    # Generate JSON output (for programmatic access)
    json_path = reconstructor.generate_json_output(
        source_path.name,
        classifications,
        filtered_results,
        json_name
    )
    
    # Generate HTML report (for user-friendly viewing)
    html_path = reconstructor.generate_html_report(
        source_path.name,
        classifications,
        filtered_results,
        html_name
    )
    
    # Return only filenames (not full paths) for URL construction
    return {
        "tagged_document": tagged_path.name,
        "review_report": report_path.name,
        "json_results": json_path.name,
        "html_report": html_path.name,
    }


if __name__ == "__main__":
    # Test with sample data
    sample_classifications = [
        {"id": 1, "tag": "CN", "confidence": 99},
        {"id": 2, "tag": "CT", "confidence": 98},
        {"id": 3, "tag": "H1", "confidence": 75, "reasoning": "Could be H2"},
    ]
    
    sample_filtered = {
        "summary": {
            "total_paragraphs": 3,
            "auto_applied": 2,
            "needs_review": 1,
            "auto_apply_percentage": 66.7,
        },
        "needs_review": [
            {
                "id": 3,
                "tag": "H1",
                "confidence": 75,
                "original_text": "Overview",
                "reasoning": "Could be H2",
                "alternatives": ["H2", "CT"],
            }
        ]
    }
    
    reconstructor = DocumentReconstructor("/tmp/test_output")
    
    # Generate review report
    report_path = reconstructor.generate_review_report("test.docx", sample_filtered)
    print(f"Generated report: {report_path}")
    
    # Generate JSON
    json_path = reconstructor.generate_json_output(
        "test.docx",
        sample_classifications,
        sample_filtered
    )
    print(f"Generated JSON: {json_path}")
