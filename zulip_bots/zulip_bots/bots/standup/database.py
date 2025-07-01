"""
SQLite database operations for the Standup Bot.
Optimized for production use with proper connection handling and thread safety.
"""

import os
import logging
import sqlite3
import json
import threading
from typing import Any, Dict, List, Optional, Tuple
import datetime
import time
from pathlib import Path
from contextlib import contextmanager

# Thread-local storage for database connections
_local = threading.local()
_db_lock = threading.Lock()

def get_db_path() -> str:
    """
    Get the database file path. Uses environment variable or default location.
    """
    db_path = os.environ.get('SQLITE_DB_PATH')
    if db_path:
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Default to data directory in the bot's folder
    bot_dir = Path(__file__).parent
    data_dir = bot_dir / 'data'
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / 'standup.db')

@contextmanager
def get_db_connection():
    """
    Context manager for database connections with proper cleanup.
    """
    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        # Enable foreign keys and WAL mode for better concurrency
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.commit()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_db() -> None:
    """
    Initialize the SQLite database and create tables.
    """
    try:
        with get_db_connection() as conn:
            create_tables(conn)
        logging.info("SQLite database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing SQLite database: {e}")
        raise

def create_tables(conn: sqlite3.Connection) -> None:
    """
    Create the necessary tables if they don't exist.
    """
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
    logging.info("Database tables created successfully")

# User operations
def get_or_create_user(user_id: str, email: str, timezone: str = 'UTC') -> Dict[str, Any]:
    """Get a user by ID or create if not exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Try to get the user
        cursor.execute("SELECT * FROM users WHERE zulip_user_id = ?", (user_id,))
        user = cursor.fetchone()

        if user is None:
            # Create the user
            cursor.execute(
                "INSERT INTO users (zulip_user_id, email, timezone) VALUES (?, ?, ?)",
                (user_id, email, timezone)
            )
            conn.commit()

            # Get the created user
            cursor.execute("SELECT * FROM users WHERE zulip_user_id = ?", (user_id,))
            user = cursor.fetchone()

        return dict(user)

def update_user_timezone(user_id: str, timezone: str) -> Dict[str, Any]:
    """Update a user's timezone."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET timezone = ?, updated_at = CURRENT_TIMESTAMP WHERE zulip_user_id = ?",
            (timezone, user_id)
        )

        if cursor.rowcount == 0:
            raise Exception(f"User {user_id} not found")

        conn.commit()

        # Get the updated user
        cursor.execute("SELECT * FROM users WHERE zulip_user_id = ?", (user_id,))
        return dict(cursor.fetchone())

def get_user_timezone(user_id: str) -> str:
    """Get a user's timezone."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timezone FROM users WHERE zulip_user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 'UTC'

# Channel operations
def get_or_create_channel(stream_id: str, stream_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Get a channel by ID or create if not exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Try to get the channel
        cursor.execute("SELECT * FROM channels WHERE zulip_stream_id = ?", (stream_id,))
        channel = cursor.fetchone()

        if channel is None:
            # Create the channel
            cursor.execute(
                """
                INSERT INTO channels
                (zulip_stream_id, stream_name, prompt_time, cutoff_time, reminder_time, timezone, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stream_id, stream_name,
                    config.get('prompt_time', '09:30'),
                    config.get('cutoff_time', '12:45'),
                    config.get('reminder_time', '11:45'),
                    config.get('timezone', 'Africa/Lagos'),
                    config.get('is_active', True)
                )
            )
            conn.commit()

            # Get the created channel
            cursor.execute("SELECT * FROM channels WHERE zulip_stream_id = ?", (stream_id,))
            channel = cursor.fetchone()

        return dict(channel)

def update_channel(stream_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Update a channel's configuration."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build the update query dynamically
        update_fields = []
        params = []

        for field in ['prompt_time', 'cutoff_time', 'reminder_time', 'timezone', 'is_active', 'stream_name']:
            if field in config:
                update_fields.append(f"{field} = ?")
                params.append(config[field])

        # Add updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        if len(update_fields) == 1:  # Only updated_at
            cursor.execute("SELECT * FROM channels WHERE zulip_stream_id = ?", (stream_id,))
            channel = cursor.fetchone()
            if channel is None:
                raise Exception(f"Channel {stream_id} not found")
            return dict(channel)

        # Build and execute the query
        query = f"UPDATE channels SET {', '.join(update_fields)} WHERE zulip_stream_id = ?"
        params.append(stream_id)

        cursor.execute(query, params)

        if cursor.rowcount == 0:
            raise Exception(f"Channel {stream_id} not found")

        conn.commit()

        # Get the updated channel
        cursor.execute("SELECT * FROM channels WHERE zulip_stream_id = ?", (stream_id,))
        return dict(cursor.fetchone())

def get_channel(stream_id: str) -> Optional[Dict[str, Any]]:
    """Get a channel by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE zulip_stream_id = ?", (stream_id,))
        channel = cursor.fetchone()
        return dict(channel) if channel else None

def get_all_active_channels() -> List[Dict[str, Any]]:
    """Get all active channels."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE is_active = 1")
        return [dict(channel) for channel in cursor.fetchall()]

