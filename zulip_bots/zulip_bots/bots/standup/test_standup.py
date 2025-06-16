from unittest.mock import patch, MagicMock
import time
import datetime
from typing import Dict, Any, List

from zulip_bots.test_lib import BotTestCase, DefaultTests, StubBotHandler


class TestStandupBot(BotTestCase, DefaultTests):
    bot_name: str = "standup"

    def test_help(self) -> None:
        bot_response = """
        Standup Bot - Helps teams run asynchronous standups in Zulip.

        Commands:
        * `/standup setup` - Activate standup for this channel
        * `/standup setup HH:MM` - Activate standup for this channel with a specific time (24h format)
        * `/standup timezone <timezone>` - Set your timezone (e.g., America/New_York)
        * `/standup pause` - Pause standup for this channel
        * `/standup resume` - Resume standup for this channel
        * `/standup status` - Check the status of standup for this channel
        * `/standup config prompt_time HH:MM` - Set the prompt time for standup
        * `/standup config cutoff_time HH:MM` - Set the cutoff time for standup responses
        * `/standup config reminder_time HH:MM` - Set the reminder time for standup
        * `/standup help` - Show this help message
        """
        with self.mock_config_info({}):
            self.verify_reply("", bot_response)
            self.verify_reply("help", bot_response)
            self.verify_reply("foo", bot_response)

    def test_invalid_command(self) -> None:
        with self.mock_config_info({}):
            self.verify_reply(
                "/standup invalid",
                "Unknown subcommand: invalid\n\n" + self.get_bot_response(""),
            )

    def test_setup_command_invalid_time(self) -> None:
        with self.mock_config_info({}):
            self.verify_reply(
                "/standup setup 25:00",
                "Invalid time format. Please use HH:MM in 24h format.",
            )

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_setup_command')
    def test_setup_command(self, mock_handle_setup) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup setup", mock_handle_setup.return_value)
            message = self.get_last_message()
            mock_handle_setup.assert_called_once_with(message, self.mock_bot_handler, [])

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_setup_command')
    def test_setup_command_with_time(self, mock_handle_setup) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup setup 14:30", mock_handle_setup.return_value)
            message = self.get_last_message()
            mock_handle_setup.assert_called_once_with(message, self.mock_bot_handler, ["14:30"])

    def test_private_message_setup(self) -> None:
        # Create a private message
        private_message = {
            'type': 'private',
            'display_recipient': [{'email': 'foo@example.com'}],
            'content': '/standup setup',
        }

        # Create a stub bot handler
        bot_handler = StubBotHandler()

        # Get the bot response
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)
            bot.handle_message(private_message, bot_handler)

        # Check that the bot responded with an error message
        self.assertEqual(
            bot_handler.last_message['content'],
            "This command must be used in a stream (channel)."
        )

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_timezone_command')
    def test_timezone_command(self, mock_handle_timezone) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup timezone America/New_York", mock_handle_timezone.return_value)
            message = self.get_last_message()
            mock_handle_timezone.assert_called_once_with(message, self.mock_bot_handler, ["America/New_York"])

    def test_timezone_command_invalid(self) -> None:
        with self.mock_config_info({}):
            self.verify_reply(
                "/standup timezone Invalid/Zone",
                "Invalid timezone: Invalid/Zone. Please use a valid timezone like 'America/New_York'."
            )

    def test_timezone_command_no_args(self) -> None:
        with self.mock_config_info({}):
            self.verify_reply(
                "/standup timezone",
                "Please specify a timezone (e.g., America/New_York)."
            )

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_pause_command')
    def test_pause_command(self, mock_handle_pause) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup pause", mock_handle_pause.return_value)
            message = self.get_last_message()
            mock_handle_pause.assert_called_once_with(message, self.mock_bot_handler)

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_resume_command')
    def test_resume_command(self, mock_handle_resume) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup resume", mock_handle_resume.return_value)
            message = self.get_last_message()
            mock_handle_resume.assert_called_once_with(message, self.mock_bot_handler)

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_status_command')
    def test_status_command(self, mock_handle_status) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup status", mock_handle_status.return_value)
            message = self.get_last_message()
            mock_handle_status.assert_called_once_with(message, self.mock_bot_handler)

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_config_command')
    def test_config_command(self, mock_handle_config) -> None:
        with self.mock_config_info({}):
            self.verify_reply("/standup config prompt_time 10:00", mock_handle_config.return_value)
            message = self.get_last_message()
            mock_handle_config.assert_called_once_with(message, self.mock_bot_handler, ["prompt_time", "10:00"])

    def test_config_command_invalid_option(self) -> None:
        # Create a stream message with a mock configuration
        stream_message = {
            'type': 'stream',
            'display_recipient': 'test-stream',
            'stream_id': 123,
            'subject': 'test topic',
            'content': '/standup config invalid_option 10:00',
        }

        # Create a stub bot handler with mock storage
        bot_handler = StubBotHandler()
        bot_handler.storage = MagicMock()
        bot_handler.storage.get.return_value = {
            'stream_id': 123,
            'stream_name': 'test-stream',
            'is_active': True
        }

        # Get the bot response
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)
            bot.handle_message(stream_message, bot_handler)

        # Check that the bot responded with an error message
        self.assertEqual(
            bot_handler.last_message['content'],
            "Unknown configuration option: invalid_option. Valid options are: prompt_time, cutoff_time, reminder_time."
        )

    def test_config_command_invalid_time(self) -> None:
        # Create a stream message with a mock configuration
        stream_message = {
            'type': 'stream',
            'display_recipient': 'test-stream',
            'stream_id': 123,
            'subject': 'test topic',
            'content': '/standup config prompt_time 25:00',
        }

        # Create a stub bot handler with mock storage
        bot_handler = StubBotHandler()
        bot_handler.storage = MagicMock()
        bot_handler.storage.get.return_value = {
            'stream_id': 123,
            'stream_name': 'test-stream',
            'is_active': True
        }

        # Get the bot response
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)
            bot.handle_message(stream_message, bot_handler)

        # Check that the bot responded with an error message
        self.assertEqual(
            bot_handler.last_message['content'],
            "Invalid time format. Please use HH:MM in 24h format."
        )

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._is_standup_response')
    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._handle_standup_response')
    def test_standup_response(self, mock_handle_response, mock_is_response) -> None:
        # Configure the mocks
        mock_is_response.return_value = True

        # Create a private message
        private_message = {
            'type': 'private',
            'display_recipient': [{'email': 'foo@example.com'}],
            'sender_id': 123,
            'sender_email': 'foo@example.com',
            'content': 'I worked on the API yesterday',
        }

        # Create a stub bot handler
        bot_handler = StubBotHandler()

        # Get the bot response
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)
            bot.handle_message(private_message, bot_handler)

        # Check that the response handler was called
        mock_handle_response.assert_called_once_with(private_message, bot_handler)

    @patch('zulip_bots.bots.standup.standup.StandupBotHandler._schedule_all_standups')
    def test_initialize(self, mock_schedule_all) -> None:
        # Create a stub bot handler
        bot_handler = StubBotHandler()
        bot_handler.get_config_info = MagicMock(return_value={
            'openai_api_key': 'test-key'
        })

        # Initialize the bot
        with self.mock_config_info({'openai_api_key': 'test-key'}):
            bot = self.get_bot_response("", bot_handler)

        # Check that the scheduler was initialized
        mock_schedule_all.assert_called_once()

    @patch('openai.ChatCompletion.create')
    def test_generate_ai_summary(self, mock_openai) -> None:
        # Configure the mock
        mock_openai.return_value.choices = [MagicMock(message=MagicMock(content="AI generated summary"))]

        # Create a stub bot handler
        bot_handler = StubBotHandler()
        bot_handler.get_config_info = MagicMock(return_value={
            'openai_api_key': 'test-key'
        })

        # Initialize the bot
        with self.mock_config_info({'openai_api_key': 'test-key'}):
            bot = self.get_bot_response("", bot_handler)

        # Test responses
        responses = [
            {
                'name': 'User 1',
                'yesterday': 'Worked on API',
                'today': 'Working on UI',
                'blockers': 'None'
            },
            {
                'name': 'User 2',
                'yesterday': 'Code review',
                'today': 'Testing',
                'blockers': 'Waiting for API'
            }
        ]

        # Call the method
        summary = bot._generate_ai_summary(responses)

        # Check that OpenAI was called
        mock_openai.assert_called_once()
        self.assertEqual(summary, "AI generated summary")

    def test_generate_manual_summary(self) -> None:
        # Create a stub bot handler
        bot_handler = StubBotHandler()

        # Initialize the bot
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)

        # Test responses
        responses = [
            {
                'name': 'User 1',
                'yesterday': 'Worked on API',
                'today': 'Working on UI',
                'blockers': 'None'
            },
            {
                'name': 'User 2',
                'yesterday': 'Code review',
                'today': 'Testing',
                'blockers': 'Waiting for API'
            }
        ]

        # Call the method
        summary = bot._generate_manual_summary(responses)

        # Check that the summary contains expected sections
        self.assertIn("# Daily Standup Summary", summary)
        self.assertIn("## Individual Updates", summary)
        self.assertIn("### User 1", summary)
        self.assertIn("### User 2", summary)
        self.assertIn("## Blockers Requiring Attention", summary)
        self.assertIn("- **User 2:** Waiting for API", summary)

    def test_is_valid_time_format(self) -> None:
        # Create a stub bot handler
        bot_handler = StubBotHandler()

        # Initialize the bot
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)

        # Test valid times
        self.assertTrue(bot._is_valid_time_format("00:00"))
        self.assertTrue(bot._is_valid_time_format("09:30"))
        self.assertTrue(bot._is_valid_time_format("23:59"))

        # Test invalid times
        self.assertFalse(bot._is_valid_time_format("24:00"))
        self.assertFalse(bot._is_valid_time_format("9:30"))
        self.assertFalse(bot._is_valid_time_format("09:60"))
        self.assertFalse(bot._is_valid_time_format("0900"))
        self.assertFalse(bot._is_valid_time_format("09-30"))

    def test_is_valid_timezone(self) -> None:
        # Create a stub bot handler
        bot_handler = StubBotHandler()

        # Initialize the bot
        with self.mock_config_info({}):
            bot = self.get_bot_response("", bot_handler)

        # Test valid timezones
        self.assertTrue(bot._is_valid_timezone("UTC"))
        self.assertTrue(bot._is_valid_timezone("America/New_York"))
        self.assertTrue(bot._is_valid_timezone("Africa/Lagos"))
        self.assertTrue(bot._is_valid_timezone("Europe/London"))

        # Test invalid timezones
        self.assertFalse(bot._is_valid_timezone("Invalid/Zone"))
        self.assertFalse(bot._is_valid_timezone("EST"))  # Abbreviations aren't valid
        self.assertFalse(bot._is_valid_timezone("New_York"))
        self.assertFalse(bot._is_valid_timezone("UTC+1"))  # Not a valid format
