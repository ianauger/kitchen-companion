#!/usr/bin/env python3
"""
Kitchen Companion - Digital Cookbook Application

Entry point for running the Flask application.
"""
from app import create_app, db
from app.models import Recipe, Tag

# Create application instance
app = create_app()


@app.shell_context_processor
def make_shell_context():
    """Enable Flask shell with pre-imported models."""
    return {'db': db, 'Recipe': Recipe, 'Tag': Tag}


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)