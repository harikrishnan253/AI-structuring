"""
Configuration for the Pre-Editor backend.
"""

import os
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}

# Base directory
BASE_DIR = Path(__file__).parent.absolute()

# Folders
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'uploads'))
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', str(BASE_DIR / 'outputs'))

# =====================================================
# Database configuration
# =====================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Production (PostgreSQL, etc.)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    # Development fallback (SQLite)
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        str(BASE_DIR / "dev.db")
    )
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

SQLALCHEMY_TRACK_MODIFICATIONS = False

# API Keys
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# Gemini model defaults
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', os.getenv('GEMINI_MODEL_PRIMARY', 'gemini-2.5-pro'))
FAST_FALLBACK_MODEL = os.getenv('FAST_FALLBACK_MODEL', os.getenv('GEMINI_MODEL_STRONG', 'gemini-2.5-flash'))

# LLM execution controls
LLM_ENABLED = _env_flag("LLM_ENABLED", True)
LLM_REQUIRED = _env_flag("LLM_REQUIRED", False)

# Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max upload

# Processing
MAX_PARAGRAPHS_PER_CHUNK = 100
CONFIDENCE_THRESHOLD = 85
