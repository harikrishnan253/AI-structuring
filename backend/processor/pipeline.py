"""
Document Processing Pipeline
Simplified interface for the queue service.
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime

from .ingestion import extract_document
from .classifier import classify_document
from .reconstruction import DocumentReconstructor
from .confidence import ConfidenceFilter

logger = logging.getLogger(__name__)


def process_document(
    input_path: str,
    output_folder: str,
    document_type: str = "Academic Document",
    use_markers: bool = False
) -> dict:
    """
    Process a single document through the full pipeline.
    
    Args:
        input_path: Path to input DOCX file
        output_folder: Base output folder (with processed/review/json subfolders)
        document_type: Type of document for classification
        use_markers: Whether to use XML markers (True) or Word styles (False)
        
    Returns:
        Dictionary with results and file paths
    """
    input_path = Path(input_path)
    output_folder = Path(output_folder)
    
    logger.info(f"Processing: {input_path.name}")
    
    # Get API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    # Stage 1: Ingestion
    logger.info("Stage 1: Document Ingestion")
    paragraphs, stats = extract_document(input_path)
    
    # Stage 2: Classification
    logger.info("Stage 2: AI Classification")
    classifications, token_usage = classify_document(
        paragraphs=paragraphs,
        document_name=input_path.name,
        api_key=api_key,
        document_type=document_type
    )
    
    # Stage 3: Confidence Filtering
    logger.info("Stage 3: Confidence Filtering")
    filter_service = ConfidenceFilter(threshold=85)
    filtered = filter_service.filter(classifications, paragraphs)
    
    # Stage 4: Reconstruction
    logger.info("Stage 4: Document Reconstruction")
    
    # Generate output filenames
    base_name = input_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_name = f"{base_name}_processed.docx"
    review_name = f"{base_name}_processed_review.docx"
    json_name = f"{base_name}_processed_results.json"
    
    # Create reconstructor with temp directory, then move files
    temp_dir = output_folder / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    reconstructor = DocumentReconstructor(output_dir=str(temp_dir))
    
    if use_markers:
        tagged_path = reconstructor.apply_tags_with_markers(
            source_path=input_path,
            classifications=classifications,
            output_name=output_name
        )
    else:
        tagged_path = reconstructor.apply_styles(
            source_path=input_path,
            classifications=classifications,
            output_name=output_name
        )
    
    # Generate review report
    review_path = reconstructor.generate_review_report(
        document_name=input_path.name,
        filtered_results=filtered.to_dict(),
        output_name=review_name
    )
    
    # Generate JSON results
    json_path = reconstructor.generate_json_output(
        document_name=input_path.name,
        classifications=classifications,
        filtered_results=filtered.to_dict(),
        output_name=json_name
    )
    
    # Generate HTML report
    html_name = f"{base_name}_processed_report.html"
    html_path = reconstructor.generate_html_report(
        document_name=input_path.name,
        classifications=classifications,
        filtered_results=filtered.to_dict(),
        output_name=html_name
    )
    
    # Move files to proper subfolders
    final_paths = {}
    
    if tagged_path and Path(tagged_path).exists():
        dest = output_folder / "processed" / output_name
        shutil.move(str(tagged_path), str(dest))
        final_paths['output_path'] = str(dest)
    
    if review_path and Path(review_path).exists():
        dest = output_folder / "review" / review_name
        shutil.move(str(review_path), str(dest))
        final_paths['review_path'] = str(dest)
    
    if json_path and Path(json_path).exists():
        dest = output_folder / "json" / json_name
        shutil.move(str(json_path), str(dest))
        final_paths['json_path'] = str(dest)
    
    if html_path and Path(html_path).exists():
        # Create html folder if needed
        html_folder = output_folder / "html"
        html_folder.mkdir(exist_ok=True)
        dest = html_folder / html_name
        shutil.move(str(html_path), str(dest))
        final_paths['html_path'] = str(dest)
    
    # Cleanup temp directory
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    
    # Build result
    result = {
        **final_paths,
        'total_paragraphs': stats.get('total_paragraphs', 0),
        'auto_applied': filtered.auto_applied_count if hasattr(filtered, 'auto_applied_count') else 0,
        'needs_review': filtered.needs_review_count if hasattr(filtered, 'needs_review_count') else 0,
        'input_tokens': token_usage.get('input_tokens', 0),
        'output_tokens': token_usage.get('output_tokens', 0),
        'total_tokens': token_usage.get('total_tokens', 0),
    }
    
    logger.info(f"Completed: {input_path.name}")
    logger.info(f"  Total paragraphs: {result['total_paragraphs']}")
    logger.info(f"  Tokens used: {result['total_tokens']:,}")
    
    return result
