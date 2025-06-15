import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import datetime
import time

import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor, Json

# Database connection pool
connection_pool = None

def init_db(database_url: Optional[str] = None) -> None:
    """
    Initialize the database connection pool.
    """
    global connection_pool

    if connection_pool is not None:
        logging.info("Database connection pool already initialized")
        return

    # Get database URL from environment variable if not provided
    if database_url is None:
        database_url = os.environ.get('DATABASE_URL')

    if database_url is None:
        logging.warning("DATABASE_URL not set. Database functionality will not be available.")
        return

    try:
        # Create connection pool
        connection_pool = pool.ThreadedConnectionPool(1, 10, database_url)
        logging.info("Database connection pool initialized")

        # Create tables if they don't exist
        create_tables()
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        connection_pool = None

def get_connection():
    """
    Get a connection from the pool.
    """
    if connection_pool is None:
        raise Exception("Database connection pool not initialized")

    return connection_pool.getconn()

def release_connection(conn):
    """
    Release a connection back to the pool.
    """
    if connection_pool is not None:
        connection_pool.putconn(conn)

def create_tables() -> None:
    """
    Create the necessary tables if they don't exist.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            zulip_user_id VARCHAR(255) UNIQUE,
            email VARCHAR(255),
            timezone VARCHAR(50) DEFAULT 'UTC',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """)

        # Create channels table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            zulip_stream_id VARCHAR(255) UNIQUE,
            stream_name VARCHAR(255),
            prompt_time TIME DEFAULT '09:30',
            cutoff_time TIME DEFAULT '12:45',
            reminder_time TIME DEFAULT '11:45',
            timezone VARCHAR(50) DEFAULT 'Africa/Lagos',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """)

        # Create channel_participants table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_participants (
            id SERIAL PRIMARY KEY,
            channel_id INTEGER REFERENCES channels(id),
            zulip_user_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(channel_id, zulip_user_id)
        )
        """)

        # Create standup_responses table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS standup_responses (
            id SERIAL PRIMARY KEY,
            zulip_user_id VARCHAR(255),
            zulip_stream_id VARCHAR(255),
            standup_date DATE,
            responses JSONB,
            submitted_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(zulip_user_id, zulip_stream_id, standup_date)
        )
        """)

        # Create standup_prompts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS standup_prompts (
            id SERIAL PRIMARY KEY,
            zulip_stream_id VARCHAR(255),
            stream_name VARCHAR(255),
            standup_date DATE,
            pending_responses JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(zulip_stream_id, standup_date)
        )
        """)

        conn.commit()
        logging.info("Database tables created successfully")
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error creating tables: {e}")
    finally:
        if conn:
            release_connection(conn)