# Channel participants operations
def add_channel_participants(channel_id: str, user_ids: List[str]) -> None:
    """Add participants to a channel."""
    if not user_ids:
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get the channel's database ID
        cursor.execute("SELECT id FROM channels WHERE zulip_stream_id = ?", (channel_id,))
        result = cursor.fetchone()

        if result is None:
            raise Exception(f"Channel {channel_id} not found")

        db_channel_id = result[0]

        # Clear existing participants first
        cursor.execute("DELETE FROM channel_participants WHERE channel_id = ?", (db_channel_id,))

        # Add new participants
        for user_id in user_ids:
            cursor.execute(
                "INSERT INTO channel_participants (channel_id, zulip_user_id) VALUES (?, ?)",
                (db_channel_id, user_id)
            )

        conn.commit()

def get_channel_participants(channel_id: str) -> List[str]:
    """Get all participants for a channel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Get the channel's database ID
        cursor.execute("SELECT id FROM channels WHERE zulip_stream_id = ?", (channel_id,))
        result = cursor.fetchone()

        if result is None:
            return []

        db_channel_id = result[0]

        # Get participants
        cursor.execute(
            "SELECT zulip_user_id FROM channel_participants WHERE channel_id = ?",
            (db_channel_id,)
        )

        return [row[0] for row in cursor.fetchall()]

# Standup prompt operations
def create_standup_prompt(stream_id: str, stream_name: str, date: str, pending_responses: List[str]) -> Dict[str, Any]:
    """Create a standup prompt."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        pending_responses_json = json.dumps(pending_responses)

        cursor.execute(
            """
            INSERT OR REPLACE INTO standup_prompts
            (zulip_stream_id, stream_name, standup_date, pending_responses, prompt_sent, updated_at)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """,
            (stream_id, stream_name, date, pending_responses_json)
        )

        conn.commit()

        # Get the created/updated prompt
        cursor.execute(
            "SELECT * FROM standup_prompts WHERE zulip_stream_id = ? AND standup_date = ?",
            (stream_id, date)
        )

        prompt = cursor.fetchone()
        prompt_dict = dict(prompt)
        prompt_dict['pending_responses'] = json.loads(prompt_dict['pending_responses'])

        return prompt_dict

def update_standup_prompt(stream_id: str, date: str, pending_responses: List[str]) -> Dict[str, Any]:
    """Update a standup prompt's pending responses."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        pending_responses_json = json.dumps(pending_responses)

        cursor.execute(
            """
            UPDATE standup_prompts
            SET pending_responses = ?, updated_at = CURRENT_TIMESTAMP
            WHERE zulip_stream_id = ? AND standup_date = ?
            """,
            (pending_responses_json, stream_id, date)
        )

        if cursor.rowcount == 0:
            raise Exception(f"Standup prompt for stream {stream_id} on {date} not found")

        conn.commit()

        # Get the updated prompt
        cursor.execute(
            "SELECT * FROM standup_prompts WHERE zulip_stream_id = ? AND standup_date = ?",
            (stream_id, date)
        )

        prompt = cursor.fetchone()
        prompt_dict = dict(prompt)
        prompt_dict['pending_responses'] = json.loads(prompt_dict['pending_responses'])

        return prompt_dict

def get_standup_prompt(stream_id: str, date: str) -> Optional[Dict[str, Any]]:
    """Get a standup prompt."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM standup_prompts WHERE zulip_stream_id = ? AND standup_date = ?",
            (stream_id, date)
        )

        prompt = cursor.fetchone()
        if prompt is None:
            return None

        prompt_dict = dict(prompt)
        prompt_dict['pending_responses'] = json.loads(prompt_dict['pending_responses'])
        return prompt_dict

