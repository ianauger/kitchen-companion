"""Configuration module for Kitchen Companion app."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Validation constants
MAX_NOTE_LENGTH = 2000
MAX_TAG_NAME_LENGTH = 100
MAX_DOWNLOAD_SIZE = 10 * 1024 * 1024  # 10MB
DOWNLOAD_TIMEOUT = 15  # seconds
DOWNLOAD_CHUNK_SIZE = 8192  # 8KB

# Pagination defaults
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR / "kitchen_companion.db"}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
    def __init__(self):
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY must be set in production")


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}