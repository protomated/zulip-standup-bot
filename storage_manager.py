import json
import logging
from typing import Dict, Any, Optional, List, Set


class StorageManager:
    """
    Manages persistent storage for the Standup Bot.
    Uses the Zulip bot storage system to store and retrieve data.
    """

    def __init__(self, storage):
        self.storage = storage
        self.logger = logging.getLogger('standup_bot.storage')
        
        # Initialize storage if needed
        self._initialize_storage()
    
    def _initialize_storage(self) -> None:
        """Initialize storage with default structure if it doesn't exist"""
        if not self.storage.contains('standups'):
            self.logger.info("Initializing storage with default structure")
            self.storage.put('standups', {})
    
    def get_standups(self) -> Dict[str, Any]:
        """Get all standups from storage"""
        return self.storage.get('standups')
    
    def get_standup(self, standup_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific standup by ID"""
        standups = self.get_standups()
        return standups.get(standup_id)
    
    def save_standup(self, standup_id: str, standup_data: Dict[str, Any]) -> None:
        """Save a standup to storage"""
        standups = self.get_standups()
        standups[standup_id] = standup_data
        self.storage.put('standups', standups)
        self.logger.debug(f"Saved standup {standup_id}")
    
    def delete_standup(self, standup_id: str) -> bool:
        """Delete a standup from storage"""
        standups = self.get_standups()
        if standup_id in standups:
            del standups[standup_id]
            self.storage.put('standups', standups)
            self.logger.debug(f"Deleted standup {standup_id}")
            return True
        return False
    
    def get_user_standups(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all standups that a user is part of"""
        standups = self.get_standups()
        user_standups = []
        
        for standup_id, standup in standups.items():
            if user_id in standup.get('participants', []) or user_id == standup.get('creator_id'):
                user_standups.append(standup)
        
        return user_standups
    
    def save_response(self, standup_id: str, date: str, user_id: int, responses: Dict[str, str]) -> None:
        """Save a user's response to a standup"""
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
        self.logger.debug(f"Saved response for user {user_id} in standup {standup_id} on {date}")
    
    def get_responses(self, standup_id: str, date: str) -> Dict[str, Any]:
        """Get all responses for a standup on a specific date"""
        standup = self.get_standup(standup_id)
        if not standup or 'responses' not in standup or date not in standup['responses']:
            return {}
        
        return standup['responses'][date]
    
    def get_missing_responses(self, standup_id: str, date: str) -> Set[int]:
        """Get users who haven't responded to a standup on a specific date"""
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
                self.logger.debug(f"Updated report for standup {standup_id} on {date}")
                return
        
        # Add new report
        standup['history'].append(report_data)
        self.save_standup(standup_id, standup)
        self.logger.debug(f"Saved new report for standup {standup_id} on {date}")
    
    def get_report(self, standup_id: str, date: str) -> Optional[Dict[str, Any]]:
        """Get a report for a standup on a specific date"""
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
