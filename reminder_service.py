from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

class ReminderService:
    """
    Service for managing and sending reminders for standup meetings
    """

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

    def send_reminder(self, standup_id: str, user_id: int) -> None:
        """
        Send a reminder to a specific user for a standup

        Args:
            standup_id: The ID of the standup
            user_id: The user ID to send the reminder to
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot send reminder: Standup {standup_id} not found")
            return

        # Construct the reminder message
        message = self._create_reminder_message(standup)

        # Send the reminder as a private message
        self.bot_handler.send_message({
            'type': 'private',
            'to': [user_id],
            'content': message
        })

        self.logger.info(f"Sent reminder for standup {standup_id} to user {user_id}")

    def send_reminders_for_standup(self, standup_id: str) -> None:
        """
        Send reminders to all participants of a standup who haven't responded yet

        Args:
            standup_id: The ID of the standup
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot send reminders: Standup {standup_id} not found")
            return

        # Get today's date in the format used for responses
        today = datetime.now().strftime("%Y-%m-%d")

        # Get list of participants who haven't responded yet
        participants = standup.get('participants', [])
        responses = standup.get('responses', {}).get(today, {})

        for participant_id in participants:
            # Skip participants who have already responded
            if str(participant_id) in responses:
                continue

            # Send reminder to this participant
            self.send_reminder(standup_id, participant_id)

    def _create_reminder_message(self, standup: Dict[str, Any]) -> str:
        """
        Create a reminder message for a standup

        Args:
            standup: The standup data

        Returns:
            A formatted reminder message
        """
        standup_name = standup.get('name', 'Unnamed standup')
        questions = standup.get('questions', [])

        message = f"📢 **Reminder: {standup_name}**\n\n"
        message += "Your standup update is due. Please provide your status by responding to the following questions:\n\n"

        for i, question in enumerate(questions, 1):
            message += f"{i}. {question}\n"

        message += "\nTo submit your update, use the `status {standup_id}` command followed by your responses."
        message = message.replace("{standup_id}", standup.get('id', ''))

        return message

    def schedule_reminders(self, standup_id: str, schedule_manager) -> None:
        """
        Schedule reminders for a standup using the schedule manager

        Args:
            standup_id: The ID of the standup
            schedule_manager: The schedule manager instance
        """
        standup = self.storage_manager.get_standup(standup_id)
        if not standup:
            self.logger.warning(f"Cannot schedule reminders: Standup {standup_id} not found")
            return

        # Schedule the reminder 30 minutes before the standup is due
        schedule = standup.get('schedule', {})
        time_str = schedule.get('time', '09:00')
        days = schedule.get('days', [])

        # Parse the time
        hour, minute = map(int, time_str.split(':'))

        # Schedule reminders for each day
        for day in days:
            # Schedule the reminder task
            schedule_manager.schedule_task(
                task_type="reminder",
                day_of_week=day,
                hour=hour,
                minute=max(0, minute-30),  # 30 minutes before, but not negative
                data={"standup_id": standup_id}
            )

        self.logger.info(f"Scheduled reminders for standup {standup_id}")
