#!/usr/bin/env python3
"""
Production script to run the Zulip Standup Bot.
Works both locally and in Docker/CapRover environments.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
import time
import json

# Add the local paths first to override installed packages
sys.path.insert(0, '/app/zulip_bots/zulip_bots/bots/standup')
sys.path.insert(0, '/app/zulip_bots/zulip_bots')
sys.path.insert(0, '/app')

def setup_logging():
    """Set up logging configuration."""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/app/data/standup_bot.log') if Path('/app/data').exists() else logging.NullHandler()
        ]
    )

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)
        print(f"✅ Loaded environment variables from {env_file}")

def check_required_env_vars():
    """Check that required environment variables are set."""
    required_vars = [
        'ZULIP_EMAIL',
        'ZULIP_API_KEY',
        'ZULIP_SITE'
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("\nRequired variables:")
        print("  ZULIP_EMAIL=your-bot@domain.com")
        print("  ZULIP_API_KEY=your_api_key")
        print("  ZULIP_SITE=https://your-zulip.com")
        print("\nOptional variables:")
        print("  GROQ_API_KEY=your_groq_key (for AI summaries)")
        print("  SQLITE_DB_PATH=./data/standup.db")
        print("  DEFAULT_TIMEZONE=Africa/Lagos")
        return False

    return True

def generate_zuliprc():
    """Generate .zuliprc file from environment variables."""

    # Get environment variables
    zulip_email = os.getenv('ZULIP_EMAIL')
    zulip_api_key = os.getenv('ZULIP_API_KEY')
    zulip_site = os.getenv('ZULIP_SITE')

    # Generate zuliprc content
    config_content = f"""[api]
email={zulip_email}
key={zulip_api_key}
site={zulip_site}
"""

    # Write to file
    with open('.zuliprc', 'w') as f:
        f.write(config_content)

    print("🔧 Generated .zuliprc from environment variables")
    return True

def run_bot_direct():
    """Run the bot directly using zulip-run-bot."""
    print("🤖 Starting Zulip Standup Bot...")
    print("=" * 50)

    # Check if we're in development or production
    is_docker = Path('/.dockerenv').exists() or os.getenv('DOCKER_ENV') == 'true'

    if is_docker:
        print("🐳 Running in Docker environment")
        bot_runner_path = 'zulip-run-bot'
    else:
        print("💻 Running in local development environment")
        # Load .env file for local development
        load_env_file()

        # Find bot runner executable
        venv_path = Path('zulip-api-py3-venv/bin/zulip-run-bot')
        if venv_path.exists():
            bot_runner_path = str(venv_path)
        else:
            bot_runner_path = 'zulip-run-bot'

    # Verify required environment variables
    if not check_required_env_vars():
        sys.exit(1)

    # Generate .zuliprc from environment variables
    if not generate_zuliprc():
        sys.exit(1)

    # Create data directory if it doesn't exist
    data_dir = Path(os.getenv('SQLITE_DB_PATH', './data/standup.db')).parent
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"📊 Database directory: {data_dir.absolute()}")
    print(f"🌍 Bot site: {os.getenv('ZULIP_SITE')}")
    print(f"📧 Bot email: {os.getenv('ZULIP_EMAIL')}")
    print(f"🤖 AI summaries: {'✅ Enabled' if os.getenv('GROQ_API_KEY') else '❌ Disabled'}")

    # Build command to run the standup bot directly
    cmd = [
        bot_runner_path,
        'zulip_bots.bots.standup.standup',
        '--config-file', '.zuliprc'
    ]

    print(f"\n🚀 Starting bot: {' '.join(cmd)}")
    print(f"📝 Logs: Check console output")
    print("-" * 50)

    try:
        # Run the bot
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Bot failed with exit code: {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n❌ Bot runner executable not found: {bot_runner_path}")
        print("💡 Try running: ./tools/provision")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    setup_logging()

    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print(__doc__)
            print("\nUsage: python run_standup_bot.py")
            print("\nEnvironment variables:")
            print("  ZULIP_EMAIL     - Bot email address (required)")
            print("  ZULIP_API_KEY   - Bot API key (required)")
            print("  ZULIP_SITE      - Zulip server URL (required)")
            print("  GROQ_API_KEY    - Groq API key for AI summaries (optional)")
            print("  SQLITE_DB_PATH  - Database file path (optional)")
            print("  LOG_LEVEL       - Logging level (optional, default: INFO)")
            return
        elif sys.argv[1] == '--check':
            print("🔍 Checking configuration...")
            load_env_file()
            if check_required_env_vars():
                print("✅ Configuration is valid!")
            else:
                sys.exit(1)
            return

    run_bot_direct()

if __name__ == "__main__":
    main()
