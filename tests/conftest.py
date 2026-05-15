import pytest
import os

os.environ['FLASK_TESTING'] = '1'  # Prevent seed_default_store from running during create_app

from app import create_app, db
from app.models import Recipe, Tag, Note
from app.auth import User
from config import DevelopmentConfig


@pytest.fixture
def app():
    app = create_app('development')
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    """Create an admin user and return credentials."""
    with app.app_context():
        user = User(username='testadmin', role='admin')
        user.set_password('Test1234!')
        db.session.add(user)
        db.session.commit()
        return {'username': 'testadmin', 'password': 'Test1234!', 'id': user.id}


@pytest.fixture
def editor_user(app):
    """Create an editor user and return credentials."""
    with app.app_context():
        user = User(username='testeditor', role='editor')
        user.set_password('Test1234!')
        db.session.add(user)
        db.session.commit()
        return {'username': 'testeditor', 'password': 'Test1234!', 'id': user.id}


@pytest.fixture
def auth_client(client, admin_user):
    """Authenticated test client (admin session)."""
    client.post('/api/auth/signin', data={
        'username': admin_user['username'],
        'password': admin_user['password']
    })
    return client


@pytest.fixture
def editor_client(client, editor_user):
    """Authenticated test client (editor session)."""
    client.post('/api/auth/signin', data={
        'username': editor_user['username'],
        'password': editor_user['password']
    })
    return client


@pytest.fixture
def db_session(app):
    """Database session fixture for tests that need database access."""
    with app.app_context():
        yield db.session
        db.session.rollback()

@pytest.fixture
def sample_recipe(app):
    with app.app_context():
        recipe = Recipe(
            title="Test Pasta",
            instructions="Boil water, add pasta, eat.",
            difficulty="easy",
            prep_time=10,
            cooking_time=10
        )
        db.session.add(recipe)
        db.session.commit()
        # Return the ID instead of the object to avoid detachment issues
        return recipe.id
