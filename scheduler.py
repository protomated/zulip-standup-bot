from typing import Dict, Any, List, Set, Callable, Optional
import threading
import time
import datetime
import heapq
from zulip_bots.lib import BotHandler
from storage_manager import StorageManager


class ScheduleManager:
    """
    Handles scheduling standup meetings and reminders
    """

    def __init__(self, storage_manager: StorageManager, bot_handler: BotHandler, timezone_manager=None):
        self.storage = storage_manager
        self.bot_handler = bot_handler
        self.timezone_manager = timezone_manager
        self.scheduled_tasks = []
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

    def initialize_scheduled_tasks(self) -> None:
        """Initialize scheduled tasks from storage"""
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            for standup_id, standup in standups.items():
                if standup['active']:
                    self._schedule_standup(standup)

    def _scheduler_loop(self) -> None:
        """Main scheduler loop that runs in a separate thread"""
        while True:
            now = time.time()

            # Check for tasks that need to be executed
            while self.scheduled_tasks and self.scheduled_tasks[0][0] <= now:
                task_time, task_id, task_func, task_args = heapq.heappop(self.scheduled_tasks)
                try:
                    task_func(*task_args)
                except Exception as e:
                    # Log exception but don't crash the scheduler
                    print(f"Error in scheduled task {task_id}: {e}")

            # Sleep for a short time
            time.sleep(10)

    def schedule_task(self, task_time: float, task_id: str, task_func: Callable, *args) -> None:
        """Schedule a task to be executed at a specific time"""
        heapq.heappush(self.scheduled_tasks, (task_time, task_id, task_func, args))

    def _schedule_standup(self, standup: Dict[str, Any]) -> None:
        """Schedule a standup meeting"""
        days = standup['schedule']['days']
        time_str = standup['schedule']['time']
        timezone = standup['schedule'].get('timezone', 'UTC')

        # Calculate next occurrence
        next_time = self._calculate_next_occurrence(days, time_str, timezone)

        if next_time:
            # Schedule the standup start
            self.schedule_task(
                next_time,
                f"standup_start_{standup['id']}",
                self._start_standup,
                standup['id']
            )

    def _calculate_next_occurrence(self, days: List[str], time_str: str, timezone: str = 'UTC') -> Optional[float]:
        """
        Calculate the next occurrence of a scheduled event

        Args:
            days: List of days when the event should occur (e.g., ['monday', 'wednesday', 'friday'])
            time_str: Time when the event should occur in format 'HH:MM'
            timezone: Timezone for the event (default: 'UTC')

        Returns:
            Unix timestamp of the next occurrence or None if calculation fails
        """
        try:
            # Map day names to numbers (0 = Monday, 6 = Sunday)
            day_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }

            # Convert days to numbers
            day_numbers = [day_map[day.lower()] for day in days]

            # Parse time
            hours, minutes = map(int, time_str.split(':'))

            # Get current time in the specified timezone
            import pytz
            from datetime import datetime, timedelta

            tz = pytz.timezone(timezone)
            now = datetime.now(tz)

            # Find the next occurrence
            next_date = None
            days_ahead = 7  # Maximum days to look ahead

            for i in range(days_ahead):
                check_date = now.date() + timedelta(days=i)
                weekday = check_date.weekday()  # 0 = Monday, 6 = Sunday

                if weekday in day_numbers:
                    # Create datetime for this occurrence
                    next_datetime = tz.localize(
                        datetime.combine(check_date, datetime.min.time().replace(hour=hours, minute=minutes))
                    )

                    # If this occurrence is in the future, use it
                    if next_datetime > now:
                        next_date = next_datetime
                        break

            if next_date:
                # Convert to UTC timestamp
                return next_date.timestamp()

            # If no occurrence found in the next week, use the first day of the following week
            if day_numbers:
                # Find the first day of the next week that has a standup
                next_week_day = min(day_numbers)
                days_until_next_week = 7 - now.weekday() + next_week_day

                next_date = tz.localize(
                    datetime.combine(
                        now.date() + timedelta(days=days_until_next_week),
                        datetime.min.time().replace(hour=hours, minute=minutes)
                    )
                )

                return next_date.timestamp()

            return None

        except Exception as e:
            import logging
            logging.getLogger('standup_bot.scheduler').error(f"Error calculating next occurrence: {e}")
            return None

    def _start_standup(self, standup_id: int) -> None:
        """Start a standup meeting"""
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) in standups and standups[str(standup_id)]['active']:
                standup = standups[str(standup_id)]

                # Check timezone handling
                if standup['timezone_handling'] == 'same':
                    # Same timezone for all participants - notify everyone now
                    for user_id in standup['participants']:
                        self._send_standup_questions(standup, user_id)
                else:
                    # Local timezone handling - schedule notifications for each participant
                    if self.timezone_manager:
                        for user_id in standup['participants']:
                            # Get user's timezone
                            user_timezone = self.timezone_manager.get_user_timezone(user_id)
                            standup_timezone = standup['schedule'].get('timezone', 'UTC')

                            # If user's timezone is different from standup timezone, schedule a notification
                            if user_timezone != standup_timezone:
                                # Convert standup time to user's local time
                                standup_time = standup['schedule']['time']
                                user_time = self.timezone_manager.convert_time(
                                    standup_time,
                                    standup_timezone,
                                    user_timezone
                                )

                                # Calculate when to send notification in user's timezone
                                now = datetime.datetime.now(pytz.timezone(user_timezone))
                                hours, minutes = map(int, user_time.split(':'))
                                target_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

                                # If target time is in the future today, schedule it
                                if target_time > now:
                                    self.schedule_task(
                                        target_time.timestamp(),
                                        f"standup_notify_{standup_id}_{user_id}",
                                        self._send_standup_questions,
                                        standup,
                                        user_id
                                    )
                                else:
                                    # Otherwise, send immediately
                                    self._send_standup_questions(standup, user_id)
                            else:
                                # User is in same timezone as standup, send now
                                self._send_standup_questions(standup, user_id)
                    else:
                        # Timezone manager not available, fall back to same timezone behavior
                        for user_id in standup['participants']:
                            self._send_standup_questions(standup, user_id)

                # Schedule the standup end
                # For local timezone handling, use the latest timezone's end time
                if standup['timezone_handling'] == 'local' and self.timezone_manager:
                    # Find the latest timezone among participants
                    latest_offset = -24 * 60 * 60  # Start with a very negative offset
                    latest_timezone = standup['schedule'].get('timezone', 'UTC')

                    for user_id in standup['participants']:
                        user_timezone = self.timezone_manager.get_user_timezone(user_id)
                        tz = pytz.timezone(user_timezone)
                        offset = tz.utcoffset(datetime.datetime.now()).total_seconds()

                        if offset > latest_offset:
                            latest_offset = offset
                            latest_timezone = user_timezone

                    # Add duration to the current time in the latest timezone
                    now = datetime.datetime.now(pytz.timezone(latest_timezone))
                    duration = standup['schedule'].get('duration', 24 * 60 * 60)  # Default 24h
                    end_time = (now + datetime.timedelta(seconds=duration)).timestamp()
                else:
                    # Same timezone for all - use standard duration
                    end_time = time.time() + standup['schedule'].get('duration', 24 * 60 * 60)  # Default 24h

                self.schedule_task(
                    end_time,
                    f"standup_end_{standup_id}",
                    self._end_standup,
                    standup_id
                )

                # Reschedule for next occurrence
                self._schedule_standup(standup)

    def _send_standup_questions(self, standup: Dict[str, Any], user_id: int) -> None:
        """
        Send standup questions to a user

        Args:
            standup: The standup configuration
            user_id: The user's ID
        """
        try:
            # Get standup details
            standup_id = standup['id']
            standup_name = standup['name']
            questions = standup['questions']

            # Format the message
            message = f"# Standup: {standup_name}\n\n"

            # Add timezone information if using local timezones
            if standup['timezone_handling'] == 'local' and self.timezone_manager:
                user_timezone = self.timezone_manager.get_user_timezone(user_id)
                standup_timezone = standup['schedule'].get('timezone', 'UTC')
                message += f"*Your timezone: {user_timezone}*\n\n"

            # Add instructions
            message += "Please respond to the following questions:\n\n"

            # Add questions
            for i, question in enumerate(questions, 1):
                message += f"{i}. **{question}**\n"

            # Add response instructions
            message += "\n\nTo respond, use the `status` command followed by your answers, like this:\n"
            message += f"```\nstatus {standup_id}\nI completed feature X\nI'm working on feature Y\nNo blockers\n```"

            # Send the message
            self.bot_handler.send_message({
                'type': 'private',
                'to': [user_id],
                'content': message
            })

            # Log the action
            logging.getLogger('standup_bot.scheduler').info(
                f"Sent standup questions for standup {standup_id} to user {user_id}"
            )

        except Exception as e:
            # Log the error
            logging.getLogger('standup_bot.scheduler').error(
                f"Error sending standup questions to user {user_id}: {e}"
            )

    def _end_standup(self, standup_id: int) -> None:
        """
        End a standup meeting and generate a report

        Args:
            standup_id: The ID of the standup to end
        """
        try:
            with self.storage.use_storage(['standups']) as cache:
                standups = cache.get('standups') or {}
                if str(standup_id) not in standups:
                    return

                standup = standups[str(standup_id)]

                # Get today's date
                today = datetime.datetime.now().strftime('%Y-%m-%d')

                # Check if there are any responses for today
                responses = standup.get('responses', {}).get(today, {})

                if not responses:
                    # No responses, log and return
                    logging.getLogger('standup_bot.scheduler').warning(
                        f"No responses for standup {standup_id} on {today}"
                    )
                    return

                # Generate report
                report = self._generate_report(standup, today)

                # Send report to the team stream
                team_stream = standup['team_stream']
                standup_name = standup['name']

                self.bot_handler.send_message({
                    'type': 'stream',
                    'to': team_stream,
                    'subject': f"Standup: {standup_name} - {today}",
                    'content': report
                })

                # Log the action
                logging.getLogger('standup_bot.scheduler').info(
                    f"Generated and sent report for standup {standup_id} on {today}"
                )

        except Exception as e:
            # Log the error
            logging.getLogger('standup_bot.scheduler').error(
                f"Error ending standup {standup_id}: {e}"
            )

    def _generate_report(self, standup: Dict[str, Any], date: str) -> str:
        """
        Generate a report for a standup

        Args:
            standup: The standup configuration
            date: The date for which to generate the report

        Returns:
            Formatted report as a string
        """
        standup_name = standup['name']
        responses = standup.get('responses', {}).get(date, {})
        questions = standup['questions']

        # Start with header
        report = f"# Standup Report: {standup_name}\n\n"
        report += f"**Date:** {date}\n"

        # Add timezone information if using local timezones
        if standup['timezone_handling'] == 'local':
            report += f"**Timezone Handling:** Adapted to local timezones\n"
        else:
            standup_timezone = standup['schedule'].get('timezone', 'UTC')
            report += f"**Timezone:** {standup_timezone}\n"

        report += f"**Participants:** {len(standup['participants'])}\n"
        report += f"**Responses:** {len(responses)}\n\n"

        # Calculate participation rate
        participation_rate = len(responses) / len(standup['participants']) * 100
        report += f"**Participation Rate:** {participation_rate:.1f}%\n\n"

        # Add responses by question
        report += "## Responses by Question\n\n"

        for i, question in enumerate(questions):
            report += f"### {i+1}. {question}\n\n"

            for user_id, response_data in responses.items():
                # Get user's response to this question
                user_responses = response_data.get('responses', {})
                if question in user_responses:
                    # In a real implementation, you would get the user's name
                    # For now, just use the user ID
                    report += f"**User {user_id}:** {user_responses[question]}\n\n"

        # Add responses by participant
        report += "## Responses by Participant\n\n"

        for user_id, response_data in responses.items():
            # In a real implementation, you would get the user's name
            report += f"### User {user_id}\n\n"

            user_responses = response_data.get('responses', {})
            for question in questions:
                if question in user_responses:
                    report += f"**{question}**\n{user_responses[question]}\n\n"

        return report
