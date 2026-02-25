"""
Deterministic smoke test proving production classifier invokes Gemini for style tagging.

Run:
    set LLM_ENABLED=1
    set LLM_REQUIRED=1
    set GEMINI_MODEL=gemini-2.5-pro
    python tools/smoke_llm_call.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from config import GEMINI_API_KEY, GEMINI_MODEL, LLM_ENABLED, LLM_REQUIRED  # noqa: E402
from app import create_app  # noqa: E402
from app.models import db, Batch, Job, JobStatus, LLMCall  # noqa: E402
from processor.classifier import classify_blocks_with_prompt  # noqa: E402


class _LLMLogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.start_payload: dict | None = None
        self.end_payload: dict | None = None
        self.fallback_seen = False

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if msg.startswith("LLM_CALL_START "):
            raw = msg[len("LLM_CALL_START ") :]
            self.start_payload = json.loads(raw)
        elif msg.startswith("LLM_CALL_END "):
            # Plain-text end log (required observability format)
            self.end_payload = {"raw": msg}
        elif msg.startswith("LLM_CALL_SUCCESS "):
            # Backward-compatible structured end log
            raw = msg[len("LLM_CALL_SUCCESS ") :]
            self.end_payload = json.loads(raw)
        elif msg.startswith("LLM_FALLBACK_USED "):
            self.fallback_seen = True


def main() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if not LLM_ENABLED:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if not LLM_REQUIRED:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")

    model_name = os.getenv("GEMINI_MODEL", GEMINI_MODEL or "gemini-2.5-pro")
    if not model_name:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")

    blocks = [
        {"id": 1, "text": "Figure 1. Anatomy of the Heart", "metadata": {"context_zone": "BODY"}},
        {"id": 2, "text": "1. Introduction", "metadata": {"context_zone": "BODY"}},
        {"id": 3, "text": "Smith J. Clinical Medicine. 2020.", "metadata": {"context_zone": "BACK_MATTER"}},
    ]

    app = create_app()
    with app.app_context():
        batch = Batch(
            batch_id=f"smoke-{int(time.time())}",
            name="LLM Smoke",
            document_type="Academic Document",
            use_markers=False,
            total_jobs=1,
            completed_jobs=0,
            failed_jobs=0,
            output_folder="outputs",
        )
        db.session.add(batch)
        db.session.flush()
        job = Job(
            job_id=f"smoke-job-{int(time.time())}",
            batch_id=batch.id,
            original_filename="smoke_llm_call.docx",
            input_path="smoke_llm_call.docx",
            document_type="Academic Document",
            use_markers=False,
            status=JobStatus.PROCESSING,
            queue_position=1,
        )
        db.session.add(job)
        db.session.commit()

    capture = _LLMLogCapture()
    clf_logger = logging.getLogger("processor.classifier")
    clf_logger.addHandler(capture)
    clf_logger.setLevel(logging.INFO)

    start = time.perf_counter()
    try:
        predictions, token_usage = classify_blocks_with_prompt(
            blocks=blocks,
            document_name="smoke_llm_call.docx",
            api_key=GEMINI_API_KEY,
            document_type="Academic Document",
            model_name=model_name,
            llm_enabled=True,
            llm_required=True,
        )
    finally:
        clf_logger.removeHandler(capture)
    end = time.perf_counter()
    latency_ms = int((end - start) * 1000)

    if capture.fallback_seen:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if not capture.start_payload or not capture.end_payload:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    actual_model = str(capture.start_payload.get("model", "")).strip()
    if not actual_model:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if not predictions or len(predictions) < 3:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if not token_usage:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if int(token_usage.get("llm_latency_ms", 0) or 0) <= 0:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if token_usage.get("llm_provider") != "gemini":
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if token_usage.get("llm_model") != model_name:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")

    with app.app_context():
        job = Job.query.filter_by(original_filename="smoke_llm_call.docx").order_by(Job.id.desc()).first()
        if not job:
            raise RuntimeError("LLM NOT INVOKED PROPERLY")
        job.status = JobStatus.COMPLETED
        job.input_tokens = token_usage.get("input_tokens")
        job.output_tokens = token_usage.get("output_tokens")
        job.total_tokens = token_usage.get("total_tokens")
        job.llm_latency_ms = token_usage.get("llm_latency_ms")
        job.llm_provider = token_usage.get("llm_provider")
        job.llm_model = token_usage.get("llm_model")
        for call in token_usage.get("llm_calls", []) or []:
            db.session.add(
                LLMCall(
                    job_id=job.job_id,
                    request_id=call.get("request_id"),
                    provider=call.get("provider"),
                    model=call.get("model"),
                    latency_ms=call.get("latency_ms"),
                    input_tokens=call.get("input_tokens"),
                    output_tokens=call.get("output_tokens"),
                )
            )
        db.session.commit()

    pred_by_id = {p["id"]: p.get("tag", "") for p in predictions}

    print("===== LLM SMOKE TEST =====")
    print("LLM_PROVIDER: gemini")
    print(f"MODEL_NAME: {actual_model}")
    print(f"BLOCK_COUNT: {len(blocks)}")
    print(f"LATENCY_MS: {latency_ms}")
    print(f"TOKENS_AVAILABLE: {'yes' if input_tokens is not None and output_tokens is not None else 'no'}")
    print(f"INPUT_TOKENS: {input_tokens}")
    print(f"OUTPUT_TOKENS: {output_tokens}")
    print("PREDICTIONS:")
    print(f"    id=1 -> {pred_by_id.get(1, '')}")
    print(f"    id=2 -> {pred_by_id.get(2, '')}")
    print(f"    id=3 -> {pred_by_id.get(3, '')}")
    print("==========================")


if __name__ == "__main__":
    main()
    input_tokens = token_usage.get("input_tokens")
    output_tokens = token_usage.get("output_tokens")
    if input_tokens is not None and int(input_tokens) < 0:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
    if output_tokens is not None and int(output_tokens) < 0:
        raise RuntimeError("LLM NOT INVOKED PROPERLY")