def get_all_standup_prompts_for_date(date: str) -> List[Dict[str, Any]]:
    """Get all standup prompts for a specific date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM standup_prompts WHERE standup_date = ?", (date,))

        result = []
        for prompt in cursor.fetchall():
            prompt_dict = dict(prompt)
            prompt_dict['pending_responses'] = json.loads(prompt_dict['pending_responses'])
            result.append(prompt_dict)

        return result

def mark_reminder_sent(stream_id: str, date: str) -> None:
    """Mark that reminder has been sent for a prompt."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE standup_prompts
            SET reminder_sent = 1, updated_at = CURRENT_TIMESTAMP
            WHERE zulip_stream_id = ? AND standup_date = ?
            """,
            (stream_id, date)
        )
        conn.commit()

def mark_summary_sent(stream_id: str, date: str) -> None:
    """Mark that summary has been sent for a prompt."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE standup_prompts
            SET summary_sent = 1, updated_at = CURRENT_TIMESTAMP
            WHERE zulip_stream_id = ? AND standup_date = ?
            """,
            (stream_id, date)
        )
        conn.commit()

# Standup response operations
def create_or_update_standup_response(
    user_id: str, stream_id: str, date: str, response_text: str
) -> Dict[str, Any]:
    """Create or update a standup response."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if response exists
        cursor.execute(
            "SELECT * FROM standup_responses WHERE zulip_user_id = ? AND zulip_stream_id = ? AND standup_date = ?",
            (user_id, stream_id, date)
        )

        existing = cursor.fetchone()

        if existing is None:
            # Create new response
            responses_json = json.dumps([response_text])
            cursor.execute(
                """
                INSERT INTO standup_responses
                (zulip_user_id, zulip_stream_id, standup_date, responses, completed)
                VALUES (?, ?, ?, ?, 0)
                """,
                (user_id, stream_id, date, responses_json)
            )
        else:
            # Update existing response
            responses = json.loads(existing['responses'])
            responses.append(response_text)
            completed = len(responses) >= 3  # Mark completed after 3 responses
            responses_json = json.dumps(responses)

            cursor.execute(
                """
                UPDATE standup_responses
                SET responses = ?, completed = ?, updated_at = CURRENT_TIMESTAMP
                WHERE zulip_user_id = ? AND zulip_stream_id = ? AND standup_date = ?
                """,
                (responses_json, completed, user_id, stream_id, date)
            )

        conn.commit()

        # Get the created/updated response
        cursor.execute(
            "SELECT * FROM standup_responses WHERE zulip_user_id = ? AND zulip_stream_id = ? AND standup_date = ?",
            (user_id, stream_id, date)
        )

        response = cursor.fetchone()
        response_dict = dict(response)
        response_dict['responses'] = json.loads(response_dict['responses'])

        return response_dict

def get_standup_response(user_id: str, stream_id: str, date: str) -> Optional[Dict[str, Any]]:
    """Get a standup response."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM standup_responses WHERE zulip_user_id = ? AND zulip_stream_id = ? AND standup_date = ?",
            (user_id, stream_id, date)
        )

        response = cursor.fetchone()
        if response is None:
            return None

        response_dict = dict(response)
        response_dict['responses'] = json.loads(response_dict['responses'])
        return response_dict

def get_all_standup_responses_for_stream_and_date(stream_id: str, date: str) -> List[Dict[str, Any]]:
    """Get all standup responses for a specific stream and date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sr.*, u.email, u.zulip_user_id as user_id
            FROM standup_responses sr
            LEFT JOIN users u ON sr.zulip_user_id = u.zulip_user_id
            WHERE sr.zulip_stream_id = ? AND sr.standup_date = ?
            """,
            (stream_id, date)
        )

        result = []
        for response in cursor.fetchall():
            response_dict = dict(response)
            response_dict['responses'] = json.loads(response_dict['responses'])
            result.append(response_dict)

        return result

def get_incomplete_responses_for_date(stream_id: str, date: str) -> List[str]:
    """Get user IDs who haven't completed their standup for a given date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT zulip_user_id FROM standup_responses
            WHERE zulip_stream_id = ? AND standup_date = ? AND completed = 0
            """,
            (stream_id, date)
        )
        return [row[0] for row in cursor.fetchall()]

# Historical data functions
def get_standup_history_for_stream(stream_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Get historical standup data for a stream."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT standup_date, COUNT(*) as response_count,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_count
            FROM standup_responses
            WHERE zulip_stream_id = ?
            GROUP BY standup_date
            ORDER BY standup_date DESC
            LIMIT ?
            """,
            (stream_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def search_standup_responses(stream_id: str, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search standup responses for a specific term."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sr.*, u.email, c.stream_name
            FROM standup_responses sr
            LEFT JOIN users u ON sr.zulip_user_id = u.zulip_user_id
            LEFT JOIN channels c ON sr.zulip_stream_id = c.zulip_stream_id
            WHERE sr.zulip_stream_id = ? AND sr.responses LIKE ?
            ORDER BY sr.standup_date DESC, sr.updated_at DESC
            LIMIT ?
            """,
            (stream_id, f'%{search_term}%', limit)
        )

        results = []
        for row in cursor.fetchall():
            response_dict = dict(row)
            response_dict['responses'] = json.loads(response_dict['responses'])
            results.append(response_dict)

        return results

def cleanup_old_data(days_to_keep: int = 90) -> None:
    """Clean up old standup data to keep database size manageable."""
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_to_keep)).strftime('%Y-%m-%d')

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Delete old responses
        cursor.execute("DELETE FROM standup_responses WHERE standup_date < ?", (cutoff_date,))
        responses_deleted = cursor.rowcount

        # Delete old prompts
        cursor.execute("DELETE FROM standup_prompts WHERE standup_date < ?", (cutoff_date,))
        prompts_deleted = cursor.rowcount

        conn.commit()

        if responses_deleted > 0 or prompts_deleted > 0:
            logging.info(f"Cleaned up old data: {responses_deleted} responses, {prompts_deleted} prompts deleted")
