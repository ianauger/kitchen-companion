"""Tests for User model methods: set_password, set_password_validated, check_password."""
import pytest
from app.auth import User, validate_password
from app import db


class TestValidatePassword:
    def test_valid_password(self):
        valid, err = validate_password('Password123')
        assert valid is True
        assert err is None

    def test_too_short(self):
        valid, err = validate_password('Ab1')
        assert valid is False
        assert 'at least 8' in err.lower()

    def test_no_uppercase(self):
        valid, err = validate_password('password123')
        assert valid is False
        assert 'uppercase' in err.lower()

    def test_no_lowercase(self):
        valid, err = validate_password('PASSWORD123')
        assert valid is False
        assert 'lowercase' in err.lower()

    def test_no_digit(self):
        valid, err = validate_password('Passworddd')
        assert valid is False
        assert 'digit' in err.lower()

    def test_exactly_8_chars(self):
        valid, err = validate_password('Pass1234')
        assert valid is True


class TestUserPasswordMethods:
    def test_set_password_stores_hash(self, app):
        """set_password stores a bcrypt hash, not the plaintext."""
        with app.app_context():
            user = User(username='pwtest', role='viewer')
            user.set_password('MySecret1')
            assert user.password_hash != 'MySecret1'
            assert user.password_hash.startswith('$2b$')

    def test_check_password_valid(self, app):
        """check_password returns True for correct password."""
        with app.app_context():
            user = User(username='pwtest2', role='viewer')
            user.set_password('MySecret1')
            assert user.check_password('MySecret1') is True

    def test_check_password_invalid(self, app):
        """check_password returns False for wrong password."""
        with app.app_context():
            user = User(username='pwtest3', role='viewer')
            user.set_password('MySecret1')
            assert user.check_password('WrongPassword1') is False

    def test_set_password_validated_with_valid_password(self, app):
        """set_password_validated accepts a valid password and stores hash."""
        with app.app_context():
            user = User(username='pwtest4', role='viewer')
            user.set_password_validated('ValidPass1')
            assert user.password_hash.startswith('$2b$')
            assert user.check_password('ValidPass1') is True

    def test_set_password_validated_raises_on_weak(self, app):
        """set_password_validated raises ValueError for weak passwords."""
        with app.app_context():
            user = User(username='pwtest5', role='viewer')
            with pytest.raises(ValueError) as exc:
                user.set_password_validated('short')
            assert 'at least 8' in str(exc.value).lower()

    def test_set_password_validated_raises_no_uppercase(self, app):
        """set_password_validated rejects password without uppercase."""
        with app.app_context():
            user = User(username='pwtest6', role='viewer')
            with pytest.raises(ValueError) as exc:
                user.set_password_validated('password123')
            assert 'uppercase' in str(exc.value).lower()

    def test_set_password_validated_raises_no_lowercase(self, app):
        """set_password_validated rejects password without lowercase."""
        with app.app_context():
            user = User(username='pwtest7', role='viewer')
            with pytest.raises(ValueError) as exc:
                user.set_password_validated('PASSWORD123')
            assert 'lowercase' in str(exc.value).lower()

    def test_set_password_validated_raises_no_digit(self, app):
        """set_password_validated rejects password without digit."""
        with app.app_context():
            user = User(username='pwtest8', role='viewer')
            with pytest.raises(ValueError) as exc:
                user.set_password_validated('Passworddd')
            assert 'digit' in str(exc.value).lower()


class TestUserToDict:
    def test_to_dict_excludes_password_hash(self, app):
        """to_dict() does not expose the password hash."""
        with app.app_context():
            user = User(username='dicttest', role='admin')
            user.set_password('Secret12')
            d = user.to_dict()
            assert 'password_hash' not in d
            assert d['username'] == 'dicttest'
            assert d['role'] == 'admin'

    def test_to_dict_includes_id(self, app):
        """to_dict() includes the user's ID."""
        with app.app_context():
            user = User(username='dicttest2', role='viewer')
            user.set_password('Secret12')
            db.session.add(user)
            db.session.commit()
            d = user.to_dict()
            assert d['id'] is not None
            assert d['id'] > 0


class TestUserModelConstraints:
    def test_default_role_is_viewer(self, app):
        """New users default to viewer role once flushed to DB."""
        with app.app_context():
            user = User(username='defaultrole')
            user.set_password('TestPass1')
            db.session.add(user)
            db.session.flush()
            assert user.role == 'viewer'

    def test_valid_roles_list(self):
        """VALID_ROLES contains expected roles."""
        assert 'admin' in User.VALID_ROLES
        assert 'editor' in User.VALID_ROLES
        assert 'viewer' in User.VALID_ROLES
        assert len(User.VALID_ROLES) == 3
