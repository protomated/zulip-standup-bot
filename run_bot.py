#!/usr/bin/env python3
import sys
import os
import argparse
import logging
import importlib.util
import traceback
import time
import glob
from zulip_bots.run import run_message_handler_for_bot
from zulip_bots.lib import zulip_env_vars_are_present

# Import our custom components
from error_handler import ErrorHandler
from monitoring import Monitoring
from health_check import HealthCheckServer
from backup_manager import BackupManager
from storage_manager import StorageManager
from rate_limiter import RateLimiter
from config import Config


def setup_logging(log_file=None, log_level=logging.INFO):
    """
    Set up logging configuration

    Args:
        log_file: Optional path to log file
        log_level: Logging level

    Returns:
        Logger instance
    """
    handlers = [logging.StreamHandler()]

    # Add file handler if log file is specified
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    return logging.getLogger('standup_bot')


def parse_args():
    parser = argparse.ArgumentParser(description='Run the Standup Bot')
    parser.add_argument('--config-file', '-c', required=False,
                        help='Path to the .zuliprc file')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--log-file', '-l', help='Path to log file')
    parser.add_argument('--health-check-port', '-p', type=int, default=8080,
                        help='Port for health check server')
    parser.add_argument('--disable-health-check', action='store_true',
                        help='Disable health check server')
    parser.add_argument('--disable-backups', action='store_true',
                        help='Disable automatic backups')
    return parser.parse_args()


def main():
    try:
        args = parse_args()
        log_level = logging.DEBUG if args.debug else logging.INFO
        logger = setup_logging(args.log_file, log_level)

        # Create error handler
        error_handler = ErrorHandler(logger)

        # Wrap the main function with error handling
        return run_bot_with_error_handling(args, logger, error_handler)
    except Exception as e:
        # Last resort error handling
        print(f"Critical error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


@ErrorHandler().with_error_handling(critical=True)
def find_and_restore_latest_backup(logger):
    """
    Find the latest backup file and restore it.

    This function is called when the bot starts to ensure data persistence
    across container recreations and deployments.

    Args:
        logger: Logger instance

    Returns:
        bool: True if a backup was restored, False otherwise
    """
    try:
        # Get backup directory from environment or use default
        backup_dir = os.environ.get('BACKUP_DIR', './backups')

        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            logger.info(f"Backup directory {backup_dir} does not exist. No backups to restore.")
            return False

        # Find all backup files
        backup_files = glob.glob(os.path.join(backup_dir, "*.json.gz"))
        if not backup_files:
            logger.info("No backup files found.")
            return False

        # Sort by modification time (newest first)
        backup_files.sort(key=os.path.getmtime, reverse=True)
        latest_backup = backup_files[0]

        logger.info(f"Found latest backup: {latest_backup}")

        # Create a temporary config and storage manager to restore the backup
        config = Config()
        storage_manager = StorageManager(None, config)
        backup_manager = BackupManager(storage_manager, config, logger)

        # Restore the backup
        success = backup_manager.restore_backup(latest_backup)
        if success:
            logger.info(f"Successfully restored from backup: {latest_backup}")
            return True
        else:
            logger.error(f"Failed to restore from backup: {latest_backup}")
            return False
    except Exception as e:
        logger.error(f"Error restoring from backup: {str(e)}", exc_info=True)
        return False


def run_bot_with_error_handling(args, logger, error_handler):
    """Run the bot with error handling"""
    bot_name = 'standup_bot'
    config_file = args.config_file

    # Attempt to restore from the latest backup
    find_and_restore_latest_backup(logger)

    # Check if environment variables are set
    env_vars_present = zulip_env_vars_are_present()

    if not config_file and not env_vars_present:
        # Try default locations for zuliprc
        default_locations = [
            os.path.join(os.getcwd(), 'zuliprc'),
            os.path.expanduser('~/.zuliprc'),
        ]

        for location in default_locations:
            if os.path.exists(location):
                config_file = location
                logger.info(f"Using default config file: {config_file}")
                break

        if not config_file:
            logger.error(
                "No configuration provided. Please either specify a config file "
                "with --config-file or set the ZULIP_EMAIL, ZULIP_API_KEY, and "
                "ZULIP_SITE environment variables."
            )
            sys.exit(1)

    if config_file:
        logger.info(f"Starting StandupBot with config file: {config_file}")
    else:
        logger.info("Starting StandupBot with environment variables")

    # Load the bot module
    bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standup_bot.py")
    spec = importlib.util.spec_from_file_location("standup_bot", bot_path)
    lib_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib_module)

    # Create monitoring system
    monitoring = Monitoring(logger)

    # Create rate limiter
    rate_limiter = RateLimiter(logger)

    # Set additional parameters
    quiet = not args.debug  # Set quiet mode based on debug flag
    bot_config_file = None  # No separate bot config file
    bot_source = "source"   # Bot source is from a file

    # Store components in the lib_module for access by the bot
    lib_module.StandupBotHandler.error_handler = error_handler
    lib_module.StandupBotHandler.monitoring = monitoring
    lib_module.StandupBotHandler.rate_limiter = rate_limiter

    # Start health check server if enabled
    health_check_server = None
    if not args.disable_health_check:
        try:
            health_check_server = HealthCheckServer(
                monitoring.get_health_status,
                port=args.health_check_port,
                logger=logger
            )
            health_check_server.start()
            lib_module.StandupBotHandler.health_check_server = health_check_server
        except Exception as e:
            logger.error(f"Failed to start health check server: {str(e)}", exc_info=True)

    # Call with all required parameters
    try:
        run_message_handler_for_bot(
            lib_module=lib_module,
            quiet=quiet,
            config_file=config_file,
            bot_config_file=bot_config_file,
            bot_name=bot_name,
            bot_source=bot_source
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}", exc_info=True)
    finally:
        # Clean up
        if health_check_server:
            health_check_server.stop()
        logger.info("Bot shutdown complete")


if __name__ == '__main__':
    main()
