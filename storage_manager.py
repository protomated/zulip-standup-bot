import json
import logging
import os
from typing import Dict, Any, Optional, List, Set, ContextManager
from contextlib import contextmanager
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, JSON, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

# Define the SQLAlchemy Base
Base = declarative_base()

# Define the database schema
class Standup(Base):
    """Standup meeting model"""
    __tablename__ = 'standups'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    creator_id = Column(Integer, nullable=False)
    team_stream = Column(String, nullable=False)
    schedule = Column(JSON, nullable=False)
    questions = Column(JSON, nullable=False)
    participants = Column(JSON, nullable=False)
    timezone_handling = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(String, nullable=False)
    team_tag = Column(String, nullable=True)
    project_tag = Column(String, nullable=True)
    permissions = Column(JSON, nullable=True)
    question_templates = Column(JSON, nullable=True)

class Response(Base):
    """User response to a standup"""
    __tablename__ = 'responses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    standup_id = Column(String, ForeignKey('standups.id'), nullable=False)
    date = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    responses = Column(JSON, nullable=False)
    timestamp = Column(String, nullable=False)

    # Composite unique constraint to ensure one response per user per standup per date
    __table_args__ = (sa.UniqueConstraint('standup_id', 'date', 'user_id', name='_standup_date_user_uc'),)

class Report(Base):
    """Standup report"""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    standup_id = Column(String, ForeignKey('standups.id'), nullable=False)
    date = Column(String, nullable=False)
    participation_rate = Column(sa.Float, nullable=True)
    ai_summary = Column(String, nullable=True)
    report_data = Column(JSON, nullable=False)

    # Composite unique constraint to ensure one report per standup per date
    __table_args__ = (sa.UniqueConstraint('standup_id', 'date', name='_standup_date_uc'),)

class UserPreference(Base):
    """User preferences"""
    __tablename__ = 'user_preferences'

    user_id = Column(String, primary_key=True)
    active_standup = Column(String, nullable=True)
    report_settings = Column(JSON, nullable=True)
    timezone = Column(String, nullable=True)
    preferences = Column(JSON, nullable=True)


