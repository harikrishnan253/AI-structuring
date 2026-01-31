"""
Configuration for the Pre-Editor backend.
"""

import os
from pathlib import Path

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

# Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max upload


# =====================================================
# AI Model Configuration
# =====================================================

# Primary classification model
# Options: 
#   - gemini-2.5-flash (recommended for accuracy)
#   - gemini-2.5-flash-lite (faster, lower cost)
#   - gemini-2.0-flash (fallback)
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

# Fallback model (if primary fails)
GEMINI_FALLBACK_MODEL = os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-2.5-flash')

# API configuration
GEMINI_TEMPERATURE = float(os.getenv('GEMINI_TEMPERATURE', '0.1'))
GEMINI_TOP_P = float(os.getenv('GEMINI_TOP_P', '0.95'))
GEMINI_TOP_K = int(os.getenv('GEMINI_TOP_K', '40'))
GEMINI_MAX_TOKENS = int(os.getenv('GEMINI_MAX_TOKENS', '8192'))

# Processing
MAX_PARAGRAPHS_PER_CHUNK = 100
CONFIDENCE_THRESHOLD = 85
