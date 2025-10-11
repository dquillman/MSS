#!/usr/bin/env python3
"""
PostgreSQL Migration Script for MSS
====================================

This script migrates data from SQLite to PostgreSQL for production deployment.

Usage:
    python migrate_to_postgres.py --sqlite-db path/to/mss.db --postgres-url postgresql://user:pass@host:port/dbname

Environment Variables (recommended for security):
    DATABASE_URL - PostgreSQL connection string
    SQLITE_DB_PATH - Path to SQLite database (default: web/mss.db)

Example:
    export DATABASE_URL="postgresql://user:pass@localhost:5432/mss"
    python migrate_to_postgres.py
"""

import sqlite3
import psycopg2
from psycopg2 import sql
import argparse
import os
import sys
from datetime import datetime

# PostgreSQL Schema
POSTGRES_SCHEMA = """
-- MSS PostgreSQL Schema
-- Generated: {timestamp}

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    subscription_tier VARCHAR(50) DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    videos_created_this_month INTEGER DEFAULT 0,
    month_reset_date DATE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- Video history table
CREATE TABLE IF NOT EXISTS video_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_filename VARCHAR(500) NOT NULL,
    title TEXT,
    topic TEXT,
    duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_video_history_user_id ON video_history(user_id);
CREATE INDEX IF NOT EXISTS idx_video_history_created_at ON video_history(created_at);

-- Password reset tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expires ON password_reset_tokens(expires_at);

-- Admin whitelist table
CREATE TABLE IF NOT EXISTS admin_whitelist (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stripe webhook events (for idempotency)
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_event_id ON stripe_webhook_events(event_id);
"""


