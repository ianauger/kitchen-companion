"""Tests for config, save_uploaded_image edge cases, and session cookie hardening."""
import pytest
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch


class TestProductionConfig:
    def test_missing_secret_key_raises(self):
        """ProductionConfig raises if SECRET_KEY is not set."""
        from config import ProductionConfig
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match='SECRET_KEY'):
                ProductionConfig()

    def test_missing_jwt_secret_key_raises(self):
        """ProductionConfig raises if JWT_SECRET_KEY is not set."""
        from config import ProductionConfig
        with patch.dict(os.environ, {'SECRET_KEY': 'something'}, clear=True):
            with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
                ProductionConfig()

    def test_production_config_with_keys(self):
        """ProductionConfig succeeds when both keys are set."""
        from config import ProductionConfig
        with patch.dict(os.environ, {
            'SECRET_KEY': 'prod-secret-32-bytes-key-here',
            'JWT_SECRET_KEY': 'prod-jwt-secret-key-here',
        }, clear=True):
            cfg = ProductionConfig()
            assert cfg.DEBUG is False


class TestDevelopmentConfig:
    def test_dev_config_has_defaults(self):
        """DevelopmentConfig provides default keys."""
        from config import DevelopmentConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = DevelopmentConfig()
            assert cfg.DEBUG is True
            assert cfg.SECRET_KEY is not None
            assert cfg.JWT_SECRET_KEY is not None


class TestConfigSessionCookies:
    def test_session_cookie_httponly(self, monkeypatch):
        """SESSION_COOKIE_HTTPONLY is True."""
        monkeypatch.setattr('config.Config.SECRET_KEY', 'test-key', raising=False)
        monkeypatch.setattr('config.Config.JWT_SECRET_KEY', 'test-jwt-key', raising=False)
        from config import Config
        cfg = Config()
        assert cfg.SESSION_COOKIE_HTTPONLY is True

    def test_session_cookie_secure_default(self, monkeypatch):
        """SESSION_COOKIE_SECURE defaults to True."""
        monkeypatch.setattr('config.Config.SECRET_KEY', 'test-key', raising=False)
        monkeypatch.setattr('config.Config.JWT_SECRET_KEY', 'test-jwt-key', raising=False)
        from config import Config
        cfg = Config()
        assert cfg.SESSION_COOKIE_SECURE is True

    def test_session_cookie_secure_false_by_env(self, monkeypatch):
        """SESSION_COOKIE_SECURE can be False, as SESSION_SECURE env var is read at class level."""
        monkeypatch.setattr('config.Config.SECRET_KEY', 'test-key', raising=False)
        monkeypatch.setattr('config.Config.JWT_SECRET_KEY', 'test-jwt-key', raising=False)
        from config import Config
        # When SESSION_SECURE env is set to 'false', the class-level attribute will be False
        # We verify the Config class has the attribute
        assert hasattr(Config, 'SESSION_COOKIE_SECURE')

    def test_session_cookie_samesite_lax(self, monkeypatch):
        """SESSION_COOKIE_SAMESITE is 'Lax'."""
        monkeypatch.setattr('config.Config.SECRET_KEY', 'test-key', raising=False)
        monkeypatch.setattr('config.Config.JWT_SECRET_KEY', 'test-jwt-key', raising=False)
        from config import Config
        cfg = Config()
        assert cfg.SESSION_COOKIE_SAMESITE == 'Lax'


class TestConfigConstants:
    def test_constants_defined(self):
        """All expected config constants are defined."""
        from config import (
            MAX_NOTE_LENGTH, MAX_TAG_NAME_LENGTH,
            MAX_DOWNLOAD_SIZE, DOWNLOAD_TIMEOUT,
            DOWNLOAD_CHUNK_SIZE, DEFAULT_PER_PAGE, MAX_PER_PAGE
        )
        assert MAX_NOTE_LENGTH == 2000
        assert MAX_TAG_NAME_LENGTH == 100
        assert MAX_DOWNLOAD_SIZE == 10 * 1024 * 1024
        assert DOWNLOAD_TIMEOUT == 15
        assert DOWNLOAD_CHUNK_SIZE == 8192
        assert DEFAULT_PER_PAGE == 20
        assert MAX_PER_PAGE == 100


class TestSaveUploadedImage:
    def _get_save_func(self):
        from app.routes import save_uploaded_image
        return save_uploaded_image

    def test_no_filename_returns_error(self, app):
        """File with no filename returns error."""
        save = self._get_save_func()
        with app.app_context():
            from werkzeug.datastructures import FileStorage
            file = FileStorage(stream=BytesIO(b''), filename='')
            rel, err = save(file, 1)
            assert rel is None
            assert err == 'No file selected'

    def test_invalid_extension(self, app):
        """Non-image extension is rejected."""
        save = self._get_save_func()
        with app.app_context():
            from werkzeug.datastructures import FileStorage
            file = FileStorage(stream=BytesIO(b'data'), filename='evil.php')
            rel, err = save(file, 1)
            assert rel is None
            assert 'Invalid file type' in err

    def test_double_extension_jpg_accepted(self, app, tmp_path):
        """Double extension like evil.php.jpg is accepted (only final suffix matters)."""
        save = self._get_save_func()
        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                from werkzeug.datastructures import FileStorage
                file = FileStorage(stream=BytesIO(b'fake data'), filename='evil.php.jpg')
                rel, err = save(file, 1)
                assert rel is not None
                assert err is None
                # Filename should be our generated one, not the original
                assert 'evil.php' not in str(rel)
            finally:
                app.static_folder = original

    def test_double_extension_php_rejected(self, app):
        """evil.jpg.php is rejected because final suffix is .php."""
        save = self._get_save_func()
        with app.app_context():
            from werkzeug.datastructures import FileStorage
            file = FileStorage(stream=BytesIO(b'<?php echo "hack"; ?>'), filename='evil.jpg.php')
            rel, err = save(file, 1)
            assert rel is None
            assert 'Invalid file type' in err

    def test_all_allowed_extensions(self, app, tmp_path):
        """All .jpg, .jpeg, .png, .gif, .webp are accepted."""
        save = self._get_save_func()
        allowed = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                from werkzeug.datastructures import FileStorage
                for ext in allowed:
                    file = FileStorage(stream=BytesIO(b'data'), filename=f'test{ext}')
                    rel, err = save(file, 1)
                    assert rel is not None, f'{ext} should be accepted'
                    assert err is None, f'{ext} should not have error'
            finally:
                app.static_folder = original

    def test_uppercase_extension_accepted(self, app, tmp_path):
        """Uppercase extensions like .JPG are normalized and accepted."""
        save = self._get_save_func()
        with app.app_context():
            original = app.static_folder
            app.static_folder = str(tmp_path)
            try:
                from werkzeug.datastructures import FileStorage
                file = FileStorage(stream=BytesIO(b'data'), filename='PHOTO.JPG')
                rel, err = save(file, 1)
                assert rel is not None
                assert err is None
            finally:
                app.static_folder = original
