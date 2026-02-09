"""
Document Processing Pipeline
Simplified interface for the queue service.
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from .blocks import extract_blocks
from .classifier import classify_blocks_with_prompt
from .reconstruction import DocumentReconstructor
from .confidence import ConfidenceFilter
from .validator import validate_and_repair
from app.services.allowed_styles import load_allowed_styles
from app.services.prompt_router import route_prompt
from app.services.quality_score import score_document
from app.services.review_bundle import create_review_bundle

logger = logging.getLogger(__name__)


def process_document(
    input_path: str,
    output_folder: str,
    document_type: str = "Academic Document",
    use_markers: bool = False,
    classifier_override: Optional[Callable[[list[dict], list[dict]], list[dict]]] = None,
    apply_repair: bool = True,
    job_id: str | None = None,
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
    
    # Stage 1: Ingestion
    logger.info("Stage 1: Document Ingestion (Blocks + Structural Features)")
    blocks, paragraphs, stats = extract_blocks(input_path)
    
    # Stage 2: Classification (Option 2 retry ladder)
    logger.info("Stage 2: AI Classification")
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    retry_count = 0
    quality_score = None
    quality_action = None
    quality_metrics = {}

    allowed_styles = load_allowed_styles()

    if classifier_override:
        classifications = classifier_override(blocks, paragraphs)
        if apply_repair:
            classifications = validate_and_repair(
                classifications,
                blocks,
                allowed_styles=allowed_styles,
                preserve_lists=use_markers,
                preserve_marker_pmi=use_markers,
            )
        # Score once for override path
        scored_blocks = []
        clf_by_id = {c["id"]: c for c in classifications}
        for b in blocks:
            c = clf_by_id.get(b["id"], {})
            scored_blocks.append(
                {
                    **b,
                    "tag": c.get("tag", "TXT"),
                    "confidence": c.get("confidence", 0),
                    "repaired": c.get("repaired", False),
                    "repair_reason": c.get("repair_reason"),
                }
            )
        quality_score, quality_metrics, quality_action = score_document(scored_blocks, allowed_styles)
    else:
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        primary_model = os.getenv("GEMINI_MODEL_PRIMARY", "gemini-2.5-flash-lite")
        strong_model = os.getenv("GEMINI_MODEL_STRONG", "gemini-2.0-flash")

        classifications = []
        for attempt in range(1, 4):
            if attempt == 1:
                prompt_name = "default"
                prompt_text = None
                model_name = primary_model
            else:
                prompt_name, prompt_text = route_prompt(blocks)
                model_name = primary_model if attempt == 2 else strong_model

            logger.info(f"Attempt {attempt}: model={model_name}, prompt={prompt_name}")
            classifications, token_usage = classify_blocks_with_prompt(
                blocks=blocks,
                document_name=input_path.name,
                api_key=api_key,
                document_type=document_type,
                model_name=model_name,
                system_prompt_override=prompt_text,
            )

            if apply_repair:
                logger.info("Stage 3: Validation + Deterministic Repair")
                classifications = validate_and_repair(
                    classifications,
                    blocks,
                    allowed_styles=allowed_styles,
                    preserve_lists=use_markers,
                    preserve_marker_pmi=use_markers,
                )

            # Score document quality
            scored_blocks = []
            clf_by_id = {c["id"]: c for c in classifications}
            for b in blocks:
                c = clf_by_id.get(b["id"], {})
                scored_blocks.append(
                    {
                        **b,
                        "tag": c.get("tag", "TXT"),
                        "confidence": c.get("confidence", 0),
                        "repaired": c.get("repaired", False),
                        "repair_reason": c.get("repair_reason"),
                    }
                )

            quality_score, quality_metrics, quality_action = score_document(scored_blocks, allowed_styles)

            if quality_action == "PASS":
                break
            if quality_action == "RETRY" and attempt < 3:
                retry_count += 1
                continue
            break

    # Stage 4: Confidence Filtering
    logger.info("Stage 4: Confidence Filtering")
    filter_service = ConfidenceFilter(threshold=85)
    filtered = filter_service.filter(classifications, paragraphs)
    
    # Stage 5: Reconstruction
    logger.info("Stage 5: Document Reconstruction")
    
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
    
    review_bundle_path = None
    if quality_action == "REVIEW":
        # build decisions payload
        clf_by_id = {c["id"]: c for c in classifications}
        decisions = []
        for b in blocks:
            c = clf_by_id.get(b["id"], {})
            decisions.append(
                {
                    "id": b["id"],
                    "text": b.get("text", ""),
                    "tag": c.get("tag"),
                    "confidence": c.get("confidence"),
                    "repaired": c.get("repaired", False),
                    "repair_reason": c.get("repair_reason"),
                }
            )
        review_bundle_path = create_review_bundle(
            job_id or input_path.stem,
            str(input_path),
            final_paths.get("output_path", ""),
            decisions,
            {
                "score": quality_score,
                "action": quality_action,
                "metrics": quality_metrics,
                "retry_count": retry_count,
            },
        )

    # Build result
    result = {
        **final_paths,
        'total_paragraphs': stats.get('total_paragraphs', 0),
        'auto_applied': filtered.auto_applied_count if hasattr(filtered, 'auto_applied_count') else 0,
        'needs_review': filtered.needs_review_count if hasattr(filtered, 'needs_review_count') else 0,
        'input_tokens': token_usage.get('input_tokens', 0),
        'output_tokens': token_usage.get('output_tokens', 0),
        'total_tokens': token_usage.get('total_tokens', 0),
        'quality_score': quality_score,
        'quality_action': quality_action,
        'retry_count': retry_count,
        'review_bundle_path': review_bundle_path,
    }
    
    logger.info(f"Completed: {input_path.name}")
    logger.info(f"  Total paragraphs: {result['total_paragraphs']}")
    logger.info(f"  Tokens used: {result['total_tokens']:,}")
    
    return result
