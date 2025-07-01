#!/usr/bin/env python3
"""
Simple bot runner for the standup bot that avoids package import issues.
"""

import sys
import os
import logging

# Add the local paths first
sys.path.insert(0, '/app/zulip_bots/zulip_bots/bots/standup')
sys.path.insert(0, '/app/zulip_bots/zulip_bots')
sys.path.insert(0, '/app')

def main():
    """Run the standup bot directly."""

    # Set up logging
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    try:
        # Import required modules directly
        import zulip

        # Import the lib module directly instead of via package
        sys.path.insert(0, '/app/zulip_bots/zulip_bots')
        import lib

        # Import the standup bot handler directly
        import standup

        print("✅ All modules imported successfully")
        print(f"✅ Standup bot loaded from: {standup.__file__}")
        print(f"✅ Lib module loaded from: {lib.__file__}")

        # Configuration file
        config_file = '.zuliprc'
        if not os.path.exists(config_file):
            print(f"❌ Config file {config_file} not found")
            sys.exit(1)

        print(f"✅ Using config file: {config_file}")

        # Run the bot
        print("🚀 Starting standup bot...")
        lib.run_message_handler_for_bot(
            lib_module=standup,
            config_file=config_file,
            bot_config_file=None,
            quiet=False,
            bot_name='standup',
            bot_source='local'
        )

    except Exception as e:
        print(f"❌ Error running bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
