#!/usr/bin/env python3
"""
Standalone database initialization script.
This script initializes the SQLite database without relying on package imports.
"""

import os
import sqlite3
import logging
from pathlib import Path

def get_db_path() -> str:
    """Get the database file path."""
    # Check for DATABASE_URL first (if it's SQLite)
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('sqlite:///'):
        db_path = database_url.replace('sqlite:///', '/')
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path
    
    # Check for legacy SQLITE_DB_PATH
    db_path = os.environ.get('SQLITE_DB_PATH')
    if db_path:
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Default to data directory
    data_dir = Path('/app/data')
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / 'standup.db')

def create_tables(conn: sqlite3.Connection) -> None:
    """Create the necessary tables if they don't exist."""
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zulip_user_id TEXT UNIQUE NOT NULL,
        email TEXT,
        timezone TEXT DEFAULT 'UTC',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create channels table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zulip_stream_id TEXT UNIQUE NOT NULL,
        stream_name TEXT,
        prompt_time TEXT DEFAULT '09:30',
        cutoff_time TEXT DEFAULT '12:45',
        reminder_time TEXT DEFAULT '11:45',
        timezone TEXT DEFAULT 'Africa/Lagos',
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create channel_participants table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channel_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER,
        zulip_user_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
        UNIQUE(channel_id, zulip_user_id)
    )
    """)

    # Create standup_responses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS standup_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zulip_user_id TEXT,
        zulip_stream_id TEXT,
        standup_date DATE,
        responses TEXT,  -- JSON string
        completed BOOLEAN DEFAULT 0,
        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(zulip_user_id, zulip_stream_id, standup_date)
    )
    """)

    # Create standup_prompts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS standup_prompts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zulip_stream_id TEXT,
        stream_name TEXT,
        standup_date DATE,
        pending_responses TEXT,  -- JSON string
        prompt_sent BOOLEAN DEFAULT 0,
        reminder_sent BOOLEAN DEFAULT 0,
        summary_sent BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(zulip_stream_id, standup_date)
    )
    """)

    # Create indexes for better performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_channels_active ON channels(is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_responses_date ON standup_responses(standup_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompts_date ON standup_prompts(standup_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_channel ON channel_participants(channel_id)")

    conn.commit()
    print("Database tables created successfully")

def init_db() -> None:
    """Initialize the SQLite database and create tables."""
    try:
        db_path = get_db_path()
        print(f"Initializing database at: {db_path}")
        
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        
        # Enable foreign keys and WAL mode for better concurrency
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.commit()
        
        create_tables(conn)
        conn.close()
        
        print("SQLite database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing SQLite database: {e}")
        raise

if __name__ == "__main__":
    init_db()
