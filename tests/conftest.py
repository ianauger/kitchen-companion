import pytest
from app import create_app, db
from app.models import Recipe, Tag, Note
from config import DevelopmentConfig

@pytest.fixture
def app():
    app = create_app('development')
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
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