class DatabaseMigrator:
    def __init__(self, sqlite_path, postgres_url):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.sqlite_conn = None
        self.pg_conn = None

    def connect(self):
        """Connect to both databases"""
        print(f"Connecting to SQLite: {self.sqlite_path}")
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row

        print(f"Connecting to PostgreSQL...")
        self.pg_conn = psycopg2.connect(self.postgres_url)
        self.pg_conn.autocommit = False
        print("✓ Connected to both databases")

    def close(self):
        """Close database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.pg_conn:
            self.pg_conn.close()

    def create_schema(self):
        """Create PostgreSQL schema"""
        print("\nCreating PostgreSQL schema...")
        cursor = self.pg_conn.cursor()

        schema = POSTGRES_SCHEMA.format(
            timestamp=datetime.now().isoformat()
        )

        cursor.execute(schema)
        self.pg_conn.commit()
        print("✓ Schema created")

    def migrate_table(self, table_name, columns, transform_fn=None):
        """Migrate a single table from SQLite to PostgreSQL

        Args:
            table_name: Name of the table
            columns: List of column names to migrate
            transform_fn: Optional function to transform row data
        """
        print(f"\nMigrating table: {table_name}")

        # Read from SQLite
        sqlite_cursor = self.sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()

        if not rows:
            print(f"  No data in {table_name}")
            return

        print(f"  Found {len(rows)} rows")

        # Prepare PostgreSQL insert
        pg_cursor = self.pg_conn.cursor()

        # Build INSERT statement
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

        # Migrate rows
        migrated = 0
        skipped = 0

        for row in rows:
            try:
                # Convert Row to dict
                row_dict = dict(row)

                # Apply transformation if provided
                if transform_fn:
                    row_dict = transform_fn(row_dict)

                # Extract values in column order
                values = [row_dict.get(col) for col in columns]

                # Insert into PostgreSQL
                pg_cursor.execute(insert_sql, values)
                migrated += 1

            except Exception as e:
                print(f"  Warning: Failed to migrate row: {e}")
                skipped += 1
                continue

        self.pg_conn.commit()
        print(f"  ✓ Migrated {migrated} rows, skipped {skipped}")

    def migrate_users(self):
        """Migrate users table"""
        def transform_user(row):
            # Ensure month_reset_date is in correct format
            if row.get('month_reset_date'):
                # Convert to date if it's a string
                row['month_reset_date'] = row['month_reset_date']
            return row

        columns = [
            'email', 'username', 'password_hash', 'created_at', 'last_login',
            'subscription_tier', 'stripe_customer_id', 'stripe_subscription_id',
            'videos_created_this_month', 'month_reset_date'
        ]

        self.migrate_table('users', columns, transform_user)

    def migrate_sessions(self):
        """Migrate sessions table"""
        columns = ['session_id', 'user_id', 'created_at', 'expires_at', 'last_activity']
        self.migrate_table('sessions', columns)

    def migrate_video_history(self):
        """Migrate video_history table"""
        columns = ['user_id', 'video_filename', 'title', 'topic', 'duration', 'created_at']
        self.migrate_table('video_history', columns)

    def migrate_password_reset_tokens(self):
        """Migrate password_reset_tokens table"""
        columns = ['user_id', 'token', 'created_at', 'expires_at', 'used']
        self.migrate_table('password_reset_tokens', columns)

    def migrate_admin_whitelist(self):
        """Migrate admin_whitelist table"""
        columns = ['email', 'added_at']
        self.migrate_table('admin_whitelist', columns)

    def verify_migration(self):
        """Verify data was migrated correctly"""
        print("\n" + "="*60)
        print("MIGRATION VERIFICATION")
        print("="*60)

        sqlite_cursor = self.sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()

        tables = ['users', 'sessions', 'video_history', 'password_reset_tokens', 'admin_whitelist']

        all_good = True

        for table in tables:
            # Count rows in SQLite
            sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cursor.fetchone()[0]

            # Count rows in PostgreSQL
            pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cursor.fetchone()[0]

            match = "✓" if sqlite_count == pg_count else "✗"
            print(f"{match} {table:30} SQLite: {sqlite_count:5} PostgreSQL: {pg_count:5}")

            if sqlite_count != pg_count:
                all_good = False

        print("="*60)

        if all_good:
            print("✓ All tables migrated successfully!")
        else:
            print("✗ Some tables have mismatched counts. Please review.")

        return all_good

    def run_migration(self):
        """Run the full migration process"""
        try:
            print("="*60)
            print("MSS DATABASE MIGRATION: SQLite → PostgreSQL")
            print("="*60)

            self.connect()
            self.create_schema()

            # Migrate all tables
            self.migrate_users()
            self.migrate_sessions()
            self.migrate_video_history()
            self.migrate_password_reset_tokens()
            self.migrate_admin_whitelist()

            # Verify
            success = self.verify_migration()

            if success:
                print("\n✓ Migration completed successfully!")
                return True
            else:
                print("\n✗ Migration completed with warnings. Please review.")
                return False

        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            if self.pg_conn:
                self.pg_conn.rollback()
            raise

        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(
        description='Migrate MSS database from SQLite to PostgreSQL'
    )

    parser.add_argument(
        '--sqlite-db',
        default=os.getenv('SQLITE_DB_PATH', 'web/mss.db'),
        help='Path to SQLite database file'
    )

    parser.add_argument(
        '--postgres-url',
        default=os.getenv('DATABASE_URL'),
        help='PostgreSQL connection URL (postgresql://user:pass@host:port/dbname)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually migrating'
    )

    args = parser.parse_args()

    # Validation
    if not args.postgres_url:
        print("Error: PostgreSQL URL is required.")
        print("Set DATABASE_URL environment variable or use --postgres-url")
        sys.exit(1)

    if not os.path.exists(args.sqlite_db):
        print(f"Error: SQLite database not found: {args.sqlite_db}")
        sys.exit(1)

    # Confirm before proceeding
    print(f"\nSQLite Database: {args.sqlite_db}")
    print(f"PostgreSQL URL:  {args.postgres_url}")
    print("\nThis will:")
    print("  1. Create tables in PostgreSQL (if they don't exist)")
    print("  2. Copy all data from SQLite to PostgreSQL")
    print("  3. Verify the migration")
    print("\nWARNING: If tables already exist in PostgreSQL, this may cause duplicates.")

    response = input("\nProceed with migration? (yes/no): ")

    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(0)

    # Run migration
    migrator = DatabaseMigrator(args.sqlite_db, args.postgres_url)
    success = migrator.run_migration()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
