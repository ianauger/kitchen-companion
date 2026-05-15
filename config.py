"""Configuration module for Kitchen Companion app."""
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent

# Validation constants
MAX_NOTE_LENGTH = 2000
MAX_TAG_NAME_LENGTH = 100
MAX_DOWNLOAD_SIZE = 10 * 1024 * 1024  # 10MB
DOWNLOAD_TIMEOUT = 15  # seconds
DOWNLOAD_CHUNK_SIZE = 8192  # 8KB
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request body

# Pagination defaults
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 200  # TODO: consider lowering (e.g. 100) to reduce response payload size

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR / "kitchen_companion.db"}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_recycle': 1800,  # 30 minutes
        'pool_pre_ping': True,
    }
    
    def __init__(self):
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set")
        if not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY environment variable must be set")
    
    # JWT settings
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request body
    # Session settings (web UI)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret-change-in-production')
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

    # TODO: call super().__init__() so any future Config validation runs in production too
    def __init__(self):
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY must be set in production")
        if not os.environ.get('JWT_SECRET_KEY'):
            raise ValueError("JWT_SECRET_KEY must be set in production")


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}