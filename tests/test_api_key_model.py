"""Tests for API key model methods: set_api_key, check_api_key, revoke_api_key, to_dict."""
import pytest
from app.auth import User
from app import db


class TestApiKeyMethods:
    def test_set_api_key_generates_key(self, app):
        """set_api_key generates a raw key and stores its hash."""
        with app.app_context():
            user = User(username='apikeytest', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            raw_key = user.set_api_key()
            assert raw_key.startswith('sk-')
            assert len(raw_key) > 40
            assert user.api_key_hash is not None
            assert user.api_key_hash != raw_key
            assert user.api_key_prefix == raw_key[:12]
            assert user.api_key_created_at is not None

    def test_check_api_key_valid(self, app):
        """check_api_key returns True for the correct raw key."""
        with app.app_context():
            user = User(username='checktest', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            raw = user.set_api_key()
            assert user.check_api_key(raw) is True

    def test_check_api_key_invalid(self, app):
        """check_api_key returns False for wrong key."""
        with app.app_context():
            user = User(username='checktest2', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            user.set_api_key()
            assert user.check_api_key('sk-this-is-fake-key-12345') is False

    def test_check_api_key_with_no_key_set(self, app):
        """check_api_key returns False when no API key exists."""
        with app.app_context():
            user = User(username='nokey', role='viewer')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            assert user.check_api_key('sk-anything') is False

    def test_revoke_api_key_clears_fields(self, app):
        """revoke_api_key nulls out all API key fields."""
        with app.app_context():
            user = User(username='revoketest', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            raw = user.set_api_key()
            assert user.api_key_hash is not None

            user.revoke_api_key()
            assert user.api_key_hash is None
            assert user.api_key_prefix is None
            assert user.api_key_created_at is None
            assert user.check_api_key(raw) is False

    def test_set_api_key_replaces_existing(self, app):
        """Calling set_api_key again replaces the old key."""
        with app.app_context():
            user = User(username='replacetest', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            old_raw = user.set_api_key()
            new_raw = user.set_api_key()

            assert old_raw != new_raw
            assert user.check_api_key(old_raw) is False
            assert user.check_api_key(new_raw) is True


class TestApiKeyToDict:
    def test_to_dict_includes_api_key_status(self, app):
        """to_dict includes has_api_key, api_key_prefix, api_key_created_at."""
        with app.app_context():
            user = User(username='dictapikey', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()

            d = user.to_dict()
            assert d['has_api_key'] is False
            assert d['api_key_prefix'] is None
            assert d['api_key_created_at'] is None

            user.set_api_key()
            db.session.flush()
            d = user.to_dict()
            assert d['has_api_key'] is True
            assert d['api_key_prefix'] is not None
            assert d['api_key_created_at'] is not None

    def test_to_dict_excludes_raw_hash(self, app):
        """to_dict does NOT expose the api_key_hash."""
        with app.app_context():
            user = User(username='nohashleak', role='editor')
            user.set_password('Test1234!')
            db.session.add(user)
            db.session.flush()
            user.set_api_key()

            d = user.to_dict()
            assert 'api_key_hash' not in d
