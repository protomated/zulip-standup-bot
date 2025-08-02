#!/usr/bin/env python3
"""
Script to run the Zulip bot server with environment variables loaded from .env file.
"""

import os
import sys
import subprocess
from pathlib import Path

def load_env_file(env_file_path: str):
    """Load environment variables from a .env file."""
    env_vars = {}
    try:
        with open(env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
                    os.environ[key] = value
        print(f"✅ Loaded {len(env_vars)} environment variables from {env_file_path}")
        return env_vars
    except FileNotFoundError:
        print(f"❌ Environment file {env_file_path} not found")
        return {}
    except Exception as e:
        print(f"❌ Error loading environment file: {e}")
        return {}

def main():
    """Main function to run the bot server."""
    print("🤖 Starting Zulip Standup Bot Server")
    print("=" * 40)

    # Get the project root directory
    project_root = Path(__file__).parent
    env_file = project_root / ".env"

    # Load environment variables
    print(f"\n📄 Loading environment variables from {env_file}")
    env_vars = load_env_file(str(env_file))

    if not env_vars:
        print("❌ Failed to load environment variables. Please check your .env file.")
        sys.exit(1)

    # Check required variables
    required_vars = ['ZULIP_BOTSERVER_CONFIG']
    missing_vars = []

    for var in required_vars:
        if var not in os.environ:
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    print("✅ All required environment variables are set")

    # Determine the bot server executable path
    venv_path = project_root / "zulip-api-py3-venv"
    bot_server_path = venv_path / "bin" / "zulip-botserver"

    if not bot_server_path.exists():
        print(f"❌ Bot server executable not found at: {bot_server_path}")
        print("   Please run: ./tools/provision to set up the virtual environment")
        sys.exit(1)

    # Build the command
    cmd = [
        str(bot_server_path),
        "--use-env-vars",  # Use environment variables instead of config file
        "--port", "5003"
    ]

    print(f"\n🚀 Starting bot server with command:")
    print(f"   {' '.join(cmd)}")
    print(f"\n📊 Bot will be available at: http://localhost:5002")
    print(f"📝 Press Ctrl+C to stop the bot server")
    print("-" * 40)

    try:
        # Run the bot server
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n🛑 Bot server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Bot server failed with exit code: {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
