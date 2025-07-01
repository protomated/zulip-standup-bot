#!/usr/bin/env python3
"""
Generate botserverrc file from environment variables
"""

import os
from pathlib import Path

def generate_botrc():
    """Generate botserverrc from environment variables."""
    
    # Get environment variables
    zulip_email = os.getenv('ZULIP_EMAIL')
    zulip_api_key = os.getenv('ZULIP_API_KEY')
    zulip_site = os.getenv('ZULIP_SITE')
    groq_api_key = os.getenv('GROQ_API_KEY', '')
    default_timezone = os.getenv('DEFAULT_TIMEZONE', 'Africa/Lagos')
    
    if not all([zulip_email, zulip_api_key, zulip_site]):
        print("❌ Missing required environment variables: ZULIP_EMAIL, ZULIP_API_KEY, ZULIP_SITE")
        return False
    
    # Generate config content
    config_content = f"""[botserver]
# Auto-generated Zulip Bot Server Configuration

[standup]
# Bot class location
bot_module=zulip_bots.bots.standup.standup
bot_name=standup

# Zulip connection details
email={zulip_email}
key={zulip_api_key}
site={zulip_site}

# Additional configuration
groq_api_key={groq_api_key}
default_timezone={default_timezone}
"""
    
    # Write to file
    with open('botserverrc', 'w') as f:
        f.write(config_content)
    
    print("✅ Generated botserverrc from environment variables")
    return True

if __name__ == "__main__":
    generate_botrc()
