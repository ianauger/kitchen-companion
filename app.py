#!/usr/bin/env python3
"""
Kitchen Companion - Digital Cookbook Application

Entry point for running the Flask application.
"""
import os
from app import create_app, db
from app.models import Recipe, Tag

# Create application instance
app = create_app()


@app.shell_context_processor
def make_shell_context():
    """Enable Flask shell with pre-imported models."""
    return {'db': db, 'Recipe': Recipe, 'Tag': Tag}


if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
