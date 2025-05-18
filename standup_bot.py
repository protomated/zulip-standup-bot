from typing import Dict, Any, List, Set
import zulip
from zulip_bots.lib import BotHandler
import json
import time
import datetime
import re
import os
import logging
import traceback

from standup_manager import StandupManager
from storage_manager import StorageManager
from scheduler import ScheduleManager
from reminder_service import ReminderService
from ai_summary import AISummaryGenerator
from report_generator import ReportGenerator
from templates import Templates
from config import Config
from setup_wizard import SetupWizard
from response_collector import ResponseCollector
from email_service import EmailService

# Import our custom components for operations and maintenance
from error_handler import ErrorHandler
from monitoring import Monitoring
from backup_manager import BackupManager
from rate_limiter import RateLimiter
from admin_commands import AdminCommands


class StandupBotHandler:
    """
    Main handler for the Standup Bot
    """
    # Class variables for components that can be set from outside
    error_handler = None
    monitoring = None
    rate_limiter = None
    health_check_server = None

    def usage(self) -> str:
        """Return a brief help message for the bot"""
        return '''
# StandupBot

Automate your team's standups, check-ins, and recurring status meetings.

## Quick Start
Type `setup` to create your first standup meeting in under 60 seconds.

## Basic Commands
* `help` - Show detailed help
* `setup` - Set up a new standup meeting
* `list` - List all standups you're part of
* `switch [standup_id]` - Set your active standup
* `status [standup_id]` - Submit your status
* `report [standup_id]` - Generate a report

## Multiple Standups
* Filter standups with `list team:TEAM` or `list project:PROJECT`
* Use `status` without an ID to submit for your active standup
* Manage permissions with `permissions [standup_id] [action]`

Type `help` for more detailed information.
'''

    def initialize(self, bot_handler: BotHandler) -> None:
        """
        Initialize the bot handler with all required components.
        This is called when the bot starts up.
        """
        self.bot_handler = bot_handler
        self.logger = logging.getLogger('standup_bot')

        # Initialize configuration
        config_file = bot_handler.get_config_info('standup_bot', optional=True)
        self.config = Config(config_file)
        self.logger.info(f"Bot initialized with email: {self.config.email}")

        # Initialize error handler if not already set
        if not self.__class__.error_handler:
            self.__class__.error_handler = ErrorHandler(self.logger)
        self.error_handler = self.__class__.error_handler

        # Initialize monitoring if not already set
        if not self.__class__.monitoring:
            self.__class__.monitoring = Monitoring(self.logger, self.config)
        self.monitoring = self.__class__.monitoring

        # Initialize rate limiter if not already set
        if not self.__class__.rate_limiter:
            self.__class__.rate_limiter = RateLimiter(self.logger)
        self.rate_limiter = self.__class__.rate_limiter

        # Initialize components
        self.storage_manager = StorageManager(bot_handler.storage, self.config)
        self.standup_manager = StandupManager(self.storage_manager, bot_handler)
        self.schedule_manager = ScheduleManager(self.storage_manager, bot_handler)
        self.reminder_service = ReminderService(self.storage_manager, bot_handler)
        self.ai_summary = AISummaryGenerator(self.config.openai_api_key)
        self.report_generator = ReportGenerator(self.storage_manager, self.ai_summary)
        self.templates = Templates()
        self.setup_wizard = SetupWizard(bot_handler, self.standup_manager, self.templates)
        self.response_collector = ResponseCollector(bot_handler, self.standup_manager, self.storage_manager)

        # Initialize email service if configured
        self.email_service = EmailService(self.config) if self.config.is_email_configured() else None
        if self.email_service:
            self.logger.info("Email service initialized")
        else:
            self.logger.warning("Email service not configured - email functionality will be disabled")

        # Initialize backup manager
        self.backup_manager = BackupManager(self.storage_manager, self.config, self.logger)

        # Initialize admin commands
        self.admin_commands = AdminCommands(
            bot_handler,
            self.storage_manager,
            self.error_handler,
            self.monitoring,
            self.backup_manager,
            self.rate_limiter,
            self.__class__.health_check_server,
            self.logger
        )

        # Initialize the scheduled tasks if any
        self.schedule_manager.initialize_scheduled_tasks()

        # Start scheduled backups if not disabled
        if not os.environ.get('DISABLE_BACKUPS', '').lower() in ('true', '1', 'yes'):
            self.backup_manager.start_scheduled_backups()
            self.logger.info("Scheduled backups started")

        # Check component health
        if self.monitoring:
            if hasattr(self.storage_manager, 'db_engine'):
                self.monitoring.check_database_health(self.storage_manager.db_engine)
            self.monitoring.check_zulip_api_health(bot_handler)
            self.monitoring.update_component_health('scheduler', 'healthy')
            self.monitoring.update_component_health('storage', 'healthy')

        self.logger.info("Bot initialization complete")

    def handle_message(self, message: Dict[str, Any], bot_handler: BotHandler) -> None:
        """
        Main message handler for the bot
        """
        start_time = time.time()
        sender_id = message.get('sender_id')

        try:
            # Check rate limits for the user
            if self.rate_limiter and not self.rate_limiter.is_allowed('user_commands', str(sender_id)):
                self.bot_handler.send_reply(message,
                    "You're sending commands too quickly. Please wait a moment before trying again.")
                return

            # Track command in monitoring
            if self.monitoring:
                self.monitoring.track_command(message.get('content', ''), 0)

            # Check for admin commands first
            if message.get('content', '').strip().startswith('admin'):
                if self.admin_commands.handle_admin_command(message):
                    # Command was handled by admin commands
                    return

            # Regular command handling
            if message['type'] == 'private':
                # Handle direct messages to the bot
                self._handle_private_message(message)
            elif message['type'] == 'stream' and self._is_bot_mentioned(message):
                # Handle stream messages where the bot is mentioned
                self._handle_stream_message(message)

        except Exception as e:
            # Log the error
            if self.error_handler:
                self.error_handler.log_exception(e, f"Error handling message: {message.get('content', '')}", critical=True)
            else:
                self.logger.error(f"Error handling message: {str(e)}", exc_info=True)

            # Track error in monitoring
            if self.monitoring:
                self.monitoring.track_error()

            # Send error message to user
            error_message = f"An error occurred while processing your request: {str(e)}"
            self.bot_handler.send_reply(message, error_message)
        finally:
            # Calculate execution time and update monitoring
            if self.monitoring:
                execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                self.monitoring.track_command(message.get('content', ''), execution_time)

    def _handle_private_message(self, message: Dict[str, Any]) -> None:
        """Handle direct messages sent to the bot"""
        content = message['content'].strip()
        sender_id = message['sender_id']

        # Check if user is in setup process
        if self.setup_wizard.is_user_in_setup(sender_id):
            # Handle response in setup process
            setup_complete = self.setup_wizard.handle_response(sender_id, content)
            if not setup_complete:
                # Setup is still in progress, no need to process as a command
                return
            # If setup is complete, acknowledge completion and return
            # This prevents falling through to normal command processing which could start a new setup
            return

        # Process as a normal command
        if content.startswith('setup'):
            self._handle_setup_command(message)
        elif content.startswith('list'):
            self._handle_list_command(message)
        elif content.startswith('switch'):
            self._handle_switch_command(message)
        elif content.startswith('status'):
            self._handle_status_command(message)
        elif content.startswith('remind'):
            self._handle_remind_command(message)
        elif content.startswith('report'):
            self._handle_report_command(message)
        elif content.startswith('cancel'):
            self._handle_cancel_command(message)
        elif content.startswith('settings'):
            self._handle_settings_command(message)
        elif content.startswith('permissions'):
            self._handle_permissions_command(message)
        elif content.startswith('help'):
            self.bot_handler.send_reply(message, self.templates.help_message())
        else:
            # Send help message by default
            self.bot_handler.send_reply(message, self.usage())

    def _handle_stream_message(self, message: Dict[str, Any]) -> None:
        """Handle stream messages where the bot is mentioned"""
        content = self._extract_content_without_mention(message)

        # Similar command handling logic as _handle_private_message
        # but adapted for stream context
        # ...

    # Helper methods for handling specific commands
    def _handle_setup_command(self, message: Dict[str, Any]) -> None:
        """
        Handle the setup command to start the interactive setup process
        """
        sender_id = message['sender_id']

        # Check if user is already in setup process
        if self.setup_wizard.is_user_in_setup(sender_id):
            self.bot_handler.send_reply(message,
                self.templates.error_message("You're already in the setup process. Please complete it or type 'cancel' to start over."))
            return

        # Start the setup process
        self.setup_wizard.start_setup(sender_id)

    # More command handlers and helper methods
    def _handle_list_command(self, message: Dict[str, Any]) -> None:
        """
        Handle the list command to display all standups the user is part of
        """
        sender_id = message['sender_id']
        content = message['content'].strip()

        # Parse command for filters
        team_filter = None
        project_filter = None

        # Check for team filter
        team_match = re.search(r'team:(\S+)', content)
        if team_match:
            team_filter = team_match.group(1)

        # Check for project filter
        project_match = re.search(r'project:(\S+)', content)
        if project_match:
            project_filter = project_match.group(1)

        # Get all standups for the user
        standups = self.standup_manager.get_standups_for_user(sender_id)

        if not standups:
            self.bot_handler.send_reply(message,
                "You're not part of any standups yet. Type `setup` to create your first standup.")
            return

        # Apply filters if specified
        if team_filter:
            standups = [s for s in standups if s.get('team_tag', '').lower() == team_filter.lower()]

        if project_filter:
            standups = [s for s in standups if s.get('project_tag', '').lower() == project_filter.lower()]

        if team_filter or project_filter:
            if not standups:
                filter_desc = []
                if team_filter:
                    filter_desc.append(f"team '{team_filter}'")
                if project_filter:
                    filter_desc.append(f"project '{project_filter}'")
                filter_str = " and ".join(filter_desc)
                self.bot_handler.send_reply(message, f"No standups found matching {filter_str}.")
                return

        # Format the standups into a readable message
        response = "# Your Standups\n\n"

        # Get user's active standup if any
        active_standup_id = self._get_user_active_standup(sender_id)

        for standup in standups:
            # Format schedule days
            days_map = {
                "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
                "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun"
            }
            days = [days_map.get(day, day) for day in standup['schedule']['days']]
            days_str = ", ".join(days)

            # Format active status
            status = "Active" if standup['active'] else "Inactive"

            # Mark current active standup
            current_marker = " ✓" if str(standup['id']) == str(active_standup_id) else ""

            # Add standup to the response
            response += f"## {standup['name']} (ID: {standup['id']}){current_marker}\n"
            response += f"**Status:** {status}\n"
            response += f"**Schedule:** {days_str} at {standup['schedule']['time']}\n"
            response += f"**Stream:** #{standup['team_stream']}\n"

            # Add team and project tags if present
            if standup.get('team_tag'):
                response += f"**Team:** {standup['team_tag']}\n"
            if standup.get('project_tag'):
                response += f"**Project:** {standup['project_tag']}\n"

            response += f"**Participants:** {len(standup['participants'])} members\n\n"

        response += "Use `switch [standup_id]` to set your active standup.\n"
        response += "Use `status` to submit your status for your active standup, or `status [standup_id]` for a specific standup.\n"
        response += "Filter standups with `list team:TEAM` or `list project:PROJECT`."

        self.bot_handler.send_reply(message, response)

    def _handle_switch_command(self, message: Dict[str, Any]) -> None:
        """
        Handle the switch command to set the active standup for a user
        """
        sender_id = message['sender_id']
        content = message['content'].strip()

        # Parse standup ID from command
        parts = content.split()
        if len(parts) < 2:
            self.bot_handler.send_reply(message,
                "Please specify a standup ID. Usage: `switch [standup_id]`")
            return

        try:
            standup_id = int(parts[1])
        except ValueError:
            self.bot_handler.send_reply(message,
                "Invalid standup ID. Please provide a numeric ID.")
            return

        # Check if standup exists and user has access
        standup = self.standup_manager.get_standup(standup_id)
        if not standup:
            self.bot_handler.send_reply(message,
                f"Standup with ID {standup_id} not found.")
            return

        # Check if user has permission to view this standup
        if not self.standup_manager.has_permission(standup_id, sender_id, 'view'):
            self.bot_handler.send_reply(message,
                f"You don't have permission to access standup {standup_id}.")
            return

        # Set as active standup for the user
        self._set_user_active_standup(sender_id, standup_id)

        self.bot_handler.send_reply(message,
            f"Switched to standup: **{standup['name']}**. You can now use `status` without specifying an ID.")

    def _handle_permissions_command(self, message: Dict[str, Any]) -> None:
        """
        Handle the permissions command to manage standup permissions
        """
        sender_id = message['sender_id']
        content = message['content'].strip()

        # Parse command
        parts = content.split()
        if len(parts) < 3:
            self.bot_handler.send_reply(message,
                "Usage: `permissions [standup_id] [action] [parameters]`\n\n" +
                "Actions:\n" +
                "- `add-admin @user` - Add a user as admin\n" +
                "- `remove-admin @user` - Remove a user as admin\n" +
                "- `set-edit [admin|participants|all]` - Set who can edit\n" +
                "- `set-view [admin|participants|all]` - Set who can view")
            return

        try:
            standup_id = int(parts[1])
            action = parts[2]
        except (ValueError, IndexError):
            self.bot_handler.send_reply(message,
                "Invalid command format. Please provide a numeric standup ID and an action.")
            return

        # Check if standup exists
        standup = self.standup_manager.get_standup(standup_id)
        if not standup:
            self.bot_handler.send_reply(message,
                f"Standup with ID {standup_id} not found.")
            return

        # Check if user has admin permission
        if not self.standup_manager.has_permission(standup_id, sender_id, 'admin'):
            self.bot_handler.send_reply(message,
                f"You don't have admin permission for standup {standup_id}.")
            return

        # Handle different actions
        if action == 'add-admin' and len(parts) >= 4:
            # Extract user from mention
            user_mention = ' '.join(parts[3:])
            user_id = self._extract_user_id_from_mention(user_mention)

            if not user_id:
                self.bot_handler.send_reply(message,
                    "Invalid user mention. Please use the format `@user`.")
                return

            if self.standup_manager.add_admin(standup_id, user_id, sender_id):
                self.bot_handler.send_reply(message,
                    f"Added user as admin for standup {standup_id}.")
            else:
                self.bot_handler.send_reply(message,
                    f"Failed to add user as admin.")

        elif action == 'remove-admin' and len(parts) >= 4:
            # Extract user from mention
            user_mention = ' '.join(parts[3:])
            user_id = self._extract_user_id_from_mention(user_mention)

            if not user_id:
                self.bot_handler.send_reply(message,
                    "Invalid user mention. Please use the format `@user`.")
                return

            if self.standup_manager.remove_admin(standup_id, user_id, sender_id):
                self.bot_handler.send_reply(message,
                    f"Removed user as admin for standup {standup_id}.")
            else:
                self.bot_handler.send_reply(message,
                    f"Failed to remove user as admin. Note: The creator cannot be removed as admin.")

        elif action == 'set-edit' and len(parts) >= 4:
            permission = parts[3]
            if permission not in ['admin', 'participants', 'all']:
                self.bot_handler.send_reply(message,
                    "Invalid permission value. Use 'admin', 'participants', or 'all'.")
                return

            if self.standup_manager.update_permissions(standup_id, {'can_edit': permission}, sender_id):
                self.bot_handler.send_reply(message,
                    f"Updated edit permissions for standup {standup_id} to '{permission}'.")
            else:
                self.bot_handler.send_reply(message,
                    f"Failed to update permissions.")

        elif action == 'set-view' and len(parts) >= 4:
            permission = parts[3]
            if permission not in ['admin', 'participants', 'all']:
                self.bot_handler.send_reply(message,
                    "Invalid permission value. Use 'admin', 'participants', or 'all'.")
                return

            if self.standup_manager.update_permissions(standup_id, {'can_view': permission}, sender_id):
                self.bot_handler.send_reply(message,
                    f"Updated view permissions for standup {standup_id} to '{permission}'.")
            else:
                self.bot_handler.send_reply(message,
                    f"Failed to update permissions.")

        else:
            self.bot_handler.send_reply(message,
                "Invalid action or missing parameters. Type `permissions` for usage help.")

    def _get_user_active_standup(self, user_id: int) -> Optional[int]:
        """Get the active standup ID for a user"""
        with self.bot_handler.storage.use_storage(['user_preferences']) as cache:
            preferences = cache.get('user_preferences') or {}
            user_prefs = preferences.get(str(user_id), {})
            return user_prefs.get('active_standup')

    def _set_user_active_standup(self, user_id: int, standup_id: int) -> None:
        """Set the active standup ID for a user"""
        with self.bot_handler.storage.use_storage(['user_preferences']) as cache:
            preferences = cache.get('user_preferences') or {}
            user_prefs = preferences.get(str(user_id), {})
            user_prefs['active_standup'] = standup_id
            preferences[str(user_id)] = user_prefs
            cache['user_preferences'] = preferences

    def _extract_user_id_from_mention(self, mention: str) -> Optional[int]:
        """Extract user ID from a mention string"""
        # In a real implementation, you would use the Zulip API to resolve user names to IDs
        # For now, we'll use a placeholder mapping
        mention_pattern = r'@\*\*([^*]+)\*\*'
        match = re.search(mention_pattern, mention)

        if not match:
            return None

        user_name = match.group(1)
        user_mapping = {
            'Alice': 101,
            'Bob': 102,
            'Charlie': 103,
            # Add more mappings as needed
        }

        return user_mapping.get(user_name)

    def _handle_status_command(self, message: Dict[str, Any]) -> None:
        """
        Handle the status command to submit a status update for a standup
        """
        sender_id = message['sender_id']
        content = message['content'].strip()

        # Parse standup ID from command if provided
        standup_id = None
        parts = content.split()

        if len(parts) >= 2:
            try:
                standup_id = int(parts[1])
            except ValueError:
                # Not a numeric ID, might be the start of a status update
                pass

        # If no standup ID provided, use the active standup
        if standup_id is None:
            standup_id = self._get_user_active_standup(sender_id)

            if standup_id is None:
                self.bot_handler.send_reply(message,
                    "No active standup set. Please specify a standup ID or use `switch [standup_id]` to set an active standup.")
                return

        # Check if standup exists
        standup = self.standup_manager.get_standup(standup_id)
        if not standup:
            self.bot_handler.send_reply(message,
                f"Standup with ID {standup_id} not found.")
            return

        # Check if user has permission to submit status
        if not self.standup_manager.has_permission(standup_id, sender_id, 'view'):
            self.bot_handler.send_reply(message,
                f"You don't have permission to access standup {standup_id}.")
            return

        # Check if user is a participant
        if sender_id not in standup.get('participants', []) and sender_id != standup.get('creator_id'):
            self.bot_handler.send_reply(message,
                f"You are not a participant in standup {standup_id}.")
            return

        # If this is just a status command without content, prompt for responses
        if len(parts) <= 2 or (len(parts) == 2 and standup_id == int(parts[1])):
            # Use the response collector to format questions
            response = self.response_collector.format_questions(standup_id)
            self.bot_handler.send_reply(message, response)
            return

        # Process status update
        # If we get here, the user has provided answers in the command
        # Extract the answers from the message content

        # Skip the command and standup ID if present
        content_start = content.find(' ', content.find(' ') + 1) + 1 if standup_id == int(parts[1]) else content.find(' ') + 1
        answers_text = content[content_start:].strip()

        # Use the response collector to validate and save responses
        success, response_message = self.response_collector.collect_and_validate_responses(
            standup_id, sender_id, answers_text
        )

        self.bot_handler.send_reply(message, response_message)

    def _is_bot_mentioned(self, message: Dict[str, Any]) -> bool:
        """Check if the bot is mentioned in a message"""
        bot_username = self.config.email.split('@')[0]
        pattern = f"@\\*\\*{bot_username}\\*\\*"
        return bool(re.search(pattern, message['content']))

    def _extract_content_without_mention(self, message: Dict[str, Any]) -> str:
        """Remove the bot mention from the message content"""
        bot_username = self.config.email.split('@')[0]
        pattern = f"@\\*\\*{bot_username}\\*\\*"
        return re.sub(pattern, '', message['content']).strip()

    def _handle_report_command(self, message: Dict[str, Any]) -> None:
        """
        Handle the report command to generate and send a standup report

        Command format:
        report [standup_id] [date] [format] [email]

        - standup_id: ID of the standup (required)
        - date: Date in YYYY-MM-DD format (optional, defaults to today)
        - format: Report format (optional, defaults to user preference or 'standard')
        - email: Email address to send report to (optional, defaults to user preference)
        """
        sender_id = message['sender_id']
        content = message['content'].strip()

        # Get user report settings
        user_settings = self.storage_manager.get_user_report_settings(sender_id)

        # Parse command arguments
        parts = content.split()

        # Check if this is a settings command
        if len(parts) >= 2 and parts[1] == 'settings':
            self._handle_report_settings_command(message, parts[2:] if len(parts) > 2 else [])
            return

        # Check if standup ID is provided
        if len(parts) < 2:
            self.bot_handler.send_reply(message,
                "Please specify a standup ID. Usage: `report [standup_id] [date] [format] [email]`\n" +
                "Or use `report settings` to manage your report preferences.")
            return

        try:
            standup_id = int(parts[1])
        except ValueError:
            self.bot_handler.send_reply(message,
                "Invalid standup ID. Please provide a numeric ID.")
            return

        # Check if standup exists
        standup = self.standup_manager.get_standup(standup_id)
        if not standup:
            self.bot_handler.send_reply(message,
                f"Standup with ID {standup_id} not found.")
            return

        # Check if user has permission to view this standup
        if not self.standup_manager.has_permission(standup_id, sender_id, 'view'):
            self.bot_handler.send_reply(message,
                f"You don't have permission to access standup {standup_id}.")
            return

        # Parse date if provided
        date = None
        if len(parts) >= 3 and re.match(r'^\d{4}-\d{2}-\d{2}$', parts[2]):
            date = parts[2]

        # Parse format if provided, otherwise use user preference
        report_format = user_settings.get('default_format', 'standard')
        if len(parts) >= 4:
            if parts[3] in ['standard', 'detailed', 'summary', 'compact']:
                report_format = parts[3]

        # Parse email if provided, otherwise use user preference if enabled
        email = None
        if len(parts) >= 5 and '@' in parts[4]:
            email = parts[4]
        elif user_settings.get('email_reports', False) and user_settings.get('default_email'):
            email = user_settings.get('default_email')

        # Generate the report
        report = self.report_generator.generate_report(standup_id, date)

        if "error" in report:
            self.bot_handler.send_reply(message, f"Error generating report: {report['error']}")
            return

        # Format the report message based on the requested format
        formatted_report = self.report_generator.format_report_message(report, report_format)

        # Send the report to the user
        self.bot_handler.send_reply(message, formatted_report)

        # If email is provided or enabled in settings, send the report via email
        if email:
            if not self.email_service:
                self.bot_handler.send_reply(message,
                    "Email service is not configured. Please contact your administrator to enable email functionality.")
                return

            try:
                # Generate a subject for the email
                subject = f"Standup Report: {report['standup_name']} - {report['date']}"

                # Send the email
                success = self.email_service.send_report(
                    to_email=email,
                    report_markdown=formatted_report,
                    subject=subject
                )

                if success:
                    self.bot_handler.send_reply(message,
                        f"Report has been sent to {email}.")
                else:
                    self.bot_handler.send_reply(message,
                        f"Failed to send email to {email}. Please check the email address and try again.")
            except Exception as e:
                self.logger.error(f"Email error: {str(e)}")
                self.bot_handler.send_reply(message,
                    f"Failed to send email: {str(e)}")

    def _handle_report_settings_command(self, message: Dict[str, Any], args: List[str]) -> None:
        """
        Handle the report settings command to manage user report preferences

        Command format:
        report settings [setting] [value]

        Settings:
        - format [standard|detailed|summary|compact]: Set default report format
        - email [on|off]: Enable/disable email reports
        - set-email [email]: Set default email address
        """
        sender_id = message['sender_id']

        # Get current settings
        settings = self.storage_manager.get_user_report_settings(sender_id)

        # If no arguments, show current settings
        if not args:
            email_status = "enabled" if settings.get('email_reports', False) else "disabled"
            email_address = settings.get('default_email', 'not set')

            response = "# Your Report Settings\n\n"
            response += f"**Default Format:** {settings.get('default_format', 'standard')}\n"
            response += f"**Email Reports:** {email_status}\n"
            response += f"**Default Email:** {email_address}\n\n"
            response += "To change settings, use:\n"
            response += "- `report settings format [standard|detailed|summary|compact]`\n"
            response += "- `report settings email [on|off]`\n"
            response += "- `report settings set-email [email]`\n"

            self.bot_handler.send_reply(message, response)
            return

        # Handle setting changes
        if len(args) >= 2:
            setting = args[0].lower()
            value = args[1].lower()

            if setting == 'format':
                if value in ['standard', 'detailed', 'summary', 'compact']:
                    self.storage_manager.save_user_report_settings(sender_id, {'default_format': value})
                    self.bot_handler.send_reply(message, f"Default report format set to **{value}**.")
                else:
                    self.bot_handler.send_reply(message,
                        "Invalid format. Please use one of: standard, detailed, summary, compact.")

            elif setting == 'email':
                if value in ['on', 'true', 'yes', 'enable']:
                    self.storage_manager.save_user_report_settings(sender_id, {'email_reports': True})

                    # Check if email is set
                    if not settings.get('default_email'):
                        self.bot_handler.send_reply(message,
                            "Email reports enabled. Please set your email address with `report settings set-email [email]`.")
                    else:
                        self.bot_handler.send_reply(message,
                            f"Email reports enabled. Reports will be sent to {settings.get('default_email')}.")

                elif value in ['off', 'false', 'no', 'disable']:
                    self.storage_manager.save_user_report_settings(sender_id, {'email_reports': False})
                    self.bot_handler.send_reply(message, "Email reports disabled.")
                else:
                    self.bot_handler.send_reply(message,
                        "Invalid value. Please use 'on' or 'off'.")

            elif setting == 'set-email':
                # Simple email validation
                if '@' in value and '.' in value:
                    self.storage_manager.save_user_report_settings(sender_id, {'default_email': value})
                    self.bot_handler.send_reply(message, f"Default email address set to {value}.")
                else:
                    self.bot_handler.send_reply(message,
                        "Invalid email address. Please provide a valid email.")
            else:
                self.bot_handler.send_reply(message,
                    "Unknown setting. Available settings: format, email, set-email.")
        else:
            self.bot_handler.send_reply(message,
                "Please provide a setting and value. Example: `report settings format detailed`")


handler_class = StandupBotHandler
