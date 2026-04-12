#!/usr/bin/env python3
"""Management script for Kitchen Companion database migrations."""

import os
import sys

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from flask_migrate import Migrate, init, migrate, upgrade, downgrade, current, history, stamp

# Create app instance
app = create_app(os.getenv('FLASK_CONFIG', 'default'))
migrate_ext = Migrate(app, db)


def print_help():
    """Print usage instructions."""
    print("""
Kitchen Companion Database Management

Usage: python manage.py <command>

Commands:
  init              Initialize migrations repository
  migrate          Create a new migration
  upgrade          Run migrations to upgrade database
  downgrade        Rollback migrations
  current          Show current migration version
  history          Show migration history
  stamp            Stamp the database with a specific revision
  create_db        Create database tables (without migrations)
  drop_db          Drop all database tables
  recreate_db      Recreate database (drop and create)

Examples:
  python manage.py init
  python manage.py migrate -m "Add indexes"
  python manage.py upgrade
""")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    with app.app_context():
        if command == 'init':
            init(directory='migrations')
        elif command == 'migrate':
            # Handle -m flag for message
            message = None
            if '-m' in args:
                idx = args.index('-m')
                if idx + 1 < len(args):
                    message = args[idx + 1]
                    args = args[:idx] + args[idx+2:]
            migrate(directory='migrations', message=message)
        elif command == 'upgrade':
            revision = args[0] if args else 'head'
            upgrade(directory='migrations', revision=revision)
        elif command == 'downgrade':
            revision = args[0] if args else '-1'
            downgrade(directory='migrations', revision=revision)
        elif command == 'current':
            current(directory='migrations')
        elif command == 'history':
            history(directory='migrations')
        elif command == 'stamp':
            revision = args[0] if args else 'head'
            stamp(directory='migrations', revision=revision)
        elif command == 'create_db':
            db.create_all()
            print("Database tables created.")
        elif command == 'drop_db':
            if input("Are you sure you want to drop all tables? (yes/no): ") == "yes":
                db.drop_all()
                print("Database tables dropped.")
            else:
                print("Cancelled.")
        elif command == 'recreate_db':
            if input("Are you sure you want to recreate the database? (yes/no): ") == "yes":
                db.drop_all()
                db.create_all()
                print("Database recreated.")
            else:
                print("Cancelled.")
        else:
            print(f"Unknown command: {command}")
            print_help()
            sys.exit(1)
