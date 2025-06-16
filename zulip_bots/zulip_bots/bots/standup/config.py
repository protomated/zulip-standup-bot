import os
import logging
from typing import Any, Dict, Optional

class Config:
    """
    Configuration class for the Standup Bot.
    Loads configuration from environment variables with fallbacks to default values.
    """

    def __init__(self):
        # Zulip Configuration
        self.zulip_email = os.getenv('ZULIP_EMAIL')
        self.zulip_api_key = os.getenv('ZULIP_API_KEY')
        self.zulip_site = os.getenv('ZULIP_SITE')
        self.zulip_bot_name = os.getenv('ZULIP_BOT_NAME', 'Standup Bot')

        # OpenAI Configuration
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Database Configuration
        self.database_url = os.getenv('DATABASE_URL')

        # Bot Configuration
        self.default_timezone = os.getenv('DEFAULT_TIMEZONE', 'Africa/Lagos')
        self.default_prompt_time = os.getenv('DEFAULT_PROMPT_TIME', '09:30')
        self.default_cutoff_time = os.getenv('DEFAULT_CUTOFF_TIME', '12:45')
        self.default_reminder_time = os.getenv('DEFAULT_REMINDER_TIME', '11:45')

        # Logging Configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # Initialize logging
        self._setup_logging()

        # Validate required configuration
        self._validate_config()

    def _setup_logging(self) -> None:
        """
        Set up logging configuration.
        """
        numeric_level = getattr(logging, self.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO

        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _validate_config(self) -> None:
        """
        Validate that required configuration is present.
        """
        missing_vars = []

        # Check for required Zulip configuration
        if not self.zulip_email:
            missing_vars.append('ZULIP_EMAIL')
        if not self.zulip_api_key:
            missing_vars.append('ZULIP_API_KEY')
        if not self.zulip_site:
            missing_vars.append('ZULIP_SITE')

        # Log warnings for missing configuration
        if missing_vars:
            logging.warning(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Log warning for missing OpenAI API key
        if not self.openai_api_key:
            logging.warning("OPENAI_API_KEY not set. AI summary generation will not be available.")

        # Log warning for missing database URL
        if not self.database_url:
            logging.warning("DATABASE_URL not set. Will use in-memory storage instead.")

    def get_bot_config(self) -> Dict[str, Any]:
        """
        Get the bot configuration as a dictionary.
        """
        return {
            'openai_api_key': self.openai_api_key,
            'default_timezone': self.default_timezone,
            'default_prompt_time': self.default_prompt_time,
            'default_cutoff_time': self.default_cutoff_time,
            'default_reminder_time': self.default_reminder_time
        }

    def get_zulip_config(self) -> Dict[str, str]:
        """
        Get the Zulip configuration as a dictionary.
        """
        return {
            'email': self.zulip_email,
            'api_key': self.zulip_api_key,
            'site': self.zulip_site
        }

    def get_database_url(self) -> Optional[str]:
        """
        Get the database URL.
        """
        return self.database_url

# Create a singleton instance
config = Config()
