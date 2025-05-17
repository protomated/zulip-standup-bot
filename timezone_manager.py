from typing import Dict, Any, List, Optional, Tuple
import datetime
import pytz
import logging
from zulip_bots.lib import BotHandler
from storage_manager import StorageManager

class TimezoneManager:
    """
    Handles timezone detection, conversion, and management for the Standup Bot.
    """

    def __init__(self, storage_manager: StorageManager, bot_handler: BotHandler):
        self.storage = storage_manager
        self.bot_handler = bot_handler
        self.logger = logging.getLogger('standup_bot.timezone_manager')

    def get_user_timezone(self, user_id: int) -> str:
        """
        Get a user's timezone preference.

        Args:
            user_id: The user's ID

        Returns:
            The user's timezone (e.g., 'America/New_York') or 'UTC' if not set
        """
        with self.storage.use_storage(['user_preferences']) as cache:
            user_prefs = cache.get('user_preferences') or {}
            user_prefs_dict = user_prefs.get(str(user_id), {})
            return user_prefs_dict.get('timezone', 'UTC')

    def set_user_timezone(self, user_id: int, timezone: str) -> bool:
        """
        Set a user's timezone preference.

        Args:
            user_id: The user's ID
            timezone: The timezone to set (e.g., 'America/New_York')

        Returns:
            True if successful, False otherwise
        """
        # Validate timezone
        if timezone not in pytz.all_timezones:
            self.logger.error(f"Invalid timezone: {timezone}")
            return False

        with self.storage.use_storage(['user_preferences']) as cache:
            user_prefs = cache.get('user_preferences') or {}
            if str(user_id) not in user_prefs:
                user_prefs[str(user_id)] = {}

            user_prefs[str(user_id)]['timezone'] = timezone
            cache['user_preferences'] = user_prefs

        return True

    def convert_time(self, time_str: str, from_tz: str, to_tz: str, date_str: Optional[str] = None) -> str:
        """
        Convert a time from one timezone to another.

        Args:
            time_str: Time string in format 'HH:MM'
            from_tz: Source timezone
            to_tz: Target timezone
            date_str: Optional date string in format 'YYYY-MM-DD'

        Returns:
            Converted time string in format 'HH:MM'
        """
        try:
            # Parse time string
            hours, minutes = map(int, time_str.split(':'))

            # Use today's date if not provided
            if date_str:
                year, month, day = map(int, date_str.split('-'))
                date = datetime.date(year, month, day)
            else:
                date = datetime.date.today()

            # Create datetime in source timezone
            dt = datetime.datetime.combine(date, datetime.time(hours, minutes))
            source_tz = pytz.timezone(from_tz)
            target_tz = pytz.timezone(to_tz)

            # Localize and convert
            dt_with_tz = source_tz.localize(dt)
            converted_dt = dt_with_tz.astimezone(target_tz)

            # Return formatted time
            return converted_dt.strftime('%H:%M')

        except Exception as e:
            self.logger.error(f"Error converting time: {e}")
            return time_str  # Return original time on error

    def get_standup_time_for_user(self, standup: Dict[str, Any], user_id: int) -> str:
        """
        Get the appropriate standup time for a user based on timezone handling.

        Args:
            standup: The standup configuration
            user_id: The user's ID

        Returns:
            The standup time for the user in format 'HH:MM'
        """
        standup_time = standup['schedule']['time']
        standup_timezone = standup['schedule'].get('timezone', 'UTC')

        # If using same timezone for all, return the standup time
        if standup['timezone_handling'] == 'same':
            return standup_time

        # If using local timezones, convert to user's timezone
        user_timezone = self.get_user_timezone(user_id)
        return self.convert_time(standup_time, standup_timezone, user_timezone)

    def get_next_standup_time(self, standup: Dict[str, Any], user_id: int) -> Tuple[datetime.datetime, str]:
        """
        Calculate the next standup time for a user.

        Args:
            standup: The standup configuration
            user_id: The user's ID

        Returns:
            Tuple of (datetime of next standup, timezone string)
        """
        # Get standup schedule
        days = standup['schedule']['days']
        standup_time = standup['schedule']['time']
        standup_timezone = standup['schedule'].get('timezone', 'UTC')

        # Get user's timezone if using local timezones
        if standup['timezone_handling'] == 'local':
            user_timezone = self.get_user_timezone(user_id)
        else:
            user_timezone = standup_timezone

        # Map day names to numbers (0 = Monday, 6 = Sunday)
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

        # Convert days to numbers
        day_numbers = [day_map[day] for day in days]

        # Get current time in user's timezone
        now = datetime.datetime.now(pytz.timezone(user_timezone))

        # Parse standup time
        hours, minutes = map(int, standup_time.split(':'))

        # Calculate next standup day
        current_weekday = now.weekday()  # 0 = Monday, 6 = Sunday

        # Find the next day that has a standup
        days_until_next = 7  # Maximum days to wait
        for day_number in day_numbers:
            days_diff = (day_number - current_weekday) % 7

            # If it's the same day, check if the time has passed
            if days_diff == 0:
                standup_dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                if now < standup_dt:
                    days_until_next = 0
                    break

            # Otherwise, find the closest future day
            if 0 < days_diff < days_until_next:
                days_until_next = days_diff

        # If no future standup found this week, use the first day next week
        if days_until_next == 7:
            days_until_next = min((day_number - current_weekday) % 7 for day_number in day_numbers)
            if days_until_next == 0:
                days_until_next = 7  # Full week if the only standup day is today and it's passed

        # Calculate the next standup datetime
        next_standup = now + datetime.timedelta(days=days_until_next)
        next_standup = next_standup.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        return (next_standup, user_timezone)

    def get_all_timezones(self) -> List[str]:
        """
        Get a list of all available timezones.

        Returns:
            List of timezone strings
        """
        return pytz.all_timezones

    def get_common_timezones(self) -> List[str]:
        """
        Get a list of common timezones.

        Returns:
            List of common timezone strings
        """
        return pytz.common_timezones

    def detect_timezone(self, user_id: int) -> str:
        """
        Attempt to detect a user's timezone.
        This is a placeholder - in a real implementation, you might use
        the Zulip API to get the user's timezone if available.

        Args:
            user_id: The user's ID

        Returns:
            Detected timezone or 'UTC' if detection fails
        """
        # In a real implementation, you would use the Zulip API to get the user's timezone
        # For now, return UTC as a default
        return 'UTC'