# User operations
def get_or_create_user(user_id: str, email: str, timezone: str = 'UTC') -> Dict[str, Any]:
    """
    Get a user by ID or create if not exists.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Try to get the user
        cursor.execute(
            "SELECT * FROM users WHERE zulip_user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()

        if user is None:
            # Create the user
            cursor.execute(
                "INSERT INTO users (zulip_user_id, email, timezone) VALUES (%s, %s, %s) RETURNING *",
                (user_id, email, timezone)
            )
            user = cursor.fetchone()
            conn.commit()

        return dict(user)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in get_or_create_user: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def update_user_timezone(user_id: str, timezone: str) -> Dict[str, Any]:
    """
    Update a user's timezone.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            "UPDATE users SET timezone = %s WHERE zulip_user_id = %s RETURNING *",
            (timezone, user_id)
        )
        user = cursor.fetchone()

        if user is None:
            raise Exception(f"User {user_id} not found")

        conn.commit()
        return dict(user)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in update_user_timezone: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_user_timezone(user_id: str) -> str:
    """
    Get a user's timezone.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT timezone FROM users WHERE zulip_user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()

        if result is None:
            return 'UTC'

        return result[0]
    except Exception as e:
        logging.error(f"Error in get_user_timezone: {e}")
        return 'UTC'
    finally:
        if conn:
            release_connection(conn)

# Channel operations
def get_or_create_channel(stream_id: str, stream_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a channel by ID or create if not exists.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Try to get the channel
        cursor.execute(
            "SELECT * FROM channels WHERE zulip_stream_id = %s",
            (stream_id,)
        )
        channel = cursor.fetchone()

        if channel is None:
            # Create the channel
            cursor.execute(
                """
                INSERT INTO channels
                (zulip_stream_id, stream_name, prompt_time, cutoff_time, reminder_time, timezone, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    stream_id,
                    stream_name,
                    config.get('prompt_time', '09:30'),
                    config.get('cutoff_time', '12:45'),
                    config.get('reminder_time', '11:45'),
                    config.get('timezone', 'Africa/Lagos'),
                    config.get('is_active', True)
                )
            )
            channel = cursor.fetchone()
            conn.commit()

        return dict(channel)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in get_or_create_channel: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def update_channel(stream_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a channel's configuration.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Build the update query dynamically based on provided config
        update_fields = []
        params = []

        if 'prompt_time' in config:
            update_fields.append("prompt_time = %s")
            params.append(config['prompt_time'])

        if 'cutoff_time' in config:
            update_fields.append("cutoff_time = %s")
            params.append(config['cutoff_time'])

        if 'reminder_time' in config:
            update_fields.append("reminder_time = %s")
            params.append(config['reminder_time'])

        if 'timezone' in config:
            update_fields.append("timezone = %s")
            params.append(config['timezone'])

        if 'is_active' in config:
            update_fields.append("is_active = %s")
            params.append(config['is_active'])

        if 'stream_name' in config:
            update_fields.append("stream_name = %s")
            params.append(config['stream_name'])

        # Add updated_at timestamp
        update_fields.append("updated_at = NOW()")

        # If no fields to update, return early
        if not update_fields:
            cursor.execute(
                "SELECT * FROM channels WHERE zulip_stream_id = %s",
                (stream_id,)
            )
            channel = cursor.fetchone()
            if channel is None:
                raise Exception(f"Channel {stream_id} not found")
            return dict(channel)

        # Build and execute the query
        query = f"UPDATE channels SET {', '.join(update_fields)} WHERE zulip_stream_id = %s RETURNING *"
        params.append(stream_id)

        cursor.execute(query, params)
        channel = cursor.fetchone()

        if channel is None:
            raise Exception(f"Channel {stream_id} not found")

        conn.commit()
        return dict(channel)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in update_channel: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_channel(stream_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a channel by ID.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            "SELECT * FROM channels WHERE zulip_stream_id = %s",
            (stream_id,)
        )
        channel = cursor.fetchone()

        if channel is None:
            return None

        return dict(channel)
    except Exception as e:
        logging.error(f"Error in get_channel: {e}")
        return None
    finally:
        if conn:
            release_connection(conn)

def get_all_active_channels() -> List[Dict[str, Any]]:
    """
    Get all active channels.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute("SELECT * FROM channels WHERE is_active = TRUE")
        channels = cursor.fetchall()

        return [dict(channel) for channel in channels]
    except Exception as e:
        logging.error(f"Error in get_all_active_channels: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)

# Channel participants operations
def add_channel_participants(channel_id: str, user_ids: List[str]) -> None:
    """
    Add participants to a channel.
    """
    if not user_ids:
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get the channel's database ID
        cursor.execute(
            "SELECT id FROM channels WHERE zulip_stream_id = %s",
            (channel_id,)
        )
        result = cursor.fetchone()

        if result is None:
            raise Exception(f"Channel {channel_id} not found")

        db_channel_id = result[0]

        # Add participants
        for user_id in user_ids:
            cursor.execute(
                """
                INSERT INTO channel_participants (channel_id, zulip_user_id)
                VALUES (%s, %s)
                ON CONFLICT (channel_id, zulip_user_id) DO NOTHING
                """,
                (db_channel_id, user_id)
            )

        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in add_channel_participants: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_channel_participants(channel_id: str) -> List[str]:
    """
    Get all participants for a channel.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get the channel's database ID
        cursor.execute(
            "SELECT id FROM channels WHERE zulip_stream_id = %s",
            (channel_id,)
        )
        result = cursor.fetchone()

        if result is None:
            return []

        db_channel_id = result[0]

        # Get participants
        cursor.execute(
            "SELECT zulip_user_id FROM channel_participants WHERE channel_id = %s",
            (db_channel_id,)
        )

        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Error in get_channel_participants: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)

