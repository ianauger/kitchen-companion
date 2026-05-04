#!/usr/bin/env python3
"""Bootstrap the first admin user for Kitchen Companion.

Usage:
    python scripts/bootstrap_admin.py [--username NAME] [--password PASS]

If no arguments are provided, prompts interactively.
Set environment variables KITCHEN_COMPANION_USERNAME / KITCHEN_COMPANION_PASSWORD
to skip the prompt entirely (useful for Docker entrypoints).
"""
import os
import sys
import argparse

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.auth import User


def bootstrap(username, password):
    """Create the admin user if no users exist yet."""
    app = create_app()
    with app.app_context():
        # Only bootstrap if this is a fresh database
        existing = User.query.first()
        if existing:
            print(f"Users already exist (first user: '{existing.username}').")
            print("Use the register API or ask an admin to create your account.")
            return False

        user = User(username=username, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"✅ Admin user created: {username} (role: admin)")
        print(f"   Login: POST /api/auth/login with username='{username}'")
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bootstrap admin user')
    parser.add_argument('--username', help='Admin username')
    parser.add_argument('--password', help='Admin password (min 8 chars)')
    args = parser.parse_args()

    username = args.username or os.environ.get('KITCHEN_COMPANION_USERNAME')
    password = args.password or os.environ.get('KITCHEN_COMPANION_PASSWORD')

    if not username:
        username = input('Admin username: ').strip()

    if not password:
        import getpass
        password = getpass.getpass('Admin password (min 8 chars): ')

    if not username or len(username) < 3:
        print('Error: Username must be at least 3 characters')
        sys.exit(1)

    if not password or len(password) < 8:
        print('Error: Password must be at least 8 characters')
        sys.exit(1)

    success = bootstrap(username, password)
    sys.exit(0 if success else 1)
