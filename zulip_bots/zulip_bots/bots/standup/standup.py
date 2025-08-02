"""
Zulip Standup Bot - Production Ready Implementation
Manages asynchronous team standups with automated scheduling.
"""

# Import lib directly since we're using direct path approach
import sys
sys.path.insert(0, '/app/zulip_bots/zulip_bots')
from lib import AbstractBotHandler

import re
import os
import json
import time
import logging
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

# Direct imports for local modules
import database
import config
import ai_summary


class StandupHandler(AbstractBotHandler):
    """
    Production-ready Zulip bot for managing team standups.
    Features:
    - Automated daily scheduling
    - Multi-timezone support
    - SQLite persistence
    - AI-powered summaries
    - Error recovery
    """

    def usage(self) -> str:
        return """
        **Standup Bot** - Automates daily team standups

        **Setup Commands:**
        • `/standup setup` - Activate standup (default: 09:30, 11:45, 12:45)
        • `/standup setup HH:MM` - Custom prompt time
        • `/standup setup HH:MM HH:MM HH:MM` - Custom prompt, reminder, cutoff times

        **Management Commands:**
        • `/standup status` - Check configuration and next scheduled times
        • `/standup pause` - Temporarily pause standups
        • `/standup resume` - Resume paused standups
        • `/standup timezone <tz>` - Set your timezone (e.g., America/New_York)

        **Configuration:**
        • `/standup config prompt_time HH:MM` - When to send prompts
        • `/standup config reminder_time HH:MM` - When to send reminders
        • `/standup config cutoff_time HH:MM` - When to post summary
        • `/standup config times HH:MM HH:MM HH:MM` - Set all times at once
        • `/standup config days weekdays` - Set which days to run standups
        • `/standup config holidays Nigeria/US` - Set holiday country
        • `/standup config skip_holidays true/false` - Enable/disable holiday skipping

        **Utilities:**
        • `/standup history [days]` - View recent standup history
        • `/standup search <term>` - Search past responses
        • `/standup debug` - Show scheduling and configuration details
        • `/standup test-prompt` - Send test prompt immediately

        **Example:** `/standup setup 09:30 11:45 13:00`
        """

    def initialize(self, bot_handler: AbstractBotHandler) -> None:
        """Initialize the bot with database and scheduler."""
        try:
            logging.info("🚀 Initializing Standup Bot...")
            self.bot_handler = bot_handler

            # Load configuration
            self.config_info = bot_handler.get_config_info('standup', True) or {}
            bot_config = config.config.get_bot_config()
            for key, value in bot_config.items():
                if key not in self.config_info or not self.config_info[key]:
                    self.config_info[key] = value

            logging.info(f"✅ Configuration loaded: {len(self.config_info)} settings")

            # Set up AI summary if available
            groq_api_key = self.config_info.get('groq_api_key')
            if groq_api_key:
                os.environ['GROQ_API_KEY'] = groq_api_key
                logging.info("🤖 AI summary generation enabled")
            else:
                logging.warning("⚠️ Groq API key not found - using manual summaries")

            # Initialize database
            self._init_database()

            # Initialize scheduler
            self._init_scheduler()

            logging.info("🎉 Standup Bot initialized successfully!")

        except Exception as e:
            logging.error(f"❌ Bot initialization failed: {e}", exc_info=True)
            raise

    def _init_database(self) -> None:
        """Initialize database connection."""
        try:
            database.init_db()
            logging.info("📊 Database initialized successfully")

            # Run cleanup on startup
            database.cleanup_old_data(days_to_keep=90)

        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
            raise

    def _init_scheduler(self) -> None:
        """Initialize the job scheduler."""
        try:
            # Configure executors and job stores
            executors = {
                'default': ThreadPoolExecutor(max_workers=5)
            }

            job_defaults = {
                'coalesce': True,  # Combine multiple pending executions
                'max_instances': 1,  # Prevent overlapping runs
                'misfire_grace_time': 300  # 5 minutes grace period
            }

            self.scheduler = BackgroundScheduler(
                executors=executors,
                job_defaults=job_defaults,
                timezone=pytz.UTC
            )

            self.scheduler.start()
            logging.info("⏰ Scheduler started successfully")

            # Schedule all existing standups
            self._schedule_all_active_standups()

            # Schedule daily maintenance
            self.scheduler.add_job(
                self._daily_maintenance,
                CronTrigger(hour=2, minute=0, timezone=pytz.UTC),
                id='daily_maintenance',
                replace_existing=True
            )

        except Exception as e:
            logging.error(f"❌ Scheduler initialization failed: {e}")
            raise

    def handle_message(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
        """Route incoming messages to appropriate handlers."""
        try:
            sender_email = message.get('sender_email', 'unknown')
            content = message.get('content', '').strip()
            message_type = message.get('type', 'unknown')
            stream_name = message.get('display_recipient', 'unknown')

            logging.info(f"📨 RAW MESSAGE: {json.dumps(message, indent=2)}")
            logging.info(f"📨 Message from {sender_email}: '{content}' (type: {message_type}, stream: {stream_name})")

            # DEBUG: Respond to ANY message mentioning the bot
            if '@' in content and ('standup' in content.lower() or 'bot' in content.lower()):
                logging.info("🔧 DEBUG: Bot mentioned, sending test response")
                try:
                    bot_handler.send_reply(message, "🤖 DEBUG: I can see you mentioned me! Bot is working.")
                    logging.info("✅ DEBUG: Test response sent successfully")
                except Exception as e:
                    logging.error(f"❌ DEBUG: Failed to send test response: {e}")

            # Handle standup commands
            if content.startswith('/standup'):
                logging.info(f"🎯 Processing standup command: {content}")
                self._handle_standup_command(message, bot_handler)
                return

            # Handle help requests
            if content.lower() in ['help', 'usage']:
                bot_handler.send_reply(message, self.usage())
                return

            # Check if this is a standup response
            if self._is_standup_response(message):
                logging.info("📝 Processing standup response")
                self._handle_standup_response(message, bot_handler)
                return

            # Default response for any message
            if message_type == 'stream' and '@' in content:
                bot_handler.send_reply(message,
                    "Hi! I'm the Standup Bot. Use `/standup help` to see available commands.")

        except Exception as e:
            logging.error(f"❌ Error handling message: {e}", exc_info=True)
            try:
                bot_handler.send_reply(message,
                    "Sorry, I encountered an error processing your message. Please try again.")
            except:
                pass

    def _handle_standup_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
        """Handle standup commands."""
        content = message['content'].strip()
        parts = content.split()

        logging.info(f"🎯 Processing standup command: {content} (parts: {parts})")

        if len(parts) < 2:
            logging.info("📤 Sending usage reply - no subcommand provided")
            bot_handler.send_reply(message, self.usage())
            return

        subcommand = parts[1].lower()
        args = parts[2:] if len(parts) > 2 else []

        logging.info(f"🔧 Subcommand: '{subcommand}', args: {args}")

        # Command routing
        handlers = {
            'setup': self._handle_setup_command,
            'status': self._handle_status_command,
            'pause': self._handle_pause_command,
            'resume': self._handle_resume_command,
            'timezone': self._handle_timezone_command,
            'config': self._handle_config_command,
            'history': self._handle_history_command,
            'search': self._handle_search_command,
            'debug': self._handle_debug_command,
            'test-prompt': self._handle_test_prompt_command,
            'help': lambda m, b, a: bot_handler.send_reply(message, self.usage())
        }

        handler = handlers.get(subcommand)
        if handler:
            try:
                logging.info(f"🚀 Executing handler for '{subcommand}'")
                handler(message, bot_handler, args)
                logging.info(f"✅ Handler for '{subcommand}' completed successfully")
            except Exception as e:
                logging.error(f"❌ Error in {subcommand} command: {e}", exc_info=True)
                bot_handler.send_reply(message, f"Error executing {subcommand} command. Please try again.")
        else:
            logging.warning(f"⚠️ Unknown subcommand: {subcommand}")
            bot_handler.send_reply(message, f"Unknown command: {subcommand}\n\n{self.usage()}")

    def _handle_setup_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Set up standup for a channel."""
        logging.info(f"🎬 Starting setup command with args: {args}")

        if message['type'] != 'stream':
            logging.warning("❌ Setup command not in a stream")
            bot_handler.send_reply(message, "❌ This command must be used in a channel (stream).")
            return

        # Default times
        prompt_time = "09:30"
        reminder_time = "11:45"
        cutoff_time = "12:45"

        logging.info(f"📅 Default times: prompt={prompt_time}, reminder={reminder_time}, cutoff={cutoff_time}")

        # Parse and validate arguments
        if args:
            logging.info(f"🔍 Validating {len(args)} time arguments")
            # Validate all provided arguments first
            for i, time_arg in enumerate(args[:3]):
                logging.info(f"⏰ Checking time argument {i}: '{time_arg}'")
                if not self._is_valid_time(time_arg):
                    logging.error(f"❌ Invalid time format: {time_arg}")
                    bot_handler.send_reply(message, f"❌ Invalid time format: {time_arg}. Use HH:MM (24-hour format).")
                    return

            # Now assign the validated times
            if len(args) >= 1:
                prompt_time = args[0]
                logging.info(f"🎯 Set prompt_time to {prompt_time}")
            if len(args) >= 2:
                reminder_time = args[1]
                logging.info(f"🔔 Set reminder_time to {reminder_time}")
            if len(args) >= 3:
                cutoff_time = args[2]
                logging.info(f"✂️ Set cutoff_time to {cutoff_time}")

        # Validate time sequence
        logging.info(f"⚖️ Validating time sequence: {prompt_time} < {reminder_time} < {cutoff_time}")
        if not self._validate_time_sequence(prompt_time, reminder_time, cutoff_time):
            logging.error(f"❌ Invalid time sequence")
            bot_handler.send_reply(message,
                f"❌ Times must be in order: prompt < reminder < cutoff\n"
                f"You provided: {prompt_time} < {reminder_time} < {cutoff_time}")
            return

        stream_id = str(message['stream_id'])
        stream_name = message['display_recipient']

        logging.info(f"📊 Processing status command for stream {stream_id} ({stream_name})")

        try:
            # Get channel subscribers
            logging.info(f"👥 Getting channel subscribers for {stream_name}")
            client = bot_handler._client
            subscribers_response = client.get_subscribers(stream=stream_name)

            logging.info(f"📊 Subscribers response result: {subscribers_response.get('result', 'unknown')}")

            if subscribers_response['result'] != 'success':
                logging.error(f"❌ Failed to get subscribers: {subscribers_response}")
                bot_handler.send_reply(message, "❌ Failed to get channel members.")
                return

            all_subscribers = subscribers_response.get('subscribers', [])
            logging.info(f"👥 Found {len(all_subscribers)} total subscribers")

            if not all_subscribers:
                logging.warning("⚠️ No subscribers found")
                bot_handler.send_reply(message, "❌ No subscribers found for this channel.")
                return

            # Get user details to filter out bots
            logging.info("👤 Getting user details to filter bots")
            users_response = client.get_users()
            if users_response['result'] != 'success':
                logging.error(f"❌ Failed to get user details: {users_response}")
                bot_handler.send_reply(message, "❌ Failed to get user details.")
                return

            users_map = {u['user_id']: u for u in users_response.get('members', [])}
            logging.info(f"👤 Got details for {len(users_map)} users")

            # Filter out bots from subscribers
            subscribers = []
            for user_id in all_subscribers:
                user = users_map.get(user_id)
                if user and not user.get('is_bot', False):
                    subscribers.append(user_id)

            logging.info(f"🤖 Filtered to {len(subscribers)} non-bot subscribers")

            if not subscribers:
                logging.warning("⚠️ No human subscribers found")
                bot_handler.send_reply(message, "❌ No human subscribers found for this channel.")
                return

            # Create channel configuration
            config_data = {
                'prompt_time': prompt_time,
                'cutoff_time': cutoff_time,
                'reminder_time': reminder_time,
                'timezone': 'Africa/Lagos',
                'days': 'mon,tue,wed,thu,fri',  # Default to weekdays
                'holiday_country': 'Nigeria',  # Default to Nigeria
                'skip_holidays': True,  # Skip holidays by default
                'is_active': True
            }

            logging.info(f"📝 Creating channel configuration: {config_data}")

            # Store in database
            logging.info("💾 Storing channel in database")
            database.get_or_create_channel(stream_id, stream_name, config_data)
            database.add_channel_participants(stream_id, [str(uid) for uid in subscribers])

            # Schedule the standup
            logging.info("⏰ Scheduling standup jobs")
            self._schedule_standup_for_channel(stream_id, config_data)

            # Success message - use the users_map we already have
            participant_list = "\n".join([
                f"• {users_map.get(uid, {}).get('full_name', f'User {uid}')}"
                for uid in subscribers[:10]  # Show first 10
            ])

            if len(subscribers) > 10:
                participant_list += f"\n• ... and {len(subscribers) - 10} more"

            logging.info("📤 Sending success message")
            # Success message
            bot_handler.send_reply(message, f"""
🎉 **Standup activated for {stream_name}!**

**⏰ Schedule:**
• **Days:** Weekdays (Mon-Fri)
• **Prompt:** {prompt_time} UTC (questions sent to team)
• **Reminder:** {reminder_time} UTC (for non-responders)
• **Summary:** {cutoff_time} UTC (posted to channel)

**👥 Participants ({len(subscribers)}):**
{participant_list}

**🚀 What happens next:**
• Daily prompts will be sent automatically on weekdays
• Team members respond via private message
• AI-powered summary posted to this channel

**💡 Customize:**
• `/standup timezone <your_timezone>` - Set personal timezone
• `/standup config times HH:MM HH:MM HH:MM` - Adjust schedule
• `/standup config days all` - Run every day including weekends
• `/standup config holidays US` - Change holiday country
• `/standup status` - Check configuration anytime

**🎉 Holiday Support:** Automatically skips Nigerian holidays by default!

Ready to go! 🎯
""")

            logging.info("✅ Setup command completed successfully")

        except Exception as e:
            logging.error(f"❌ Setup error for stream {stream_id}: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Failed to set up standup. Please try again.")

    def _handle_status_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Show standup status for a channel."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        stream_id = str(message['stream_id'])
        stream_name = message['display_recipient']

        logging.info(f"📊 Processing status command for stream {stream_id} ({stream_name})")

        try:
            # Get channel config
            channel = database.get_channel(stream_id)
            if not channel:
                bot_handler.send_reply(message, f"❌ Standup not configured for **{stream_name}**.\nUse `/standup setup` to get started!")
                return

            # Get participants
            participants = database.get_channel_participants(stream_id)

            # Calculate next run times
            timezone = channel.get('timezone', 'Africa/Lagos')
            next_times = self._calculate_next_run_times(channel, timezone)
            
            # Format days for display
            days_config = channel.get('days', 'mon,tue,wed,thu,fri')
            parsed_days = self._parse_days_config(days_config)
            days_display = self._format_days_display(parsed_days)
            
            # Holiday configuration
            holiday_country = channel.get('holiday_country', 'Nigeria')
            skip_holidays = channel.get('skip_holidays', True)
            holiday_status = "✅ Enabled" if skip_holidays else "❌ Disabled"

            # Build status message
            is_active = channel.get('is_active', False)
            status_icon = "✅" if is_active else "⏸️"

            status_msg = f"""
🎯 **Standup Status for {stream_name}**

**📊 Configuration:**
• Status: {status_icon} {'Active' if is_active else 'Paused'}
• Timezone: {timezone}
• Days: {days_display}
• Holiday Country: {holiday_country}
• Skip Holidays: {holiday_status}
• Participants: {len(participants)} members

**⏰ Schedule (UTC):**
• Prompt: {channel.get('prompt_time', 'N/A')}
• Reminder: {channel.get('reminder_time', 'N/A')}
• Summary: {channel.get('cutoff_time', 'N/A')}

**🕐 Next Scheduled:**
{next_times}

**🔧 Management:**
• `/standup pause` - Pause standups
• `/standup config times HH:MM HH:MM HH:MM` - Change schedule
• `/standup config days weekdays` - Change days
• `/standup config holidays US` - Change holiday country
• `/standup debug` - Technical details
"""

            bot_handler.send_reply(message, status_msg)

        except Exception as e:
            logging.error(f"❌ Status error for stream {stream_id}: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error retrieving status.")

    def _handle_debug_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Show debugging information."""
        try:
            import datetime
            now = datetime.datetime.now(pytz.UTC)

            # Get scheduler info
            jobs = self.scheduler.get_jobs() if hasattr(self, 'scheduler') else []

            # Get database info
            active_channels = database.get_all_active_channels()

            debug_msg = f"""
🐛 **Debug Information**

**⏰ Scheduler Status:**
• Running: {'✅ Yes' if hasattr(self, 'scheduler') and self.scheduler.running else '❌ No'}
• Scheduled Jobs: {len(jobs)}
• Current Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}

**📊 Database:**
• Active Channels: {len(active_channels)}
• Database Path: {database.get_db_path()}

**🔧 Jobs:**
"""

            for job in jobs[:10]:  # Show first 10 jobs
                next_run = getattr(job, 'next_run_time', None)
                if next_run:
                    time_until = next_run - now.replace(tzinfo=None)
                    hours_until = time_until.total_seconds() / 3600
                    debug_msg += f"• `{job.id}`: {next_run.strftime('%H:%M UTC')} ({hours_until:.1f}h)\n"
                else:
                    debug_msg += f"• `{job.id}`: Next run unknown\n"

            if len(jobs) > 10:
                debug_msg += f"• ... and {len(jobs) - 10} more jobs\n"

            debug_msg += f"""
**📈 Channels:**
"""

            for channel in active_channels[:5]:  # Show first 5 channels
                stream_name = channel.get('stream_name', 'Unknown')
                prompt_time = channel.get('prompt_time', 'N/A')
                holiday_country = channel.get('holiday_country', 'Nigeria')
                skip_holidays = channel.get('skip_holidays', True)
                
                # Check if today is a holiday
                import datetime
                today = datetime.date.today()
                is_holiday_today = self._is_holiday(today, holiday_country) if skip_holidays else False
                holiday_indicator = " 🎉" if is_holiday_today else ""
                
                debug_msg += f"• **{stream_name}**: Prompt at {prompt_time} UTC, Holidays: {holiday_country}{holiday_indicator}\n"

            if len(active_channels) > 5:
                debug_msg += f"• ... and {len(active_channels) - 5} more channels\n"

            bot_handler.send_reply(message, debug_msg)

        except Exception as e:
            logging.error(f"❌ Debug command error: {e}", exc_info=True)
            bot_handler.send_reply(message, f"❌ Debug error: {str(e)}")

    def _handle_test_prompt_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Send a test standup prompt."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        stream_id = str(message['stream_id'])

        try:
            # Check if standup is configured
            channel = database.get_channel(stream_id)
            if not channel:
                bot_handler.send_reply(message, "❌ Standup not configured. Use `/standup setup` first.")
                return

            bot_handler.send_reply(message, "🧪 Sending test standup prompts...")

            # Send the prompts
            self._send_standup_prompts(stream_id)

            bot_handler.send_reply(message, "✅ Test prompts sent! Check your private messages.")

        except Exception as e:
            logging.error(f"❌ Test prompt error: {e}", exc_info=True)
            bot_handler.send_reply(message, f"❌ Error sending test prompts: {str(e)}")

    def _handle_pause_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Pause standup for a channel."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        stream_id = str(message['stream_id'])
        stream_name = message['display_recipient']

        logging.info(f"📊 Processing status command for stream {stream_id} ({stream_name})")

        try:
            # Check if standup exists
            channel = database.get_channel(stream_id)
            if not channel:
                bot_handler.send_reply(message, f"❌ Standup not configured for **{stream_name}**.")
                return

            if not channel.get('is_active', True):
                bot_handler.send_reply(message, f"⏸️ Standup is already paused for **{stream_name}**.")
                return

            # Pause the standup
            database.update_channel(stream_id, {'is_active': False})
            self._unschedule_standup_for_channel(stream_id)

            bot_handler.send_reply(message, f"⏸️ **Standup paused for {stream_name}**\n\nUse `/standup resume` to reactivate.")

        except Exception as e:
            logging.error(f"❌ Pause error: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error pausing standup.")

    def _handle_resume_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Resume standup for a channel."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        stream_id = str(message['stream_id'])
        stream_name = message['display_recipient']

        logging.info(f"📊 Processing status command for stream {stream_id} ({stream_name})")

        try:
            # Check if standup exists
            channel = database.get_channel(stream_id)
            if not channel:
                bot_handler.send_reply(message, f"❌ Standup not configured for **{stream_name}**.")
                return

            if channel.get('is_active', False):
                bot_handler.send_reply(message, f"✅ Standup is already active for **{stream_name}**.")
                return

            # Resume the standup
            database.update_channel(stream_id, {'is_active': True})
            self._schedule_standup_for_channel(stream_id, channel)

            bot_handler.send_reply(message, f"✅ **Standup resumed for {stream_name}**\n\nDaily standups will continue as scheduled.")

        except Exception as e:
            logging.error(f"❌ Resume error: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error resuming standup.")

    def _handle_timezone_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Set user's timezone."""
        if not args:
            bot_handler.send_reply(message, "❌ Please specify a timezone (e.g., `America/New_York`).")
            return

        timezone_str = args[0]

        # Validate timezone
        try:
            pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            bot_handler.send_reply(message,
                f"❌ Invalid timezone: `{timezone_str}`\n\n"
                "Common timezones:\n"
                "• `America/New_York`\n"
                "• `Europe/London`\n"
                "• `Asia/Tokyo`\n"
                "• `Africa/Lagos`")
            return

        try:
            user_id = str(message['sender_id'])
            user_email = message['sender_email']

            database.get_or_create_user(user_id, user_email, timezone_str)

            bot_handler.send_reply(message, f"✅ Your timezone has been set to **{timezone_str}**.")

        except Exception as e:
            logging.error(f"❌ Timezone error: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error setting timezone.")

    def _handle_config_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Handle configuration commands."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        if not args:
            bot_handler.send_reply(message, """
**Configuration Options:**
• `/standup config prompt_time HH:MM` - When to send questions
• `/standup config reminder_time HH:MM` - When to send reminders
• `/standup config cutoff_time HH:MM` - When to post summary
• `/standup config times HH:MM HH:MM HH:MM` - Set all times at once
• `/standup config days mon,tue,wed,thu,fri` - Set which days to run
• `/standup config holidays Nigeria` - Set holiday country (Nigeria, US)
• `/standup config skip_holidays true/false` - Enable/disable holiday skipping

**Examples:**
• `/standup config times 09:30 11:45 13:00`
• `/standup config days weekdays` - Monday to Friday only
• `/standup config holidays US` - Use US holidays
• `/standup config skip_holidays false` - Run on holidays too
""")
            return

        stream_id = str(message['stream_id'])
        option = args[0].lower()

        try:
            channel = database.get_channel(stream_id)
            if not channel:
                bot_handler.send_reply(message, "❌ Standup not configured for this channel.")
                return

            if option == 'times' and len(args) == 4:
                # Set all times at once
                prompt_time, reminder_time, cutoff_time = args[1], args[2], args[3]

                # Validate times
                for time_str in [prompt_time, reminder_time, cutoff_time]:
                    if not self._is_valid_time(time_str):
                        bot_handler.send_reply(message, f"❌ Invalid time format: {time_str}")
                        return

                if not self._validate_time_sequence(prompt_time, reminder_time, cutoff_time):
                    bot_handler.send_reply(message, "❌ Times must be in order: prompt < reminder < cutoff")
                    return

                # Update configuration
                config_updates = {
                    'prompt_time': prompt_time,
                    'reminder_time': reminder_time,
                    'cutoff_time': cutoff_time
                }

                database.update_channel(stream_id, config_updates)
                self._reschedule_standup_for_channel(stream_id)

                bot_handler.send_reply(message, f"""
✅ **Schedule updated!**
• Prompt: {prompt_time} UTC
• Reminder: {reminder_time} UTC
• Summary: {cutoff_time} UTC
""")

            elif option in ['prompt_time', 'reminder_time', 'cutoff_time'] and len(args) == 2:
                # Set individual time
                time_value = args[1]

                if not self._is_valid_time(time_value):
                    bot_handler.send_reply(message, f"❌ Invalid time format: {time_value}")
                    return

                database.update_channel(stream_id, {option: time_value})
                self._reschedule_standup_for_channel(stream_id)

                option_name = option.replace('_', ' ').title()
                bot_handler.send_reply(message, f"✅ {option_name} set to **{time_value} UTC**")

            elif option == 'days' and len(args) == 2:
                # Set days configuration
                days_value = args[1]

                if not self._validate_days_config(days_value):
                    bot_handler.send_reply(message, f"""❌ Invalid days format: {days_value}

**Valid formats:**
• `weekdays` - Monday to Friday
• `weekend` - Saturday and Sunday  
• `all` - Every day
• `mon,tue,wed,thu,fri` - Specific days
• `1,2,3,4,5` - Numeric format (0=Monday)""")
                    return

                # Parse and format for display
                parsed_days = self._parse_days_config(days_value)
                days_display = self._format_days_display(parsed_days)

                database.update_channel(stream_id, {'days': days_value})
                self._reschedule_standup_for_channel(stream_id)

                bot_handler.send_reply(message, f"✅ Standup days set to **{days_display}**")

            elif option == 'holidays' and len(args) == 2:
                # Set holiday country
                country_value = args[1]
                supported_countries = self._get_supported_countries()
                
                # Check if the country is supported
                country_lower = country_value.lower()
                valid_country = None
                for supported in supported_countries:
                    if country_lower == supported.lower():
                        valid_country = supported
                        break
                
                if not valid_country:
                    bot_handler.send_reply(message, f"""❌ Unsupported holiday country: {country_value}

**Supported countries:**
• Nigeria (ng)
• United States (US, USA)

**Example:** `/standup config holidays US`""")
                    return

                # Normalize the country name
                if valid_country.lower() in ['us', 'usa', 'united states']:
                    normalized_country = 'United States'
                else:
                    normalized_country = 'Nigeria'

                database.update_channel(stream_id, {'holiday_country': normalized_country})
                self._reschedule_standup_for_channel(stream_id)

                bot_handler.send_reply(message, f"✅ Holiday country set to **{normalized_country}**")

            elif option == 'skip_holidays' and len(args) == 2:
                # Set skip holidays flag
                skip_value = args[1].lower()
                
                if skip_value in ['true', 'yes', 'on', '1', 'enable']:
                    skip_holidays = True
                    skip_text = "enabled"
                elif skip_value in ['false', 'no', 'off', '0', 'disable']:
                    skip_holidays = False
                    skip_text = "disabled"
                else:
                    bot_handler.send_reply(message, f"""❌ Invalid value: {args[1]}

**Valid values:**
• `true`, `yes`, `on`, `1`, `enable` - Skip holidays
• `false`, `no`, `off`, `0`, `disable` - Run on holidays

**Example:** `/standup config skip_holidays true`""")
                    return

                database.update_channel(stream_id, {'skip_holidays': skip_holidays})
                self._reschedule_standup_for_channel(stream_id)

                bot_handler.send_reply(message, f"✅ Holiday skipping **{skip_text}**")

            else:
                bot_handler.send_reply(message, "❌ Invalid config command. Use `/standup config` for help.")

        except Exception as e:
            logging.error(f"❌ Config error: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error updating configuration.")

    def _handle_history_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Show standup history."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        stream_id = str(message['stream_id'])
        days = 7  # default

        if args and args[0].isdigit():
            days = min(int(args[0]), 30)

        try:
            history = database.get_standup_history_for_stream(stream_id, days)

            if not history:
                bot_handler.send_reply(message, "📭 No standup history found.")
                return

            history_msg = f"📊 **Standup History** (Last {len(history)} days)\n\n"

            for entry in history:
                date = entry['standup_date']
                count = entry['response_count']
                completed = entry.get('completed_count', count)
                history_msg += f"• **{date}**: {completed}/{count} completed\n"

            bot_handler.send_reply(message, history_msg)

        except Exception as e:
            logging.error(f"❌ History error: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error retrieving history.")

    def _handle_search_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler, args: List[str]) -> None:
        """Search standup responses."""
        if message['type'] != 'stream':
            bot_handler.send_reply(message, "❌ This command must be used in a channel.")
            return

        if not args:
            bot_handler.send_reply(message, "❌ Please provide a search term. Example: `/standup search kubernetes`")
            return

        stream_id = str(message['stream_id'])
        search_term = ' '.join(args)

        try:
            results = database.search_standup_responses(stream_id, search_term, 10)

            if not results:
                bot_handler.send_reply(message, f"🔍 No results found for **{search_term}**")
                return

            search_msg = f"🔍 **Search Results for '{search_term}'**\n\n"

            for result in results:
                date = result['standup_date']
                email = result.get('email', 'Unknown')
                responses = result.get('responses', [])

                # Find matching responses
                matching = [r for r in responses if search_term.lower() in r.lower()]

                if matching:
                    search_msg += f"**{date}** - {email}:\n"
                    for resp in matching[:1]:  # Show first match
                        truncated = resp[:100] + "..." if len(resp) > 100 else resp
                        search_msg += f"  └ {truncated}\n"
                    search_msg += "\n"

            bot_handler.send_reply(message, search_msg)

        except Exception as e:
            logging.error(f"❌ Search error: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error performing search.")

    def _is_standup_response(self, message: Dict[str, Any]) -> bool:
        """Check if message is a standup response."""
        # Must be a private message
        if message['type'] != 'private':
            return False

        user_id = str(message['sender_id'])
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        try:
            # Check if user has any active prompts today
            prompts = database.get_all_standup_prompts_for_date(today)

            for prompt in prompts:
                pending = prompt.get('pending_responses', [])
                if user_id in pending:
                    return True

            return False

        except Exception as e:
            logging.error(f"❌ Error checking standup response: {e}")
            return False

    def _handle_standup_response(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
        """Handle a standup response from a user."""
        user_id = str(message['sender_id'])
        user_email = message['sender_email']
        content = message['content'].strip()
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        logging.info(f"📝 Processing standup response from {user_email}")

        try:
            # Find which stream this response is for
            prompts = database.get_all_standup_prompts_for_date(today)
            target_stream_id = None

            for prompt in prompts:
                if user_id in prompt.get('pending_responses', []):
                    target_stream_id = prompt['zulip_stream_id']
                    break

            if not target_stream_id:
                bot_handler.send_reply(message, "❌ No active standup found. Please wait for the next scheduled standup.")
                return

            # Store the response
            response_data = database.create_or_update_standup_response(
                user_id, target_stream_id, today, content
            )

            responses = response_data.get('responses', [])
            num_responses = len(responses)

            # Send follow-up questions
            if num_responses == 1:
                self._send_private_message(bot_handler, user_email,
                    "Thanks! What are you planning to work on today?")
            elif num_responses == 2:
                self._send_private_message(bot_handler, user_email,
                    "Great! Any blockers or issues you're facing?")
            elif num_responses >= 3:
                self._send_private_message(bot_handler, user_email,
                    "Perfect! Thank you for completing your standup. Your responses have been recorded. 🎉")

                # Remove user from pending responses
                try:
                    prompt_data = database.get_standup_prompt(target_stream_id, today)
                    if prompt_data:
                        pending = prompt_data.get('pending_responses', [])
                        if user_id in pending:
                            pending.remove(user_id)
                            database.update_standup_prompt(target_stream_id, today, pending)
                            logging.info(f"✅ User {user_id} removed from pending responses")
                except Exception as e:
                    logging.error(f"❌ Error updating pending responses: {e}")

        except Exception as e:
            logging.error(f"❌ Error handling standup response: {e}", exc_info=True)
            bot_handler.send_reply(message, "❌ Error processing your response. Please try again.")

    # === SCHEDULER METHODS ===

    def _schedule_all_active_standups(self) -> None:
        """Schedule all active standups from the database."""
        try:
            active_channels = database.get_all_active_channels()
            logging.info(f"⏰ Scheduling {len(active_channels)} active standups")

            for channel in active_channels:
                stream_id = channel['zulip_stream_id']
                self._schedule_standup_for_channel(stream_id, channel)

            logging.info(f"✅ Successfully scheduled {len(active_channels)} standups")

        except Exception as e:
            logging.error(f"❌ Error scheduling standups: {e}", exc_info=True)

    def _schedule_standup_for_channel(self, stream_id: str, channel_config: Dict[str, Any]) -> None:
        """Schedule standup jobs for a specific channel."""
        try:
            # Unschedule any existing jobs first
            self._unschedule_standup_for_channel(stream_id)

            if not channel_config.get('is_active', True):
                logging.info(f"⏸️ Channel {stream_id} is paused, skipping scheduling")
                return

            timezone = channel_config.get('timezone', 'Africa/Lagos')
            prompt_time = channel_config.get('prompt_time', '09:30')
            reminder_time = channel_config.get('reminder_time', '11:45')
            cutoff_time = channel_config.get('cutoff_time', '12:45')
            days_config = channel_config.get('days', 'mon,tue,wed,thu,fri')

            # Parse times
            prompt_hour, prompt_minute = map(int, prompt_time.split(':'))
            reminder_hour, reminder_minute = map(int, reminder_time.split(':'))
            cutoff_hour, cutoff_minute = map(int, cutoff_time.split(':'))

            # Parse days
            allowed_days = self._parse_days_config(days_config)

            # Get timezone object
            tz = pytz.timezone(timezone)

            # Schedule prompt job
            self.scheduler.add_job(
                self._send_standup_prompts,
                CronTrigger(hour=prompt_hour, minute=prompt_minute, day_of_week=','.join(map(str, allowed_days)), timezone=tz),
                id=f'prompt_{stream_id}',
                args=[stream_id],
                replace_existing=True
            )

            # Schedule reminder job
            self.scheduler.add_job(
                self._send_standup_reminders,
                CronTrigger(hour=reminder_hour, minute=reminder_minute, day_of_week=','.join(map(str, allowed_days)), timezone=tz),
                id=f'reminder_{stream_id}',
                args=[stream_id],
                replace_existing=True
            )

            # Schedule summary job
            self.scheduler.add_job(
                self._generate_and_post_summary,
                CronTrigger(hour=cutoff_hour, minute=cutoff_minute, day_of_week=','.join(map(str, allowed_days)), timezone=tz),
                id=f'summary_{stream_id}',
                args=[stream_id],
                replace_existing=True
            )

            days_display = self._format_days_display(allowed_days)
            logging.info(f"✅ Scheduled standup for stream {stream_id}: {prompt_time}, {reminder_time}, {cutoff_time} ({timezone}) on {days_display}")

        except Exception as e:
            logging.error(f"❌ Error scheduling standup for stream {stream_id}: {e}", exc_info=True)

    def _unschedule_standup_for_channel(self, stream_id: str) -> None:
        """Remove all scheduled jobs for a channel."""
        job_ids = [f'prompt_{stream_id}', f'reminder_{stream_id}', f'summary_{stream_id}']

        for job_id in job_ids:
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass  # Job might not exist

        logging.info(f"🗑️ Unscheduled standup jobs for stream {stream_id}")

    def _reschedule_standup_for_channel(self, stream_id: str) -> None:
        """Reschedule standup for a channel after config changes."""
        try:
            channel = database.get_channel(stream_id)
            if channel:
                self._schedule_standup_for_channel(stream_id, channel)
                logging.info(f"🔄 Rescheduled standup for stream {stream_id}")
        except Exception as e:
            logging.error(f"❌ Error rescheduling standup for stream {stream_id}: {e}")

    # === STANDUP EXECUTION METHODS ===

    def _send_standup_prompts(self, stream_id: str) -> None:
        """Send standup prompts to all participants."""
        try:
            logging.info(f"📤 Sending standup prompts for stream {stream_id}")

            # Get channel configuration
            channel = database.get_channel(stream_id)
            if not channel or not channel.get('is_active', True):
                logging.info(f"⏸️ Channel {stream_id} is not active, skipping prompts")
                return

            # Check if today is a holiday and we should skip
            import datetime
            today = datetime.date.today()
            if not self._should_run_standup_on_date(today, channel):
                skip_holidays = channel.get('skip_holidays', True)
                holiday_country = channel.get('holiday_country', 'Nigeria')
                
                if skip_holidays and self._is_holiday(today, holiday_country):
                    holiday_name = self._get_holiday_name(today, holiday_country)
                    logging.info(f"🎉 Skipping standup for stream {stream_id} - Today is {holiday_name} in {holiday_country}")
                else:
                    logging.info(f"📅 Skipping standup for stream {stream_id} - Today is not a configured standup day")
                return

            # Get participants
            participants = database.get_channel_participants(stream_id)
            if not participants:
                logging.warning(f"⚠️ No participants found for stream {stream_id}")
                return

            stream_name = channel.get('stream_name', 'Unknown')
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Create prompt record
            database.create_standup_prompt(stream_id, stream_name, today, participants.copy())

            # Calculate the last standup day for dynamic prompt
            last_date, last_day_description = self._get_last_standup_day(channel)
            logging.info(f"📅 Last standup day for {stream_name}: {last_day_description} ({last_date})")

            # Get user details
            client = self.bot_handler._client
            users_response = client.get_users()

            if users_response['result'] != 'success':
                logging.error(f"❌ Failed to get user details for stream {stream_id}")
                return

            users_map = {u['user_id']: u for u in users_response.get('members', [])}

            # Send prompts to all participants
            successful_sends = 0
            for user_id in participants:
                user_id_int = int(user_id) if isinstance(user_id, str) else user_id

                if user_id_int in users_map:
                    user = users_map[user_id_int]
                    user_email = user['email']
                    user_name = user['full_name']

                    prompt_message = f"""
👋 Hi **{user_name}**! Time for daily standup in **{stream_name}**.

Please answer: **What did you work on {last_day_description}?**

(I'll ask you 2 more questions after this one)
"""

                    try:
                        self._send_private_message(self.bot_handler, user_email, prompt_message)
                        successful_sends += 1
                        logging.info(f"✅ Sent prompt to {user_email}")
                    except Exception as e:
                        logging.error(f"❌ Failed to send prompt to {user_email}: {e}")

            logging.info(f"📤 Sent {successful_sends}/{len(participants)} standup prompts for stream {stream_id}")

        except Exception as e:
            logging.error(f"❌ Error sending prompts for stream {stream_id}: {e}", exc_info=True)

    def _send_standup_reminders(self, stream_id: str) -> None:
        """Send reminders to users who haven't responded."""
        try:
            logging.info(f"🔔 Sending reminders for stream {stream_id}")

            # Check if today is a holiday and we should skip
            channel = database.get_channel(stream_id)
            if channel:
                import datetime
                today_date = datetime.date.today()
                if not self._should_run_standup_on_date(today_date, channel):
                    logging.info(f"📅 Skipping reminders for stream {stream_id} - Not a standup day")
                    return

            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Get prompt data
            prompt_data = database.get_standup_prompt(stream_id, today)
            if not prompt_data:
                logging.warning(f"⚠️ No prompt data found for stream {stream_id} on {today}")
                return

            # Get users who haven't completed their standup
            incomplete_users = database.get_incomplete_responses_for_date(stream_id, today)
            pending_responses = prompt_data.get('pending_responses', [])

            # Users who haven't responded at all
            no_response_users = [uid for uid in pending_responses if uid not in incomplete_users]

            reminder_users = incomplete_users + no_response_users

            if not reminder_users:
                logging.info(f"✅ No reminders needed for stream {stream_id}")
                return

            # Get user details
            client = self.bot_handler._client
            users_response = client.get_users()

            if users_response['result'] != 'success':
                logging.error(f"❌ Failed to get user details for reminders")
                return

            users_map = {u['user_id']: u for u in users_response.get('members', [])}
            stream_name = prompt_data.get('stream_name', 'Unknown')

            # Send reminders
            reminder_count = 0
            for user_id in reminder_users:
                user_id_int = int(user_id) if isinstance(user_id, str) else user_id

                if user_id_int in users_map:
                    user = users_map[user_id_int]
                    user_email = user['email']

                    reminder_message = f"""
🔔 **Friendly reminder!**

You haven't completed your standup for **{stream_name}** today.

Please respond to complete your standup before the summary is posted.
"""

                    try:
                        self._send_private_message(self.bot_handler, user_email, reminder_message)
                        reminder_count += 1
                        logging.info(f"🔔 Sent reminder to {user_email}")
                    except Exception as e:
                        logging.error(f"❌ Failed to send reminder to {user_email}: {e}")

            # Mark reminder as sent
            database.mark_reminder_sent(stream_id, today)

            logging.info(f"🔔 Sent {reminder_count} reminders for stream {stream_id}")

        except Exception as e:
            logging.error(f"❌ Error sending reminders for stream {stream_id}: {e}", exc_info=True)

    def _generate_and_post_summary(self, stream_id: str) -> None:
        """Generate and post standup summary to the channel."""
        try:
            logging.info(f"📊 Generating summary for stream {stream_id}")

            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Get channel info
            channel = database.get_channel(stream_id)
            if not channel:
                logging.error(f"❌ Channel {stream_id} not found for summary")
                return

            # Check if today is a holiday and we should skip
            import datetime as dt
            today_date = dt.date.today()
            if not self._should_run_standup_on_date(today_date, channel):
                logging.info(f"📅 Skipping summary for stream {stream_id} - Not a standup day")
                return

            stream_name = channel.get('stream_name', 'Unknown')

            # Calculate the last standup day for summary labels
            last_date, last_day_description = self._get_last_standup_day(channel)

            # Get all responses for today
            responses = database.get_all_standup_responses_for_stream_and_date(stream_id, today)

            # Get user details for names
            client = self.bot_handler._client
            users_response = client.get_users()
            users_map = {}

            if users_response['result'] == 'success':
                users_map = {u['user_id']: u for u in users_response.get('members', [])}

            if not responses:
                # No responses received
                summary_content = f"""
📭 **Daily Standup Summary - {today}**

No standup responses were received today for **{stream_name}**.

💡 *Tip: Team members can respond to standup prompts via private message with the bot.*
"""
            else:
                # Format responses for AI summary
                formatted_responses = []
                completed_responses = []

                for response in responses:
                    user_id = response.get('user_id') or response.get('zulip_user_id')
                    user_id_int = int(user_id) if user_id else None
                    user_name = users_map.get(user_id_int, {}).get('full_name', f"User {user_id}")
                    response_list = response.get('responses', [])

                    if len(response_list) >= 3:
                        # Complete response
                        formatted_responses.append({
                            'name': user_name,
                            'yesterday': response_list[0],
                            'today': response_list[1],
                            'blockers': response_list[2]
                        })
                        completed_responses.append(response)

                # Generate summary using AI if available
                if ai_summary.summary_generator.is_available() and formatted_responses:
                    summary_content = ai_summary.summary_generator.generate_summary(formatted_responses)
                else:
                    # Manual summary with dynamic last day description
                    summary_content = self._generate_manual_summary(formatted_responses, today, stream_name, len(responses), last_day_description)

            # Post summary to channel
            self._send_stream_message(
                self.bot_handler,
                stream_name,
                f"Daily Standup Summary - {today}",
                summary_content
            )

            # Mark summary as sent
            database.mark_summary_sent(stream_id, today)

            logging.info(f"📊 Posted summary for stream {stream_id}")

        except Exception as e:
            logging.error(f"❌ Error generating summary for stream {stream_id}: {e}", exc_info=True)

    def _generate_manual_summary(self, responses: List[Dict[str, str]], date: str, stream_name: str, total_responses: int, last_day_description: str = "yesterday") -> str:
        """Generate a manual summary when AI is not available."""
        if not responses:
            return f"""
📭 **Daily Standup Summary - {date}**

No completed standup responses for **{stream_name}** today.

*Total responses: {total_responses} (incomplete)*
"""

        summary = f"""
📊 **Daily Standup Summary - {date}**

**Team:** {stream_name}
**Participants:** {len(responses)} completed

"""

        # Group by themes if possible
        if len(responses) <= 8:  # Show individual updates for smaller teams
            summary += "## 👥 Individual Updates\n\n"

            for response in responses:
                name = response.get('name', 'Unknown')
                yesterday = response.get('yesterday', 'No response')
                today = response.get('today', 'No response')
                blockers = response.get('blockers', 'None')

                # Capitalize the first letter of the day description for display
                day_label = last_day_description.capitalize()
                
                summary += f"**{name}**\n"
                summary += f"• {day_label}: {yesterday}\n"
                summary += f"• Today: {today}\n"
                summary += f"• Blockers: {blockers}\n\n"
        else:
            summary += f"## 📈 Team Activity Summary\n\n"
            summary += f"✅ **{len(responses)} team members** completed their standup\n\n"

        # Add blockers section if any exist
        blockers_exist = any(
            response.get('blockers', 'None').lower() not in ['none', 'no', 'n/a', '', 'no blockers', 'nothing']
            for response in responses
        )

        if blockers_exist:
            summary += "## ⚠️ Blockers & Issues\n\n"
            for response in responses:
                name = response.get('name', 'Unknown')
                blockers = response.get('blockers', 'None')
                if blockers.lower() not in ['none', 'no', 'n/a', '', 'no blockers', 'nothing']:
                    summary += f"• **{name}:** {blockers}\n"
            summary += "\n"

        summary += "---\n*Generated by Standup Bot*"
        return summary

    def _daily_maintenance(self) -> None:
        """Run daily maintenance tasks."""
        try:
            logging.info("🧹 Running daily maintenance")

            # Clean up old data
            database.cleanup_old_data(days_to_keep=90)

            # Reschedule all standups to handle any config changes
            self._schedule_all_active_standups()

            logging.info("✅ Daily maintenance completed")

        except Exception as e:
            logging.error(f"❌ Daily maintenance error: {e}", exc_info=True)

    # === HOLIDAY DETECTION UTILITIES ===

    def _get_holiday_calendar(self, country: str):
        """Get holiday calendar for the specified country."""
        try:
            import holidays
            
            country_map = {
                'nigeria': holidays.Nigeria,
                'ng': holidays.Nigeria,
                'us': holidays.UnitedStates,
                'usa': holidays.UnitedStates,
                'united states': holidays.UnitedStates,
                'united_states': holidays.UnitedStates,
            }
            
            country_key = country.lower().strip()
            holiday_class = country_map.get(country_key)
            
            if holiday_class:
                return holiday_class()
            else:
                logging.warning(f"⚠️ Unsupported holiday country: {country}, falling back to Nigeria")
                return holidays.Nigeria()
                
        except ImportError:
            logging.error("❌ holidays library not installed, holiday detection disabled")
            return None
        except Exception as e:
            logging.error(f"❌ Error creating holiday calendar for {country}: {e}")
            return None

    def _is_holiday(self, date_obj, country: str) -> bool:
        """Check if a given date is a holiday in the specified country."""
        try:
            holiday_calendar = self._get_holiday_calendar(country)
            if holiday_calendar is None:
                return False
            
            return date_obj in holiday_calendar
            
        except Exception as e:
            logging.error(f"❌ Error checking holiday for {date_obj} in {country}: {e}")
            return False

    def _get_holiday_name(self, date_obj, country: str) -> str:
        """Get the name of the holiday on the given date."""
        try:
            holiday_calendar = self._get_holiday_calendar(country)
            if holiday_calendar is None:
                return "Holiday"
            
            return holiday_calendar.get(date_obj, "Holiday")
            
        except Exception as e:
            logging.error(f"❌ Error getting holiday name for {date_obj} in {country}: {e}")
            return "Holiday"

    def _get_supported_countries(self) -> List[str]:
        """Get list of supported holiday countries."""
        return [
            'Nigeria', 'ng',
            'United States', 'US', 'USA'
        ]

    # === DAY FILTERING UTILITIES ===

    def _parse_days_config(self, days_str: str) -> List[int]:
        """Parse days configuration string to list of day numbers (0=Monday)."""
        try:
            if not days_str:
                return [0, 1, 2, 3, 4]  # Default to weekdays
            
            days_str = days_str.lower().strip()
            
            # Handle shortcuts
            if days_str in ['weekdays', 'workdays']:
                return [0, 1, 2, 3, 4]  # Mon-Fri
            elif days_str in ['weekend']:
                return [5, 6]  # Sat-Sun
            elif days_str in ['all', 'everyday', 'daily']:
                return [0, 1, 2, 3, 4, 5, 6]  # All days
            
            # Parse comma-separated values
            days = []
            for day in days_str.split(','):
                day = day.strip()
                if day.isdigit():
                    # Numeric format (0-6)
                    day_num = int(day)
                    if 0 <= day_num <= 6:
                        days.append(day_num)
                else:
                    # Name format
                    day_mapping = {
                        'mon': 0, 'monday': 0,
                        'tue': 1, 'tuesday': 1,
                        'wed': 2, 'wednesday': 2,
                        'thu': 3, 'thursday': 3,
                        'fri': 4, 'friday': 4,
                        'sat': 5, 'saturday': 5,
                        'sun': 6, 'sunday': 6
                    }
                    if day in day_mapping:
                        days.append(day_mapping[day])
            
            return sorted(list(set(days))) if days else [0, 1, 2, 3, 4]
            
        except Exception as e:
            logging.error(f"❌ Error parsing days config '{days_str}': {e}")
            return [0, 1, 2, 3, 4]  # Default to weekdays on error

    def _validate_days_config(self, days_str: str) -> bool:
        """Validate days configuration string."""
        try:
            parsed_days = self._parse_days_config(days_str)
            return len(parsed_days) > 0 and all(0 <= day <= 6 for day in parsed_days)
        except:
            return False

    def _format_days_display(self, days: List[int]) -> str:
        """Format day numbers for display."""
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if len(days) == 7:
            return "Every day"
        elif days == [0, 1, 2, 3, 4]:
            return "Weekdays (Mon-Fri)"
        elif days == [5, 6]:
            return "Weekends (Sat-Sun)"
        else:
            return ", ".join(day_names[day] for day in sorted(days))

    def _should_run_standup_on_date(self, check_date, channel_config: Dict[str, Any]) -> bool:
        """Check if standup should run on a given date (considering days and holidays)."""
        try:
            import datetime
            
            # Check if it's in allowed days
            days_config = channel_config.get('days', 'mon,tue,wed,thu,fri')
            allowed_days = self._parse_days_config(days_config)
            
            if check_date.weekday() not in allowed_days:
                return False
            
            # Check holidays if enabled
            skip_holidays = channel_config.get('skip_holidays', True)
            if skip_holidays:
                holiday_country = channel_config.get('holiday_country', 'Nigeria')
                if self._is_holiday(check_date, holiday_country):
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Error checking if standup should run on {check_date}: {e}")
            return True  # Default to running if there's an error

    def _get_last_standup_day(self, channel_config: Dict[str, Any]) -> Tuple[str, str]:
        """
        Calculate the last day standups were supposed to run based on configured days and holidays.
        Returns tuple of (date_string, day_description) for use in prompts.
        """
        try:
            import datetime
            
            days_config = channel_config.get('days', 'mon,tue,wed,thu,fri')
            allowed_days = self._parse_days_config(days_config)
            skip_holidays = channel_config.get('skip_holidays', True)
            holiday_country = channel_config.get('holiday_country', 'Nigeria')
            
            # Sanity check
            if not allowed_days:
                logging.warning("⚠️ No allowed days configured, defaulting to weekdays")
                allowed_days = [0, 1, 2, 3, 4]
            
            # Start from yesterday and work backwards
            today = datetime.date.today()
            check_date = today - datetime.timedelta(days=1)
            
            # Look back up to 14 days to find the last standup day
            for _ in range(14):
                # Check if standup should have run on this day
                if self._should_run_standup_on_date(check_date, channel_config):
                    # Format the date string
                    date_str = check_date.strftime('%Y-%m-%d')
                    
                    # Calculate how many days ago it was
                    days_ago = (today - check_date).days
                    
                    if days_ago == 1:
                        day_description = "yesterday"
                    elif days_ago == 2:
                        day_description = "2 days ago"
                    elif days_ago <= 7:
                        day_name = check_date.strftime('%A')  # e.g., "Monday"
                        day_description = f"last {day_name}"
                    else:
                        day_description = check_date.strftime('%A, %B %d')  # e.g., "Monday, January 15"
                    
                    return date_str, day_description
                
                # Go back one more day
                check_date -= datetime.timedelta(days=1)
            
            # Fallback if no standup day found in last 14 days (e.g., first standup ever)
            return (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d'), "your last work session"
            
        except Exception as e:
            logging.error(f"❌ Error calculating last standup day: {e}")
            import datetime
            return (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d'), "yesterday"

    # === UTILITY METHODS ===

    def _calculate_next_run_times(self, channel: Dict[str, Any], timezone: str) -> str:
        """Calculate next run times for a channel."""
        try:
            import pytz
            from datetime import datetime, timedelta

            tz = pytz.timezone(timezone)
            now = datetime.now(tz)

            prompt_time = channel.get('prompt_time', '09:30')
            reminder_time = channel.get('reminder_time', '11:45')
            cutoff_time = channel.get('cutoff_time', '12:45')

            next_times = ""

            for label, time_str in [("Prompt", prompt_time), ("Reminder", reminder_time), ("Summary", cutoff_time)]:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    if next_time <= now:
                        next_time += timedelta(days=1)

                    # Convert to UTC for display
                    next_time_utc = next_time.astimezone(pytz.UTC)

                    time_until = next_time - now
                    hours_until = time_until.total_seconds() / 3600

                    next_times += f"• **{label}:** {next_time_utc.strftime('%H:%M UTC')} ({hours_until:.1f}h)\n"

                except Exception:
                    next_times += f"• **{label}:** Invalid time format\n"

            return next_times

        except Exception as e:
            logging.error(f"❌ Error calculating next run times: {e}")
            return "• Error calculating next run times\n"

    def _send_private_message(self, bot_handler: AbstractBotHandler, user_email: str, content: str) -> None:
        """Send a private message to a user."""
        message = {
            'type': 'private',
            'to': [user_email],
            'content': content
        }
        bot_handler.send_message(message)

    def _send_stream_message(self, bot_handler: AbstractBotHandler, stream: str, topic: str, content: str) -> None:
        """Send a message to a stream."""
        message = {
            'type': 'stream',
            'to': stream,
            'subject': topic,
            'content': content
        }
        bot_handler.send_message(message)

    def _is_valid_time(self, time_str: str) -> bool:
        """Validate time format (HH:MM)."""
        pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
        return bool(pattern.match(time_str))

    def _validate_time_sequence(self, prompt_time: str, reminder_time: str, cutoff_time: str) -> bool:
        """Validate that times are in correct sequence."""
        try:
            def time_to_minutes(time_str: str) -> int:
                hour, minute = map(int, time_str.split(':'))
                return hour * 60 + minute

            prompt_min = time_to_minutes(prompt_time)
            reminder_min = time_to_minutes(reminder_time)
            cutoff_min = time_to_minutes(cutoff_time)

            return prompt_min < reminder_min < cutoff_min

        except (ValueError, IndexError):
            return False


# Bot handler class for Zulip
handler_class = StandupHandler
