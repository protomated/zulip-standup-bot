import os
import configparser
from typing import Optional


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
