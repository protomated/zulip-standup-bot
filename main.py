#!/usr/bin/env python3
import sys
import os
import argparse
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
    run_message_handler_for_bot(bot_name, config_file)


if __name__ == '__main__':
    main()
