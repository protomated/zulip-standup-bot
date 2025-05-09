#!/usr/bin/env python3
import sys
import os
import argparse
import logging
from zulip_bots.run import run_message_handler_for_bot
from zulip_bots.lib import zulip_env_vars_are_present


def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('standup_bot')


def parse_args():
    parser = argparse.ArgumentParser(description='Run the Standup Bot')
    parser.add_argument('--config-file', '-c', required=False,
                        help='Path to the .zuliprc file')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable debug logging')
    return parser.parse_args()


def main():
    args = parse_args()
    logger = setup_logging()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    bot_name = 'standup_bot'
    config_file = args.config_file

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

    run_message_handler_for_bot(bot_name, config_file)


if __name__ == '__main__':
    main()
