from zulip_bots.test_lib import BotTestCase, DefaultTests


class TestStandupBot(BotTestCase, DefaultTests):
    bot_name: str = "standup"

    def test_help_command(self) -> None:
        """Test that help command returns usage information."""
        with self.mock_config_info({}):
            response = self.get_response(self.make_request_message("help"))
            self.assertIn("Standup Bot", response["content"])
            self.assertIn("/standup setup", response["content"])

    def test_standup_setup_in_private_message(self) -> None:
        """Test that setup command requires stream context."""
        with self.mock_config_info({}):
            # Create a private message
            message = {
                "type": "private",
                "content": "/standup setup",
                "sender_id": 123,
                "sender_email": "test@example.com",
                "display_recipient": [{"id": 123, "email": "test@example.com"}],
            }
            response = self.get_response(message)
            self.assertIn("must be used in a stream", response["content"])

    def test_timezone_command(self) -> None:
        """Test timezone setting command."""
        with self.mock_config_info({}):
            response = self.get_response(self.make_request_message("/standup timezone America/New_York"))
            self.assertIn("timezone has been set", response["content"])

    def test_invalid_timezone(self) -> None:
        """Test invalid timezone handling."""
        with self.mock_config_info({}):
            response = self.get_response(self.make_request_message("/standup timezone Invalid/Timezone"))
            self.assertIn("Invalid timezone", response["content"])

    def test_unknown_command(self) -> None:
        """Test unknown subcommand handling."""
        with self.mock_config_info({}):
            response = self.get_response(self.make_request_message("/standup unknown"))
            self.assertIn("Unknown subcommand", response["content"])

    def test_bot_responds_to_empty_message(self) -> None:
        """Test bot responds to empty message with usage."""
        with self.mock_config_info({}):
            message = self.make_request_message("")
            response = self.get_response(message)
            # Should show usage information
            self.assertIn("Standup Bot", response["content"])

    def make_request_message(self, content: str) -> dict:
        """Create a test message."""
        return {
            "type": "stream",
            "content": content,
            "sender_id": 123,
            "sender_email": "test@example.com",
            "display_recipient": "test-stream",
            "stream_id": 456,
            "subject": "test topic",
        }
