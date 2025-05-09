from typing import Dict, Any, List, Set
import zulip
from zulip_bots.lib import BotHandler
import json
import time
import datetime
import re
import os

from standup_manager import StandupManager
from storage_manager import StorageManager
from scheduler import ScheduleManager
from reminder_service import ReminderService
from ai_summary import AISummaryGenerator
from report_generator import ReportGenerator
from templates import Templates
from config import Config


class StandupBotHandler:
    """
    Main handler for the Standup Bot
    """

    def usage(self) -> str:
        return '''
        StandupBot - Automate your team's standups, check-ins, and recurring status meetings

        Commands:
        * `help` - Show this help message
        * `setup` - Set up a new standup meeting
        * `list` - List all standups you're part of
        * `status` - Submit your status for a standup
        * `remind` - Send reminders to users who haven't submitted their status
        * `report` - Generate a report for a standup
        * `cancel` - Cancel a standup meeting
        * `settings` - Change settings for a standup
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
        # Implementation for setting up a new standup
        # This would handle the interactive setup flow
        pass

    # More command handlers and helper methods
    # ...

    def _is_bot_mentioned(self, message: Dict[str, Any]) -> bool:
        """Check if the bot is mentioned in a message"""
        bot_username = self.bot_handler.user_email.split('@')[0]
        pattern = f"@\\*\\*{bot_username}\\*\\*"
        return bool(re.search(pattern, message['content']))

    def _extract_content_without_mention(self, message: Dict[str, Any]) -> str:
        """Remove the bot mention from the message content"""
        bot_username = self.bot_handler.user_email.split('@')[0]
        pattern = f"@\\*\\*{bot_username}\\*\\*"
        return re.sub(pattern, '', message['content']).strip()


handler_class = StandupBotHandler