# Standup prompt operations
def create_standup_prompt(stream_id: str, stream_name: str, date: str, pending_responses: List[str]) -> Dict[str, Any]:
    """
    Create a standup prompt.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            """
            INSERT INTO standup_prompts (zulip_stream_id, stream_name, standup_date, pending_responses)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (zulip_stream_id, standup_date)
            DO UPDATE SET pending_responses = %s, stream_name = %s
            RETURNING *
            """,
            (stream_id, stream_name, date, Json(pending_responses), Json(pending_responses), stream_name)
        )

        prompt = cursor.fetchone()
        conn.commit()

        return dict(prompt)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in create_standup_prompt: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def update_standup_prompt(stream_id: str, date: str, pending_responses: List[str]) -> Dict[str, Any]:
    """
    Update a standup prompt's pending responses.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            """
            UPDATE standup_prompts
            SET pending_responses = %s
            WHERE zulip_stream_id = %s AND standup_date = %s
            RETURNING *
            """,
            (Json(pending_responses), stream_id, date)
        )

        prompt = cursor.fetchone()

        if prompt is None:
            raise Exception(f"Standup prompt for stream {stream_id} on {date} not found")

        conn.commit()
        return dict(prompt)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in update_standup_prompt: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_standup_prompt(stream_id: str, date: str) -> Optional[Dict[str, Any]]:
    """
    Get a standup prompt.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            """
            SELECT * FROM standup_prompts
            WHERE zulip_stream_id = %s AND standup_date = %s
            """,
            (stream_id, date)
        )

        prompt = cursor.fetchone()

        if prompt is None:
            return None

        return dict(prompt)
    except Exception as e:
        logging.error(f"Error in get_standup_prompt: {e}")
        return None
    finally:
        if conn:
            release_connection(conn)

def get_all_standup_prompts_for_date(date: str) -> List[Dict[str, Any]]:
    """
    Get all standup prompts for a specific date.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            "SELECT * FROM standup_prompts WHERE standup_date = %s",
            (date,)
        )

        prompts = cursor.fetchall()
        return [dict(prompt) for prompt in prompts]
    except Exception as e:
        logging.error(f"Error in get_all_standup_prompts_for_date: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)

# Standup response operations
def create_or_update_standup_response(
    user_id: str,
    stream_id: str,
    date: str,
    response_text: str
) -> Dict[str, Any]:
    """
    Create or update a standup response.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Check if response exists
        cursor.execute(
            """
            SELECT * FROM standup_responses
            WHERE zulip_user_id = %s AND zulip_stream_id = %s AND standup_date = %s
            """,
            (user_id, stream_id, date)
        )

        existing = cursor.fetchone()

        if existing is None:
            # Create new response
            cursor.execute(
                """
                INSERT INTO standup_responses
                (zulip_user_id, zulip_stream_id, standup_date, responses)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, stream_id, date, Json([response_text]))
            )
        else:
            # Update existing response
            responses = existing['responses']
            responses.append(response_text)

            cursor.execute(
                """
                UPDATE standup_responses
                SET responses = %s, submitted_at = NOW()
                WHERE zulip_user_id = %s AND zulip_stream_id = %s AND standup_date = %s
                RETURNING *
                """,
                (Json(responses), user_id, stream_id, date)
            )

        response = cursor.fetchone()
        conn.commit()

        return dict(response)
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in create_or_update_standup_response: {e}")
        raise
    finally:
        if conn:
            release_connection(conn)

def get_standup_response(user_id: str, stream_id: str, date: str) -> Optional[Dict[str, Any]]:
    """
    Get a standup response.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            """
            SELECT * FROM standup_responses
            WHERE zulip_user_id = %s AND zulip_stream_id = %s AND standup_date = %s
            """,
            (user_id, stream_id, date)
        )

        response = cursor.fetchone()

        if response is None:
            return None

        return dict(response)
    except Exception as e:
        logging.error(f"Error in get_standup_response: {e}")
        return None
    finally:
        if conn:
            release_connection(conn)

def get_all_standup_responses_for_stream_and_date(stream_id: str, date: str) -> List[Dict[str, Any]]:
    """
    Get all standup responses for a specific stream and date.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute(
            """
            SELECT * FROM standup_responses
            WHERE zulip_stream_id = %s AND standup_date = %s
            """,
            (stream_id, date)
        )

        responses = cursor.fetchall()
        return [dict(response) for response in responses]
    except Exception as e:
        logging.error(f"Error in get_all_standup_responses_for_stream_and_date: {e}")
        return []
    finally:
        if conn:
            release_connection(conn)