class StorageManager:
    """
    Manages persistent storage for the Standup Bot.
    Uses PostgreSQL database for storage and retrieval of data.
    Falls back to Zulip bot storage if database is not configured.
    """

    def __init__(self, storage, config=None):
        self.storage = storage
        self.config = config
        self.logger = logging.getLogger('standup_bot.storage')
        self.db_engine = None
        self.Session = None

        # Initialize database connection if config is provided
        if config and config.is_db_configured():
            self._initialize_db_connection(config.get_db_config())
        else:
            self.logger.warning("Database not configured, falling back to Zulip bot storage")

        # Initialize storage if needed
        self._initialize_storage()

    def _initialize_db_connection(self, db_config: Dict[str, str]) -> None:
        """Initialize database connection"""
        try:
            # Create database URL
            db_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"

            # Create engine
            self.db_engine = create_engine(db_url)

            # Create session factory
            self.Session = scoped_session(sessionmaker(bind=self.db_engine))

            # Create tables if they don't exist
            Base.metadata.create_all(self.db_engine)

            self.logger.info("Database connection initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database connection: {str(e)}")
            self.db_engine = None
            self.Session = None

    def _initialize_storage(self) -> None:
        """Initialize storage with default structure if it doesn't exist"""
        # If using Zulip bot storage, initialize it
        if not self.db_engine:
            if not self.storage.contains('standups'):
                self.logger.info("Initializing storage with default structure")
                self.storage.put('standups', {})

    def get_standups(self) -> Dict[str, Any]:
        """Get all standups from storage"""
        if self.db_engine:
            try:
                session = self.Session()
                standups_dict = {}

                try:
                    standups = session.query(Standup).all()
                    for standup in standups:
                        # Convert SQLAlchemy model to dictionary
                        standup_dict = {c.name: getattr(standup, c.name) for c in standup.__table__.columns}
                        standups_dict[standup.id] = standup_dict

                    return standups_dict
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting standups from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        return self.storage.get('standups')

    def get_standup(self, standup_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific standup by ID"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    standup = session.query(Standup).filter(Standup.id == str(standup_id)).first()
                    if standup:
                        # Convert SQLAlchemy model to dictionary
                        return {c.name: getattr(standup, c.name) for c in standup.__table__.columns}
                    return None
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting standup {standup_id} from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standups = self.get_standups()
        return standups.get(standup_id)

    def save_standup(self, standup_id: str, standup_data: Dict[str, Any]) -> None:
        """Save a standup to storage"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Check if standup exists
                    existing_standup = session.query(Standup).filter(Standup.id == str(standup_id)).first()

                    if existing_standup:
                        # Update existing standup
                        for key, value in standup_data.items():
                            if hasattr(existing_standup, key):
                                setattr(existing_standup, key, value)
                    else:
                        # Create new standup
                        new_standup = Standup(id=str(standup_id), **standup_data)
                        session.add(new_standup)

                    session.commit()
                    self.logger.debug(f"Saved standup {standup_id} to database")
                    return
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error saving standup {standup_id} to database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standups = self.get_standups()
        standups[standup_id] = standup_data
        self.storage.put('standups', standups)
        self.logger.debug(f"Saved standup {standup_id} to Zulip storage")

    def delete_standup(self, standup_id: str) -> bool:
        """Delete a standup from storage"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    standup = session.query(Standup).filter(Standup.id == str(standup_id)).first()
                    if standup:
                        session.delete(standup)
                        session.commit()
                        self.logger.debug(f"Deleted standup {standup_id} from database")
                        return True
                    return False
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error deleting standup {standup_id} from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standups = self.get_standups()
        if standup_id in standups:
            del standups[standup_id]
            self.storage.put('standups', standups)
            self.logger.debug(f"Deleted standup {standup_id} from Zulip storage")
            return True
        return False

    def get_user_standups(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all standups that a user is part of"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Query for standups where user is a participant or creator
                    # Note: This is a bit complex because participants is a JSON array
                    # We need to use SQL functions to check if user_id is in the array
                    standups = session.query(Standup).filter(
                        sa.or_(
                            Standup.creator_id == user_id,
                            # This checks if user_id is in the participants JSON array
                            Standup.participants.cast(sa.String).contains(str(user_id))
                        )
                    ).all()

                    # Convert SQLAlchemy models to dictionaries
                    user_standups = []
                    for standup in standups:
                        standup_dict = {c.name: getattr(standup, c.name) for c in standup.__table__.columns}
                        user_standups.append(standup_dict)

                    return user_standups
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting user standups from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standups = self.get_standups()
        user_standups = []

        for standup_id, standup in standups.items():
            if user_id in standup.get('participants', []) or user_id == standup.get('creator_id'):
                user_standups.append(standup)

        return user_standups

    def save_response(self, standup_id: str, date: str, user_id: int, responses: Dict[str, str]) -> None:
        """Save a user's response to a standup"""
        if self.db_engine:
            try:
                # First check if the standup exists
                standup = self.get_standup(standup_id)
                if not standup:
                    self.logger.error(f"Cannot save response: standup {standup_id} not found")
                    return

                session = self.Session()

                try:
                    # Check if response already exists
                    existing_response = session.query(Response).filter(
                        Response.standup_id == str(standup_id),
                        Response.date == date,
                        Response.user_id == str(user_id)
                    ).first()

                    timestamp = self._get_current_timestamp()

                    if existing_response:
                        # Update existing response
                        existing_response.responses = responses
                        existing_response.timestamp = timestamp
                    else:
                        # Create new response
                        new_response = Response(
                            standup_id=str(standup_id),
                            date=date,
                            user_id=str(user_id),
                            responses=responses,
                            timestamp=timestamp
                        )
                        session.add(new_response)

                    session.commit()
                    self.logger.debug(f"Saved response for user {user_id} in standup {standup_id} on {date} to database")
                    return
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error saving response to database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standup = self.get_standup(standup_id)
        if not standup:
            self.logger.error(f"Cannot save response: standup {standup_id} not found")
            return

        # Initialize responses for this date if they don't exist
        if 'responses' not in standup:
            standup['responses'] = {}

        if date not in standup['responses']:
            standup['responses'][date] = {}

        # Save the response
        standup['responses'][date][str(user_id)] = {
            'responses': responses,
            'timestamp': self._get_current_timestamp()
        }

        self.save_standup(standup_id, standup)
        self.logger.debug(f"Saved response for user {user_id} in standup {standup_id} on {date} to Zulip storage")

    def get_responses(self, standup_id: str, date: str) -> Dict[str, Any]:
        """Get all responses for a standup on a specific date"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Query for responses for this standup and date
                    db_responses = session.query(Response).filter(
                        Response.standup_id == str(standup_id),
                        Response.date == date
                    ).all()

                    # Convert to the expected format
                    responses_dict = {}
                    for response in db_responses:
                        responses_dict[response.user_id] = {
                            'responses': response.responses,
                            'timestamp': response.timestamp
                        }

                    return responses_dict
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting responses from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standup = self.get_standup(standup_id)
        if not standup or 'responses' not in standup or date not in standup['responses']:
            return {}

        return standup['responses'][date]

    def get_missing_responses(self, standup_id: str, date: str) -> Set[int]:
        """Get users who haven't responded to a standup on a specific date"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Get the standup to get the list of participants
                    standup = session.query(Standup).filter(Standup.id == str(standup_id)).first()
                    if not standup:
                        return set()

                    participants = set(standup.participants)

                    # Get the users who have responded
                    responses = session.query(Response).filter(
                        Response.standup_id == str(standup_id),
                        Response.date == date
                    ).all()

                    responders = {int(response.user_id) for response in responses}

                    # Return the difference
                    return participants - responders
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting missing responses from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standup = self.get_standup(standup_id)
        if not standup:
            return set()

        participants = set(standup.get('participants', []))

        if 'responses' not in standup or date not in standup['responses']:
            return participants

        responders = {int(user_id) for user_id in standup['responses'][date].keys()}
        return participants - responders

    def save_report(self, standup_id: str, date: str, report_data: Dict[str, Any]) -> None:
        """Save a report for a standup on a specific date"""
        if self.db_engine:
            try:
                # First check if the standup exists
                standup = self.get_standup(standup_id)
                if not standup:
                    self.logger.error(f"Cannot save report: standup {standup_id} not found")
                    return

                session = self.Session()

                try:
                    # Check if report already exists
                    existing_report = session.query(Report).filter(
                        Report.standup_id == str(standup_id),
                        Report.date == date
                    ).first()

                    # Extract specific fields from report_data
                    participation_rate = report_data.get('participation_rate')
                    ai_summary = report_data.get('ai_summary')

                    if existing_report:
                        # Update existing report
                        existing_report.participation_rate = participation_rate
                        existing_report.ai_summary = ai_summary
                        existing_report.report_data = report_data
                    else:
                        # Create new report
                        new_report = Report(
                            standup_id=str(standup_id),
                            date=date,
                            participation_rate=participation_rate,
                            ai_summary=ai_summary,
                            report_data=report_data
                        )
                        session.add(new_report)

                    session.commit()
                    self.logger.debug(f"Saved report for standup {standup_id} on {date} to database")
                    return
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error saving report to database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standup = self.get_standup(standup_id)
        if not standup:
            self.logger.error(f"Cannot save report: standup {standup_id} not found")
            return

        # Initialize history if it doesn't exist
        if 'history' not in standup:
            standup['history'] = []

        # Check if a report for this date already exists
        for i, report in enumerate(standup['history']):
            if report.get('date') == date:
                # Update existing report
                standup['history'][i] = report_data
                self.save_standup(standup_id, standup)
                self.logger.debug(f"Updated report for standup {standup_id} on {date} in Zulip storage")
                return

        # Add new report
        standup['history'].append(report_data)
        self.save_standup(standup_id, standup)
        self.logger.debug(f"Saved new report for standup {standup_id} on {date} to Zulip storage")

    def get_report(self, standup_id: str, date: str) -> Optional[Dict[str, Any]]:
        """Get a report for a standup on a specific date"""
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Query for report for this standup and date
                    report = session.query(Report).filter(
                        Report.standup_id == str(standup_id),
                        Report.date == date
                    ).first()

                    if report:
                        # Return the report data
                        return report.report_data
                    return None
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting report from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        standup = self.get_standup(standup_id)
        if not standup or 'history' not in standup:
            return None

        for report in standup['history']:
            if report.get('date') == date:
                return report

        return None

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'

    def get_user_report_settings(self, user_id: int) -> Dict[str, Any]:
        """
        Get report settings for a user

        Args:
            user_id: User ID

        Returns:
            Dictionary of report settings
        """
        # Default report settings
        default_settings = {
            'default_format': 'standard',
            'include_missing_participants': True,
            'email_reports': False,
            'default_email': None
        }

        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Query for user preferences
                    user_pref = session.query(UserPreference).filter(
                        UserPreference.user_id == str(user_id)
                    ).first()

                    if user_pref and user_pref.report_settings:
                        return user_pref.report_settings

                    # If no settings found, create default settings
                    if user_pref:
                        user_pref.report_settings = default_settings
                    else:
                        new_pref = UserPreference(
                            user_id=str(user_id),
                            report_settings=default_settings
                        )
                        session.add(new_pref)

                    session.commit()
                    return default_settings
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error getting user report settings from database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        with self.use_storage(['user_preferences']) as cache:
            preferences = cache.get('user_preferences') or {}
            user_prefs = preferences.get(str(user_id), {})
            report_settings = user_prefs.get('report_settings', {})

            # Set defaults if not present
            if not report_settings:
                report_settings = default_settings
                user_prefs['report_settings'] = report_settings
                preferences[str(user_id)] = user_prefs
                cache.put('user_preferences', preferences)

            return report_settings

    def save_user_report_settings(self, user_id: int, settings: Dict[str, Any]) -> None:
        """
        Save report settings for a user

        Args:
            user_id: User ID
            settings: Dictionary of report settings
        """
        if self.db_engine:
            try:
                session = self.Session()

                try:
                    # Query for user preferences
                    user_pref = session.query(UserPreference).filter(
                        UserPreference.user_id == str(user_id)
                    ).first()

                    if user_pref:
                        # Update existing settings
                        if user_pref.report_settings:
                            user_pref.report_settings.update(settings)
                        else:
                            user_pref.report_settings = settings
                    else:
                        # Create new user preference
                        new_pref = UserPreference(
                            user_id=str(user_id),
                            report_settings=settings
                        )
                        session.add(new_pref)

                    session.commit()
                    self.logger.debug(f"Saved report settings for user {user_id} to database")
                    return
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Error saving user report settings to database: {str(e)}")
                # Fall back to Zulip storage

        # Use Zulip storage if database is not available
        with self.use_storage(['user_preferences']) as cache:
            preferences = cache.get('user_preferences') or {}
            user_prefs = preferences.get(str(user_id), {})

            # Update report settings
            report_settings = user_prefs.get('report_settings', {})
            report_settings.update(settings)
            user_prefs['report_settings'] = report_settings

            preferences[str(user_id)] = user_prefs
            cache.put('user_preferences', preferences)
            self.logger.debug(f"Saved report settings for user {user_id} to Zulip storage")

    @contextmanager
    def use_storage(self, keys: List[str]) -> ContextManager[Dict[str, Any]]:
        """
        Context manager for accessing and modifying storage.

        This method provides a unified interface for storage operations,
        whether using PostgreSQL or Zulip bot storage.

        Args:
            keys: List of storage keys to access

        Returns:
            A context manager that provides access to the specified storage keys
        """
        # Create a cache dictionary to hold the data
        cache = {}

        # Check if we're using a StateHandler that doesn't have use_storage method
        if not hasattr(self.storage, 'use_storage'):
            # Use our own implementation for Zulip storage
            with self._use_zulip_storage(keys) as zulip_cache:
                yield zulip_cache
            return

        # If using PostgreSQL and the key is 'user_preferences', use the database
        if self.db_engine and 'user_preferences' in keys:
            # For user_preferences, we'll handle it specially since it's stored in the UserPreference table
            try:
                session = self.Session()

                # Load all user preferences
                if 'user_preferences' in keys:
                    user_prefs = {}
                    db_prefs = session.query(UserPreference).all()
                    for pref in db_prefs:
                        user_prefs[pref.user_id] = {
                            'active_standup': pref.active_standup,
                            'report_settings': pref.report_settings,
                            'timezone': pref.timezone,
                            'preferences': pref.preferences
                        }
                    cache['user_preferences'] = user_prefs

                # Load other keys from Zulip storage
                for key in keys:
                    if key != 'user_preferences':
                        if self.storage.contains(key):
                            cache[key] = self.storage.get(key)
                        else:
                            cache[key] = {}

                try:
                    # Yield the cache for the context block to use
                    yield cache
                finally:
                    # Save any changes back to storage
                    if 'user_preferences' in cache:
                        # Save user preferences to database
                        user_prefs = cache['user_preferences']
                        for user_id, prefs in user_prefs.items():
                            # Get or create user preference
                            user_pref = session.query(UserPreference).filter(
                                UserPreference.user_id == str(user_id)
                            ).first()

                            if user_pref:
                                # Update existing preference
                                user_pref.active_standup = prefs.get('active_standup')
                                user_pref.report_settings = prefs.get('report_settings')
                                user_pref.timezone = prefs.get('timezone')
                                user_pref.preferences = prefs.get('preferences')
                            else:
                                # Create new preference
                                new_pref = UserPreference(
                                    user_id=str(user_id),
                                    active_standup=prefs.get('active_standup'),
                                    report_settings=prefs.get('report_settings'),
                                    timezone=prefs.get('timezone'),
                                    preferences=prefs.get('preferences')
                                )
                                session.add(new_pref)

                        session.commit()
                        self.logger.debug("Updated user preferences in database")

                    # Save other keys to Zulip storage
                    for key in keys:
                        if key != 'user_preferences' and key in cache:
                            self.storage.put(key, cache[key])
                            self.logger.debug(f"Updated Zulip storage for key: {key}")
            except Exception as e:
                self.logger.error(f"Error using database storage: {str(e)}")
                session.rollback()
                # Fall back to Zulip storage
                with self._use_zulip_storage(keys) as zulip_cache:
                    yield zulip_cache
            finally:
                session.close()
        else:
            # Use Zulip storage for all keys
            with self._use_zulip_storage(keys) as zulip_cache:
                yield zulip_cache

    @contextmanager
    def _use_zulip_storage(self, keys: List[str]) -> ContextManager[Dict[str, Any]]:
        """
        Context manager for accessing and modifying Zulip bot storage.

        This is a fallback method used when PostgreSQL is not available.

        Args:
            keys: List of storage keys to access

        Returns:
            A context manager that provides access to the specified storage keys
        """
        # Create a cache dictionary to hold the data
        cache = {}

        # Load data for each key
        for key in keys:
            if self.storage.contains(key):
                cache[key] = self.storage.get(key)
            else:
                cache[key] = {}

        try:
            # Yield the cache for the context block to use
            yield cache
        finally:
            # Save any changes back to storage
            for key in keys:
                if key in cache:
                    self.storage.put(key, cache[key])
                    self.logger.debug(f"Updated Zulip storage for key: {key}")
