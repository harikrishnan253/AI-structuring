"""
Database models for the queue system.
Uses SQLite - no external database required.
Timestamps are in IST (India Standard Time - UTC+5:30)
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# IST timezone offset (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_ist_now():
    """Get current datetime in IST timezone."""
    return datetime.now(IST)


def utc_to_ist(utc_dt):
    """Convert UTC datetime to IST."""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(IST)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Batch(db.Model):
    """A batch of documents uploaded together."""
    __tablename__ = 'batches'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=get_ist_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Settings
    document_type = db.Column(db.String(100), default="Academic Document")
    use_markers = db.Column(db.Boolean, default=False)
    
    # Statistics
    total_jobs = db.Column(db.Integer, default=0)
    completed_jobs = db.Column(db.Integer, default=0)
    failed_jobs = db.Column(db.Integer, default=0)
    
    # Output folder path
    output_folder = db.Column(db.String(500), nullable=True)
    
    # Relationships
    jobs = db.relationship('Job', backref='batch', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def status(self) -> str:
        if self.total_jobs == 0:
            return "empty"
        if self.completed_jobs + self.failed_jobs == self.total_jobs:
            return "completed" if self.failed_jobs == 0 else "completed_with_errors"
        if any(j.status == JobStatus.PROCESSING for j in self.jobs):
            return "processing"
        if any(j.status == JobStatus.PENDING for j in self.jobs):
            return "pending"
        return "completed"
    
    @property
    def progress_percent(self) -> int:
        if self.total_jobs == 0:
            return 0
        return int((self.completed_jobs + self.failed_jobs) / self.total_jobs * 100)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'document_type': self.document_type,
            'use_markers': self.use_markers,
            'total_jobs': self.total_jobs,
            'completed_jobs': self.completed_jobs,
            'failed_jobs': self.failed_jobs,
            'status': self.status,
            'progress_percent': self.progress_percent,
            'output_folder': self.output_folder,
            'timezone': 'IST',
        }


class Job(db.Model):
    """A single document processing job."""
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(36), unique=True, nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    
    # File info
    original_filename = db.Column(db.String(255), nullable=False)
    input_path = db.Column(db.String(500), nullable=False)
    
    # Settings
    document_type = db.Column(db.String(100), nullable=True)
    use_markers = db.Column(db.Boolean, nullable=True)
    
    # Status
    status = db.Column(db.Enum(JobStatus), default=JobStatus.PENDING)
    queue_position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=get_ist_now)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Results
    output_path = db.Column(db.String(500), nullable=True)
    review_path = db.Column(db.String(500), nullable=True)
    json_path = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Statistics
    total_paragraphs = db.Column(db.Integer, nullable=True)
    auto_applied = db.Column(db.Integer, nullable=True)
    needs_review = db.Column(db.Integer, nullable=True)
    processing_time_seconds = db.Column(db.Float, nullable=True)
    
    # Token usage
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)
    
    # Content integrity tracking
    original_paragraph_count = db.Column(db.Integer, nullable=True)
    processed_paragraph_count = db.Column(db.Integer, nullable=True)
    content_hash = db.Column(db.String(64), nullable=True)  # SHA-256 hash of original content
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'job_id': self.job_id,
            'batch_id': self.batch_id,
            'original_filename': self.original_filename,
            'status': self.status.value if self.status else None,
            'queue_position': self.queue_position,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'output_path': self.output_path,
            'review_path': self.review_path,
            'json_path': self.json_path,
            'error_message': self.error_message,
            'total_paragraphs': self.total_paragraphs,
            'auto_applied': self.auto_applied,
            'needs_review': self.needs_review,
            'processing_time_seconds': self.processing_time_seconds,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'timezone': 'IST',
            # Content integrity info
            'original_paragraph_count': self.original_paragraph_count,
            'processed_paragraph_count': self.processed_paragraph_count,
            'content_verified': self.original_paragraph_count == self.processed_paragraph_count if self.original_paragraph_count else None,
        }


def init_db(app):
    """Initialize database."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
