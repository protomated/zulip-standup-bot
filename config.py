import os
import configparser
from typing import Optional, Dict


class Config:
    """
    Configuration management for the Standup Bot.
    Supports both file-based configuration (.zuliprc) and environment variables.
    """

    def __init__(self, config_file: Optional[str] = None):
        # Zulip API credentials
        self.email = None
        self.api_key = None
        self.site = None

        # OpenAI API key for AI summaries
        self.openai_api_key = None

        # Email configuration for report distribution
        self.smtp_server = None
        self.smtp_port = 587  # Default to TLS port
        self.smtp_username = None
        self.smtp_password = None
        self.from_email = None

        # PostgreSQL database configuration
        self.db_host = None
        self.db_port = 5432  # Default PostgreSQL port
        self.db_name = None
        self.db_user = None
        self.db_password = None

        # Load configuration from file if provided
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)

        # Override with environment variables if provided
        self._load_from_env()

        # Validate configuration
        self._validate_config()

    def _load_from_file(self, config_file: str) -> None:
        """Load configuration from a .zuliprc file"""
        config = configparser.ConfigParser()
        config.read(config_file)

        if 'api' in config:
            self.email = config['api'].get('email')
            self.api_key = config['api'].get('key')
            self.site = config['api'].get('site')

        if 'openai' in config:
            self.openai_api_key = config['openai'].get('api_key')

        if 'email' in config:
            self.smtp_server = config['email'].get('smtp_server')
            self.smtp_port = config['email'].get('smtp_port', '587')
            self.smtp_username = config['email'].get('smtp_username')
            self.smtp_password = config['email'].get('smtp_password')
            self.from_email = config['email'].get('from_email')

        if 'database' in config:
            self.db_host = config['database'].get('host')
            self.db_port = config['database'].get('port', '5432')
            self.db_name = config['database'].get('name')
            self.db_user = config['database'].get('user')
            self.db_password = config['database'].get('password')

    def _load_from_env(self) -> None:
        """Load configuration from environment variables"""
        # Zulip API credentials
        if os.environ.get('ZULIP_EMAIL'):
            self.email = os.environ.get('ZULIP_EMAIL')

        if os.environ.get('ZULIP_API_KEY'):
            self.api_key = os.environ.get('ZULIP_API_KEY')

        if os.environ.get('ZULIP_SITE'):
            self.site = os.environ.get('ZULIP_SITE')

        # OpenAI API key
        if os.environ.get('OPENAI_API_KEY'):
            self.openai_api_key = os.environ.get('OPENAI_API_KEY')

        # Email configuration
        if os.environ.get('SMTP_SERVER'):
            self.smtp_server = os.environ.get('SMTP_SERVER')

        if os.environ.get('SMTP_PORT'):
            self.smtp_port = os.environ.get('SMTP_PORT')

        if os.environ.get('SMTP_USERNAME'):
            self.smtp_username = os.environ.get('SMTP_USERNAME')

        if os.environ.get('SMTP_PASSWORD'):
            self.smtp_password = os.environ.get('SMTP_PASSWORD')

        if os.environ.get('FROM_EMAIL'):
            self.from_email = os.environ.get('FROM_EMAIL')

        # PostgreSQL configuration
        if os.environ.get('DB_HOST'):
            self.db_host = os.environ.get('DB_HOST')

        if os.environ.get('DB_PORT'):
            self.db_port = os.environ.get('DB_PORT')

        if os.environ.get('DB_NAME'):
            self.db_name = os.environ.get('DB_NAME')

        if os.environ.get('DB_USER'):
            self.db_user = os.environ.get('DB_USER')

        if os.environ.get('DB_PASSWORD'):
            self.db_password = os.environ.get('DB_PASSWORD')

    def _validate_config(self) -> None:
        """Validate that required configuration is present"""
        if not all([self.email, self.api_key, self.site]):
            raise ValueError(
                "Missing required Zulip API credentials. "
                "Please provide them via .zuliprc file or environment variables "
                "(ZULIP_EMAIL, ZULIP_API_KEY, ZULIP_SITE)."
            )

    def get_zulip_config(self) -> dict:
        """Return Zulip API configuration as a dictionary"""
        return {
            'email': self.email,
            'api_key': self.api_key,
            'site': self.site
        }

    def get_email_config(self) -> dict:
        """Return email configuration as a dictionary"""
        return {
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'smtp_username': self.smtp_username,
            'smtp_password': self.smtp_password,
            'from_email': self.from_email
        }

    def get_db_config(self) -> Dict[str, str]:
        """Return database configuration as a dictionary"""
        return {
            'host': self.db_host,
            'port': self.db_port,
            'database': self.db_name,
            'user': self.db_user,
            'password': self.db_password
        }

    def is_email_configured(self) -> bool:
        """Check if email is configured"""
        return all([
            self.smtp_server,
            self.smtp_port,
            self.smtp_username,
            self.smtp_password,
            self.from_email
        ])

    def is_db_configured(self) -> bool:
        """Check if database is configured"""
        return all([
            self.db_host,
            self.db_port,
            self.db_name,
            self.db_user,
            self.db_password
        ])
