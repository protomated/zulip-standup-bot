#!/usr/bin/env python3
import sys
import os
import argparse
import importlib.util
from zulip_bots.run import run_message_handler_for_bot


def parse_args():
    parser = argparse.ArgumentParser(description='Run the Standup Bot')
    parser.add_argument('--config-file', '-c', required=True,
                        help='Path to the .zuliprc file')
    return parser.parse_args()


def main():
    args = parse_args()
    bot_name = 'standup_bot'
    config_file = args.config_file

    print(f"Starting StandupBot with config: {config_file}")

    # Load the bot module
    bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standup_bot.py")
    spec = importlib.util.spec_from_file_location("standup_bot", bot_path)
    lib_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib_module)

    # Set additional parameters
    quiet = False  # Don't run in quiet mode
    bot_config_file = None  # No separate bot config file
    bot_source = "source"   # Bot source is from a file

    # Call with all required parameters
    run_message_handler_for_bot(
        lib_module=lib_module,
        quiet=quiet,
        config_file=config_file,
        bot_config_file=bot_config_file,
        bot_name=bot_name,
        bot_source=bot_source
    )


if __name__ == '__main__':
    main()
