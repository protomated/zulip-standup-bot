from typing import Dict, Any, List, Optional
import json
import time
import datetime
from zulip_bots.lib import BotHandler
from storage_manager import StorageManager


class StandupManager:
    """
    Handles the core standup meeting functionality
    """

    def __init__(self, storage_manager: StorageManager, bot_handler: BotHandler):
        self.storage = storage_manager
        self.bot_handler = bot_handler

    def create_standup(self, creator_id: int, name: str, team_stream: str,
                       schedule: Dict[str, Any], questions: List[str],
                       participants: List[int], timezone_handling: str = "same") -> int:
        """
        Create a new standup meeting

        Args:
            creator_id: User ID of the creator
            name: Name of the standup
            team_stream: Stream where reports will be posted
            schedule: Schedule settings (days, time, etc.)
            questions: List of questions to ask in the standup
            participants: List of participant user IDs
            timezone_handling: How to handle timezones ("same" or "local")

        Returns:
            Standup ID
        """
        standup_id = int(time.time())  # Simple unique ID generation

        standup = {
            'id': standup_id,
            'name': name,
            'creator_id': creator_id,
            'team_stream': team_stream,
            'schedule': schedule,
            'questions': questions,
            'participants': participants,
            'timezone_handling': timezone_handling,
            'active': True,
            'created_at': datetime.datetime.now().isoformat(),
            'responses': {},
            'history': []
        }

        # Store the standup
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            standups[standup_id] = standup
            cache['standups'] = standups

        return standup_id

    def get_standup(self, standup_id: int) -> Optional[Dict[str, Any]]:
        """Get a standup by ID"""
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            return standups.get(str(standup_id))

    def get_standups_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all standups a user is part of"""
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            return [s for s in standups.values() if user_id in s['participants'] or user_id == s.get('creator_id')]

    def is_standup_day(self, standup: Dict[str, Any]) -> bool:
        """Check if today is a scheduled day for the standup"""
        today = datetime.datetime.now().strftime('%A').lower()
        return today in standup['schedule']['days']

    def add_response(self, standup_id: int, user_id: int, responses: Dict[str, str]) -> bool:
        """Add a user's responses to a standup"""
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return False

            standup = standups[str(standup_id)]

            # Add response
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            if today not in standup['responses']:
                standup['responses'][today] = {}

            standup['responses'][today][user_id] = {
                'responses': responses,
                'timestamp': datetime.datetime.now().isoformat()
            }

            # Update standups
            cache['standups'] = standups
            return True

    def cancel_standup(self, standup_id: int) -> bool:
        """Cancel a standup meeting"""
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return False

            standups[str(standup_id)]['active'] = False
            cache['standups'] = standups
            return True
