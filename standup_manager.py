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
                       participants: List[int], timezone_handling: str = "same",
                       team_tag: str = "", project_tag: str = "",
                       permissions: Dict[str, Any] = None,
                       question_templates: Optional[List[Dict[str, Any]]] = None) -> int:
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
            team_tag: Optional team tag for categorizing standups
            project_tag: Optional project tag for categorizing standups
            permissions: Optional permissions settings for the standup
            question_templates: Optional structured question templates with validation rules

        Returns:
            Standup ID
        """
        standup_id = int(time.time())  # Simple unique ID generation

        # Default permissions if none provided
        if permissions is None:
            permissions = {
                'admin_users': [creator_id],  # Creator is admin by default
                'can_edit': 'admin',  # Only admins can edit
                'can_view': 'participants'  # Only participants can view
            }

        standup = {
            'id': standup_id,
            'name': name,
            'creator_id': creator_id,
            'team_stream': team_stream,
            'schedule': schedule,
            'questions': questions,
            'participants': participants,
            'timezone_handling': timezone_handling,
            'team_tag': team_tag,
            'project_tag': project_tag,
            'permissions': permissions,
            'settings': {
                'reminder_time': 30,  # Minutes before standup to send reminder
                'report_format': 'detailed',  # Default report format
                'ai_summary': True  # Enable AI summary by default
            },
            'active': True,
            'created_at': datetime.datetime.now().isoformat(),
            'responses': {},
            'history': [],
            'question_templates': question_templates or []
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

    def has_permission(self, standup_id: int, user_id: int, permission_type: str) -> bool:
        """
        Check if a user has a specific permission for a standup

        Args:
            standup_id: ID of the standup
            user_id: ID of the user
            permission_type: Type of permission ('view', 'edit', 'admin')

        Returns:
            True if user has permission, False otherwise
        """
        standup = self.get_standup(standup_id)
        if not standup:
            return False

        # Creator always has all permissions
        if user_id == standup.get('creator_id'):
            return True

        # Check if user is an admin
        if permission_type == 'admin':
            return user_id in standup.get('permissions', {}).get('admin_users', [])

        # Check edit permission
        if permission_type == 'edit':
            edit_permission = standup.get('permissions', {}).get('can_edit', 'admin')
            if edit_permission == 'admin':
                return user_id in standup.get('permissions', {}).get('admin_users', [])
            elif edit_permission == 'participants':
                return user_id in standup.get('participants', [])
            elif edit_permission == 'all':
                return True

        # Check view permission
        if permission_type == 'view':
            view_permission = standup.get('permissions', {}).get('can_view', 'participants')
            if view_permission == 'admin':
                return user_id in standup.get('permissions', {}).get('admin_users', [])
            elif view_permission == 'participants':
                return user_id in standup.get('participants', [])
            elif view_permission == 'all':
                return True

        return False

    def add_admin(self, standup_id: int, admin_id: int, requester_id: int) -> bool:
        """
        Add an admin to a standup

        Args:
            standup_id: ID of the standup
            admin_id: ID of the user to add as admin
            requester_id: ID of the user making the request

        Returns:
            True if successful, False otherwise
        """
        # Check if requester has admin permission
        if not self.has_permission(standup_id, requester_id, 'admin'):
            return False

        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return False

            standup = standups[str(standup_id)]
            if 'permissions' not in standup:
                standup['permissions'] = {
                    'admin_users': [standup['creator_id']],
                    'can_edit': 'admin',
                    'can_view': 'participants'
                }

            if admin_id not in standup['permissions']['admin_users']:
                standup['permissions']['admin_users'].append(admin_id)

            cache['standups'] = standups
            return True

    def remove_admin(self, standup_id: int, admin_id: int, requester_id: int) -> bool:
        """
        Remove an admin from a standup

        Args:
            standup_id: ID of the standup
            admin_id: ID of the user to remove as admin
            requester_id: ID of the user making the request

        Returns:
            True if successful, False otherwise
        """
        # Check if requester has admin permission
        if not self.has_permission(standup_id, requester_id, 'admin'):
            return False

        # Cannot remove creator as admin
        standup = self.get_standup(standup_id)
        if not standup or admin_id == standup.get('creator_id'):
            return False

        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return False

            standup = standups[str(standup_id)]
            if 'permissions' not in standup or 'admin_users' not in standup['permissions']:
                return False

            if admin_id in standup['permissions']['admin_users']:
                standup['permissions']['admin_users'].remove(admin_id)

            cache['standups'] = standups
            return True

    def update_settings(self, standup_id: int, settings: Dict[str, Any], requester_id: int) -> bool:
        """
        Update settings for a standup

        Args:
            standup_id: ID of the standup
            settings: Dictionary of settings to update
            requester_id: ID of the user making the request

        Returns:
            True if successful, False otherwise
        """
        # Check if requester has edit permission
        if not self.has_permission(standup_id, requester_id, 'edit'):
            return False

        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return False

            standup = standups[str(standup_id)]
            if 'settings' not in standup:
                standup['settings'] = {
                    'reminder_time': 30,
                    'report_format': 'detailed',
                    'ai_summary': True
                }

            # Update settings
            for key, value in settings.items():
                standup['settings'][key] = value

            cache['standups'] = standups
            return True

    def update_permissions(self, standup_id: int, permissions: Dict[str, Any], requester_id: int) -> bool:
        """
        Update permissions for a standup

        Args:
            standup_id: ID of the standup
            permissions: Dictionary of permissions to update
            requester_id: ID of the user making the request

        Returns:
            True if successful, False otherwise
        """
        # Check if requester has admin permission
        if not self.has_permission(standup_id, requester_id, 'admin'):
            return False

        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return False

            standup = standups[str(standup_id)]
            if 'permissions' not in standup:
                standup['permissions'] = {
                    'admin_users': [standup['creator_id']],
                    'can_edit': 'admin',
                    'can_view': 'participants'
                }

            # Update permissions
            for key, value in permissions.items():
                # Don't allow removing creator from admin_users
                if key == 'admin_users' and standup['creator_id'] not in value:
                    value.append(standup['creator_id'])
                standup['permissions'][key] = value

            cache['standups'] = standups
            return True
