from typing import Dict, Any, List, Set
import zulip
from zulip_bots.lib import BotHandler
import json
import time
import datetime
import re
import os
import logging

from standup_manager import StandupManager
from storage_manager import StorageManager
from scheduler import ScheduleManager
from reminder_service import ReminderService
from ai_summary import AISummaryGenerator
from report_generator import ReportGenerator
from templates import Templates
from config import Config
from setup_wizard import SetupWizard


class StandupBotHandler:
    """
    Main handler for the Standup Bot
    """

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
* `status [standup_id]` - Submit your status
* `report [standup_id]` - Generate a report

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

        # Initialize components
        self.storage_manager = StorageManager(bot_handler.storage)
        self.standup_manager = StandupManager(self.storage_manager, bot_handler)
        self.schedule_manager = ScheduleManager(self.storage_manager, bot_handler)
        self.reminder_service = ReminderService(self.storage_manager, bot_handler)
        self.ai_summary = AISummaryGenerator(self.config.openai_api_key)
        self.report_generator = ReportGenerator(self.storage_manager, self.ai_summary)
        self.templates = Templates()
        self.setup_wizard = SetupWizard(bot_handler, self.standup_manager, self.templates)

        # Initialize the scheduled tasks if any
        self.schedule_manager.initialize_scheduled_tasks()

        self.logger.info("Bot initialization complete")

    def handle_message(self, message: Dict[str, Any], bot_handler: BotHandler) -> None:
        """
        Main message handler for the bot
        """
        if message['type'] == 'private':
            # Handle direct messages to the bot
            self._handle_private_message(message)
        elif message['type'] == 'stream' and self._is_bot_mentioned(message):
            # Handle stream messages where the bot is mentioned
            self._handle_stream_message(message)

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

        # Get all standups for the user
        standups = self.standup_manager.get_standups_for_user(sender_id)

        if not standups:
            self.bot_handler.send_reply(message,
                "You're not part of any standups yet. Type `setup` to create your first standup.")
            return

        # Format the standups into a readable message
        response = "# Your Standups\n\n"

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

            # Add standup to the response
            response += f"## {standup['name']} (ID: {standup['id']})\n"
            response += f"**Status:** {status}\n"
            response += f"**Schedule:** {days_str} at {standup['schedule']['time']}\n"
            response += f"**Stream:** #{standup['team_stream']}\n"
            response += f"**Participants:** {len(standup['participants'])} members\n\n"

        response += "Use `status [standup_id]` to submit your status for a specific standup."

        self.bot_handler.send_reply(message, response)

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


handler_class = StandupBotHandler
