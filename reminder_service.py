from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

class ReminderService:
    """
    Service for managing and sending reminders for standup meetings
    """

    # Reminder levels
    REMINDER_FRIENDLY = 'friendly'
    REMINDER_NORMAL = 'normal'
    REMINDER_URGENT = 'urgent'
    REMINDER_SUPERVISOR = 'supervisor'

    # Default reminder intervals (in minutes)
    DEFAULT_REMINDER_INTERVALS = {
        REMINDER_FRIENDLY: 30,  # 30 minutes before due
        REMINDER_NORMAL: 15,    # 15 minutes after due
        REMINDER_URGENT: 60,    # 1 hour after due
        REMINDER_SUPERVISOR: 120  # 2 hours after due
    }

    def __init__(self, storage_manager, bot_handler):
        """
        Initialize the ReminderService

        Args:
            storage_manager: The storage manager instance for accessing standup data
            bot_handler: The bot handler for sending messages
        """
        self.storage_manager = storage_manager
        self.bot_handler = bot_handler
        self.logger = logging.getLogger('standup_bot.reminder_service')
        self.logger.info("ReminderService initialized")

    def send_reminder(self, standup_id: str, user_id: int, reminder_level: str = 'normal') -> None:
        """
        Send a reminder to a specific user for a standup

        Args:
            standup_id: The ID of the standup
            user_id: The user ID to send the reminder to
            reminder_level: The level of the reminder (friendly, normal, urgent, supervisor)
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot send reminder: Standup {standup_id} not found")
            return

        # Check if user is OOO
        today = datetime.now().strftime("%Y-%m-%d")
        if self._is_user_ooo(user_id, today):
            self.logger.info(f"Skipping reminder for user {user_id} who is OOO")
            return

        # Construct the reminder message
        message = self._create_reminder_message(standup, reminder_level)

        # Send the reminder as a private message
        self.bot_handler.send_message({
            'type': 'private',
            'to': [user_id],
            'content': message
        })

        self.logger.info(f"Sent {reminder_level} reminder for standup {standup_id} to user {user_id}")

    def send_reminders_for_standup(self, standup_id: str, reminder_level: str = 'normal') -> None:
        """
        Send reminders to all participants of a standup who haven't responded yet

        Args:
            standup_id: The ID of the standup
            reminder_level: The level of the reminder (friendly, normal, urgent, supervisor)
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot send reminders: Standup {standup_id} not found")
            return

        # Get today's date in the format used for responses
        today = datetime.now().strftime("%Y-%m-%d")

        # Get list of participants who haven't responded yet
        missing_participants = self.storage_manager.get_missing_responses(standup_id, today)

        # If this is a supervisor reminder, send to supervisors instead
        if reminder_level == self.REMINDER_SUPERVISOR:
            self._send_supervisor_notification(standup_id, today, missing_participants)
            return

        # Send reminders to participants who haven't responded
        for participant_id in missing_participants:
            # Skip participants who are OOO
            if self._is_user_ooo(participant_id, today):
                continue

            # Send reminder to this participant
            self.send_reminder(standup_id, participant_id, reminder_level)

    def _create_reminder_message(self, standup: Dict[str, Any], reminder_level: str = 'normal') -> str:
        """
        Create a reminder message for a standup based on the reminder level

        Args:
            standup: The standup data
            reminder_level: The level of the reminder (friendly, normal, urgent, supervisor)

        Returns:
            A formatted reminder message
        """
        standup_name = standup.get('name', 'Unnamed standup')
        questions = standup.get('questions', [])
        standup_id = standup.get('id', '')

        # Get reminder settings
        reminder_settings = standup.get('reminder_settings', {})
        custom_templates = reminder_settings.get('templates', {})

        # Check if there's a custom template for this level
        if reminder_level in custom_templates:
            message = custom_templates[reminder_level]
            # Replace placeholders
            message = message.replace("{standup_name}", standup_name)
            message = message.replace("{standup_id}", standup_id)
            message = message.replace("{questions}", "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)]))
            return message

        # Use default templates based on level
        if reminder_level == self.REMINDER_FRIENDLY:
            message = f"🔔 **Friendly Reminder: {standup_name}**\n\n"
            message += "Your standup update will be due soon. When you have a moment, please provide your status by responding to the following questions:\n\n"
        elif reminder_level == self.REMINDER_NORMAL:
            message = f"📢 **Reminder: {standup_name}**\n\n"
            message += "Your standup update is due. Please provide your status by responding to the following questions:\n\n"
        elif reminder_level == self.REMINDER_URGENT:
            message = f"⚠️ **Urgent Reminder: {standup_name}**\n\n"
            message += "Your standup update is overdue. Please provide your status as soon as possible by responding to the following questions:\n\n"
        else:
            message = f"📢 **Reminder: {standup_name}**\n\n"
            message += "Your standup update is due. Please provide your status by responding to the following questions:\n\n"

        # Add questions
        for i, question in enumerate(questions, 1):
            message += f"{i}. {question}\n"

        # Add instructions
        message += f"\nTo submit your update, use the `status {standup_id}` command followed by your responses."

        return message

    def _send_supervisor_notification(self, standup_id: str, date: str, missing_participants: List[int]) -> None:
        """
        Send a notification to supervisors about team members who haven't responded

        Args:
            standup_id: The ID of the standup
            date: The date for which to check responses
            missing_participants: List of participant IDs who haven't responded
        """
        if not missing_participants:
            return

        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            return

        # Get supervisor IDs from standup settings
        reminder_settings = standup.get('reminder_settings', {})
        supervisors = reminder_settings.get('supervisors', [])

        # If no supervisors configured, use the creator
        if not supervisors and 'creator_id' in standup:
            supervisors = [standup['creator_id']]

        if not supervisors:
            return

        # Create the notification message
        standup_name = standup.get('name', 'Unnamed standup')
        message = f"⚠️ **Supervisor Notification: {standup_name}**\n\n"
        message += f"The following team members have not submitted their standup updates for {date}:\n\n"

        # Add the list of missing participants
        for participant_id in missing_participants:
            # Skip participants who are OOO
            if self._is_user_ooo(participant_id, date):
                continue
            message += f"- <@{participant_id}>\n"

        message += f"\nYou may want to follow up with them directly or send a reminder using:\n"
        message += f"`remind {standup_id} urgent`"

        # Send the notification to each supervisor
        for supervisor_id in supervisors:
            self.bot_handler.send_message({
                'type': 'private',
                'to': [supervisor_id],
                'content': message
            })

        self.logger.info(f"Sent supervisor notification for standup {standup_id}")

    def _is_user_ooo(self, user_id: int, date: str) -> bool:
        """
        Check if a user is out of office on a specific date

        Args:
            user_id: The user ID to check
            date: The date to check in YYYY-MM-DD format

        Returns:
            True if the user is OOO, False otherwise
        """
        # Try to get the calendar integration from the storage manager
        calendar_integration = getattr(self.storage_manager, 'calendar_integration', None)
        if calendar_integration and hasattr(calendar_integration, 'is_user_ooo'):
            return calendar_integration.is_user_ooo(user_id, date)

        # Fallback: check if there's a schedule manager with OOO functionality
        schedule_manager = getattr(self, 'schedule_manager', None)
        if schedule_manager and hasattr(schedule_manager, 'is_user_ooo'):
            return schedule_manager.is_user_ooo(user_id, date)

        return False

    def schedule_reminders(self, standup_id: str, schedule_manager) -> None:
        """
        Schedule progressive reminders for a standup using the schedule manager

        Args:
            standup_id: The ID of the standup
            schedule_manager: The schedule manager instance
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot schedule reminders: Standup {standup_id} not found")
            return

        # Store the schedule manager for later use
        self.schedule_manager = schedule_manager

        # Get reminder settings
        reminder_settings = standup.get('reminder_settings', {})

        # Get reminder intervals (in minutes)
        intervals = reminder_settings.get('intervals', self.DEFAULT_REMINDER_INTERVALS)

        # Get enabled reminder levels
        enabled_levels = reminder_settings.get('enabled_levels',
                                             [self.REMINDER_FRIENDLY, self.REMINDER_NORMAL, self.REMINDER_URGENT])

        # Check if supervisor notifications are enabled
        supervisor_enabled = self.REMINDER_SUPERVISOR in enabled_levels

        # Schedule the standup time
        schedule = standup.get('schedule', {})
        time_str = schedule.get('time', '09:00')
        days = schedule.get('days', [])

        # Parse the time
        hour, minute = map(int, time_str.split(':'))

        # Schedule reminders for each day
        for day in days:
            # Schedule friendly reminder before the standup (if enabled)
            if self.REMINDER_FRIENDLY in enabled_levels:
                friendly_minutes = intervals.get(self.REMINDER_FRIENDLY, 30)
                friendly_hour, friendly_minute = self._adjust_time(hour, minute, -friendly_minutes)

                schedule_manager.schedule_task(
                    task_type="reminder",
                    day_of_week=day,
                    hour=friendly_hour,
                    minute=friendly_minute,
                    data={"standup_id": standup_id, "level": self.REMINDER_FRIENDLY}
                )

            # Schedule normal reminder after the standup (if enabled)
            if self.REMINDER_NORMAL in enabled_levels:
                normal_minutes = intervals.get(self.REMINDER_NORMAL, 15)
                normal_hour, normal_minute = self._adjust_time(hour, minute, normal_minutes)

                schedule_manager.schedule_task(
                    task_type="reminder",
                    day_of_week=day,
                    hour=normal_hour,
                    minute=normal_minute,
                    data={"standup_id": standup_id, "level": self.REMINDER_NORMAL}
                )

            # Schedule urgent reminder after the standup (if enabled)
            if self.REMINDER_URGENT in enabled_levels:
                urgent_minutes = intervals.get(self.REMINDER_URGENT, 60)
                urgent_hour, urgent_minute = self._adjust_time(hour, minute, urgent_minutes)

                schedule_manager.schedule_task(
                    task_type="reminder",
                    day_of_week=day,
                    hour=urgent_hour,
                    minute=urgent_minute,
                    data={"standup_id": standup_id, "level": self.REMINDER_URGENT}
                )

            # Schedule supervisor notification after the standup (if enabled)
            if supervisor_enabled:
                supervisor_minutes = intervals.get(self.REMINDER_SUPERVISOR, 120)
                supervisor_hour, supervisor_minute = self._adjust_time(hour, minute, supervisor_minutes)

                schedule_manager.schedule_task(
                    task_type="reminder",
                    day_of_week=day,
                    hour=supervisor_hour,
                    minute=supervisor_minute,
                    data={"standup_id": standup_id, "level": self.REMINDER_SUPERVISOR}
                )

        self.logger.info(f"Scheduled progressive reminders for standup {standup_id}")

    def _adjust_time(self, hour: int, minute: int, delta_minutes: int) -> Tuple[int, int]:
        """
        Adjust a time by adding or subtracting minutes, handling hour rollover

        Args:
            hour: The hour (0-23)
            minute: The minute (0-59)
            delta_minutes: The number of minutes to add (positive) or subtract (negative)

        Returns:
            Tuple of (adjusted_hour, adjusted_minute)
        """
        # Convert to total minutes
        total_minutes = hour * 60 + minute + delta_minutes

        # Handle negative times (previous day)
        if total_minutes < 0:
            total_minutes += 24 * 60  # Add a full day

        # Handle times past midnight (next day)
        total_minutes %= 24 * 60  # Mod by minutes in a day

        # Convert back to hours and minutes
        adjusted_hour = total_minutes // 60
        adjusted_minute = total_minutes % 60

        return adjusted_hour, adjusted_minute

    def get_default_reminder_settings(self) -> Dict[str, Any]:
        """
        Get the default reminder settings

        Returns:
            Dictionary of default reminder settings
        """
        return {
            'enabled_levels': [
                self.REMINDER_FRIENDLY,
                self.REMINDER_NORMAL,
                self.REMINDER_URGENT
            ],
            'intervals': self.DEFAULT_REMINDER_INTERVALS.copy(),
            'supervisors': [],
            'templates': {}
        }

    def update_reminder_settings(self, standup_id: str, settings: Dict[str, Any]) -> None:
        """
        Update reminder settings for a standup

        Args:
            standup_id: The ID of the standup
            settings: Dictionary of settings to update
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot update reminder settings: Standup {standup_id} not found")
            return

        # Get current reminder settings or initialize with defaults
        reminder_settings = standup.get('reminder_settings', self.get_default_reminder_settings())

        # Update settings
        for key, value in settings.items():
            if key == 'intervals' and isinstance(value, dict):
                # Merge intervals
                reminder_settings['intervals'].update(value)
            elif key == 'enabled_levels' and isinstance(value, list):
                # Replace enabled levels
                reminder_settings['enabled_levels'] = value
            elif key == 'supervisors' and isinstance(value, list):
                # Replace supervisors
                reminder_settings['supervisors'] = value
            elif key == 'templates' and isinstance(value, dict):
                # Merge templates
                if 'templates' not in reminder_settings:
                    reminder_settings['templates'] = {}
                reminder_settings['templates'].update(value)

        # Save updated settings
        standup['reminder_settings'] = reminder_settings
        self.storage_manager.save_standup(standup_id, standup)

        self.logger.info(f"Updated reminder settings for standup {standup_id}")
