# See readme.md for instructions on running this code.

from zulip_bots.lib import AbstractBotHandler
import re
import os
import json
import time
import logging
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from threading import Thread
import pytz
import openai
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from . import database
from .config import config


class StandupHandler:
    """
    A bot that helps teams run asynchronous standups in Zulip.
    """

    def usage(self) -> str:
        return """
        Standup Bot - Helps teams run asynchronous standups in Zulip.

        Commands:
        * `/standup setup` - Activate standup for this channel
        * `/standup setup HH:MM` - Activate standup for this channel with a specific time (24h format)
        * `/standup timezone <timezone>` - Set your timezone (e.g., America/New_York)
        * `/standup pause` - Pause standup for this channel
        * `/standup resume` - Resume standup for this channel
        * `/standup status` - Check the status of standup for this channel
        * `/standup config prompt_time HH:MM` - Set the prompt time for standup
        * `/standup config cutoff_time HH:MM` - Set the cutoff time for standup responses
        * `/standup config reminder_time HH:MM` - Set the reminder time for standup
        * `/standup help` - Show this help message
        """

    def handle_message(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
        """
        Handle incoming messages and route them to the appropriate handler.
        """
        # Extract the command from the message
        content = message['content'].strip()

        # Check if this is a response to a standup prompt
        if self._is_standup_response(message, bot_handler):
            self._handle_standup_response(message, bot_handler)
            return

        if content.startswith('/standup'):
            self._handle_standup_command(message, bot_handler)
        else:
            # Default response for messages that don't match any command
            bot_handler.send_reply(message, self.usage())

        def initialize(self, bot_handler: AbstractBotHandler) -> None:
            """
            Initialize the bot with configuration and start the scheduler.
            """
            self.bot_handler = bot_handler

            # Get configuration from bot_handler and merge with environment config
            self.config_info = bot_handler.get_config_info('standup', {})

            # Merge with environment config
            bot_config = config.get_bot_config()
            for key, value in bot_config.items():
                if key not in self.config_info or not self.config_info[key]:
                    self.config_info[key] = value

            # Set up OpenAI API key
            openai_api_key = self.config_info.get('openai_api_key')
            if openai_api_key:
                openai.api_key = openai_api_key
            else:
                logging.warning("OpenAI API key not found. AI summary generation will not work.")

            # Initialize database
            database_url = config.get_database_url()
            if database_url:
                database.init_db(database_url)
                self.use_database = True
                logging.info("Using PostgreSQL database for storage")
            else:
                self.use_database = False
                logging.info("Using in-memory storage (no database configured)")

            # Set up scheduler
            self.scheduler = BackgroundScheduler()
            self.scheduler.add_jobstore(MemoryJobStore(), 'default')
            self.scheduler.start()

            # Schedule existing standups
            self._schedule_all_standups()

            # Schedule a job to check for new standups every hour
            self.scheduler.add_job(
                self._schedule_all_standups,
                IntervalTrigger(hours=1),
                id='check_standups',
                replace_existing=True
            )

            logging.info("Standup bot initialized")

        def _is_standup_response(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> bool:
            """
            Check if a message is a response to a standup prompt.
            """
            # Only consider private messages
            if message['type'] != 'private':
                return False

            # Check if the user has an active standup prompt
            user_id = message['sender_id']
            user_email = message['sender_email']

            # Get all active standup prompts
            active_prompts = self._get_active_standup_prompts(bot_handler)

            # Check if this user has an active prompt
            for prompt in active_prompts:
                if user_id in prompt.get('pending_responses', []):
                    return True

            return False

        def _handle_standup_response(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
            """
            Handle a response to a standup prompt.
            """
            user_id = message['sender_id']
            user_email = message['sender_email']
            content = message['content'].strip()

            # Get all active standup prompts
            active_prompts = self._get_active_standup_prompts(bot_handler)

            # Find the prompt this user is responding to
            for prompt in active_prompts:
                if user_id in prompt.get('pending_responses', []):
                    # Store the response
                    stream_id = prompt['stream_id']
                    standup_date = prompt['date']

                    if self.use_database:
                        try:
                            # Use database to store response
                            response = database.create_or_update_standup_response(
                                user_id,
                                stream_id,
                                standup_date,
                                content
                            )

                            # Get the number of responses
                            num_responses = len(response.get('responses', []))

                            # Send follow-up question based on response count
                            if num_responses == 1:
                                self._send_private_message(
                                    bot_handler,
                                    user_email,
                                    "What are you planning to work on today?"
                                )
                            elif num_responses == 2:
                                self._send_private_message(
                                    bot_handler,
                                    user_email,
                                    "Any blockers or issues?"
                                )
                            elif num_responses == 3:
                                # Thank the user for completing the standup
                                self._send_private_message(
                                    bot_handler,
                                    user_email,
                                    "Thanks for completing your standup! Your responses have been recorded."
                                )

                                # Remove user from pending responses in database
                                try:
                                    prompt_data = database.get_standup_prompt(stream_id, standup_date)
                                    if prompt_data and 'pending_responses' in prompt_data:
                                        pending_responses = prompt_data['pending_responses']
                                        if user_id in pending_responses:
                                            pending_responses.remove(user_id)
                                            database.update_standup_prompt(stream_id, standup_date, pending_responses)
                                except Exception as e:
                                    logging.error(f"Error updating prompt in database: {e}")
                        except Exception as e:
                            logging.error(f"Error storing response in database: {e}")
                            # Fall back to in-memory storage for this response
                            self._handle_response_in_memory(bot_handler, user_id, user_email, stream_id, standup_date,
                                                            content, prompt)
                    else:
                        # Use in-memory storage
                        self._handle_response_in_memory(bot_handler, user_id, user_email, stream_id, standup_date,
                                                        content, prompt)
                    return

            # If we get here, the user doesn't have an active prompt
            bot_handler.send_reply(message,
                                   "You don't have an active standup prompt. Please wait for the next scheduled standup.")

        def _handle_response_in_memory(self, bot_handler: AbstractBotHandler, user_id: str, user_email: str,
                                       stream_id: str, standup_date: str, content: str, prompt: Dict[str, Any]) -> None:
            """
            Handle a standup response using in-memory storage.
            """
            # Get existing responses for this user
            storage_key = f"standup_response_{stream_id}_{user_id}_{standup_date}"
            try:
                existing_response = bot_handler.storage.get(storage_key)
            except KeyError:
                existing_response = None

            if existing_response is None:
                # First response
                response_data = {
                    'user_id': user_id,
                    'user_email': user_email,
                    'stream_id': stream_id,
                    'date': standup_date,
                    'responses': [content],
                    'timestamp': time.time()
                }

                # Send follow-up question if this is the first response
                if len(response_data['responses']) == 1:
                    self._send_private_message(
                        bot_handler,
                        user_email,
                        "What are you planning to work on today?"
                    )

            else:
                # Additional response
                response_data = existing_response
                response_data['responses'].append(content)
                response_data['timestamp'] = time.time()

                # Send follow-up question if this is the second response
                if len(response_data['responses']) == 2:
                    self._send_private_message(
                        bot_handler,
                        user_email,
                        "Any blockers or issues?"
                    )
                elif len(response_data['responses']) == 3:
                    # Thank the user for completing the standup
                    self._send_private_message(
                        bot_handler,
                        user_email,
                        "Thanks for completing your standup! Your responses have been recorded."
                    )

                    # Remove user from pending responses
                    prompt['pending_responses'].remove(user_id)
                    storage_key_prompt = f"standup_prompt_{stream_id}_{standup_date}"
                    bot_handler.storage.put(storage_key_prompt, prompt)

            # Store the response
            bot_handler.storage.put(storage_key, response_data)

            # Register the response key
            self._add_to_registry("response", storage_key)

        def _handle_standup_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
            """
            Handle the /standup command and its subcommands.
            """
            content = message['content'].strip()
            command_parts = content.split()

            if len(command_parts) < 2:
                bot_handler.send_reply(message, self.usage())
                return

            subcommand = command_parts[1].lower()

            if subcommand == 'setup':
                self._handle_setup_command(message, bot_handler, command_parts[2:])
            elif subcommand == 'timezone':
                self._handle_timezone_command(message, bot_handler, command_parts[2:])
            elif subcommand == 'pause':
                self._handle_pause_command(message, bot_handler)
            elif subcommand == 'resume':
                self._handle_resume_command(message, bot_handler)
            elif subcommand == 'status':
                self._handle_status_command(message, bot_handler)
            elif subcommand == 'config':
                self._handle_config_command(message, bot_handler, command_parts[2:])
            elif subcommand == 'help':
                bot_handler.send_reply(message, self.usage())
            else:
                bot_handler.send_reply(message, f"Unknown subcommand: {subcommand}\n\n{self.usage()}")

        def _handle_setup_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler,
                                  args: List[str]) -> None:
            """
            Handle the /standup setup command to activate standup for a channel.
            """
            # Default prompt time is 9:30 AM
            prompt_time = "09:30"
            # Default cutoff time is 12:45 PM
            cutoff_time = "12:45"
            # Default reminder time is 1 hour before cutoff
            reminder_time = "11:45"
            # Default timezone is Africa/Lagos
            default_timezone = "Africa/Lagos"

            # If a time is provided, validate and use it
            if args and self._is_valid_time_format(args[0]):
                prompt_time = args[0]
            elif args:
                bot_handler.send_reply(message, "Invalid time format. Please use HH:MM in 24h format.")
                return

            # Get the stream (channel) information
            if message['type'] != 'stream':
                bot_handler.send_reply(message, "This command must be used in a stream (channel).")
                return

            stream_name = message['display_recipient']
            stream_id = message['stream_id']
            topic = message['subject']

            # Get the list of subscribers (members) for this stream
            client = bot_handler._client
            subscribers_response = client.get_subscribers(stream=stream_name)

            if subscribers_response['result'] != 'success':
                bot_handler.send_reply(message, "Failed to get channel members. Please try again later.")
                return

            # Extract the list of subscribers
            subscribers = subscribers_response.get('subscribers', [])

            # Get user details for all subscribers
            users_response = client.get_users()
            if users_response['result'] != 'success':
                bot_handler.send_reply(message, "Failed to get user details. Please try again later.")
                return

            # Create a map of user_id to user details
            users_map = {user['user_id']: user for user in users_response.get('members', [])}

            # Prepare the standup configuration
            config = {
                'stream_id': stream_id,
                'stream_name': stream_name,
                'prompt_time': prompt_time,
                'cutoff_time': cutoff_time,
                'reminder_time': reminder_time,
                'timezone': default_timezone,
                'is_active': True,
                'participants': subscribers,
                'created_at': time.time(),
                'updated_at': time.time()
            }

            if self.use_database:
                try:
                    # Use database to store channel configuration
                    database.get_or_create_channel(stream_id, stream_name, config)
                    # Store participants
                    database.add_channel_participants(stream_id, subscribers)
                    logging.info(f"Channel {stream_id} configuration stored in database")
                except Exception as e:
                    logging.error(f"Error storing channel configuration in database: {e}")
                    bot_handler.send_reply(message,
                                           "There was an error setting up the standup. Please try again later.")
                    return
            else:
                # Use in-memory storage
                storage_key = f"standup_config_{stream_id}"
                bot_handler.storage.put(storage_key, config)

                # Register the config key
                self._add_to_registry("config", storage_key)

            # Format the list of participants for display
            participant_names = []
            for user_id in subscribers:
                if user_id in users_map:
                    user = users_map[user_id]
                    participant_names.append(f"{user['full_name']} ({user['email']})")
                else:
                    participant_names.append(f"User {user_id}")

            # Format the participant list for display
            participant_list = "\n".join([f"- {name}" for name in participant_names])

            # Create a confirmation message
            confirmation = f"""
    Standup activated for **{stream_name}**!

    **Configuration:**
    - Prompt time: {prompt_time} (24h format)
    - Cutoff time: {cutoff_time} (24h format)
    - Reminder time: {reminder_time} (24h format)
    - Timezone: {default_timezone}
    - Participants: {len(subscribers)} channel members

    **Participants:**
    {participant_list}

    The standup bot will post a daily prompt at {prompt_time} in each participant's timezone.
    Reminders will be sent at {reminder_time} to those who haven't responded.
    A summary will be posted to the channel at {cutoff_time}.

    You can customize these settings with:
    - `/standup config prompt_time HH:MM`
    - `/standup config cutoff_time HH:MM`
    - `/standup config reminder_time HH:MM`
    - `/standup timezone <timezone>` (for individual users)
    """

            bot_handler.send_reply(message, confirmation)

            # Schedule the standup
            self._schedule_standup(stream_id, config)

        def _handle_timezone_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler,
                                     args: List[str]) -> None:
            """
            Handle the /standup timezone command to set a user's timezone.
            """
            if not args:
                bot_handler.send_reply(message, "Please specify a timezone (e.g., America/New_York).")
                return

            timezone_str = args[0]

            # Validate the timezone
            if not self._is_valid_timezone(timezone_str):
                bot_handler.send_reply(message,
                                       f"Invalid timezone: {timezone_str}. Please use a valid timezone like 'America/New_York'.")
                return

            # Store the user's timezone
            user_id = message['sender_id']
            user_email = message['sender_email']

            if self.use_database:
                try:
                    # Use database to store user timezone
                    database.get_or_create_user(user_id, user_email, timezone_str)
                    logging.info(f"User {user_id} timezone set to {timezone_str} in database")
                except Exception as e:
                    logging.error(f"Error setting user timezone in database: {e}")
                    bot_handler.send_reply(message, "There was an error setting your timezone. Please try again later.")
                    return
            else:
                # Use in-memory storage
                user_config = {
                    'user_id': user_id,
                    'email': user_email,
                    'timezone': timezone_str,
                    'updated_at': time.time()
                }

                storage_key = f"user_config_{user_id}"
                bot_handler.storage.put(storage_key, user_config)

                # Register the user config key
                self._add_to_registry("user", storage_key)

            bot_handler.send_reply(message, f"Your timezone has been set to {timezone_str}.")

        def _handle_pause_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
            """
            Handle the /standup pause command to pause standup for a channel.
            """
            # Get the stream (channel) information
            if message['type'] != 'stream':
                bot_handler.send_reply(message, "This command must be used in a stream (channel).")
                return

            stream_id = message['stream_id']
            stream_name = message['display_recipient']

            # Get the standup configuration
            if self.use_database:
                try:
                    # Use database to get channel configuration
                    channel = database.get_channel(stream_id)
                    if channel is None:
                        bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                        return

                    if not channel.get('is_active', True):
                        bot_handler.send_reply(message, f"Standup is already paused for {stream_name}.")
                        return

                    # Pause the standup
                    database.update_channel(stream_id, {'is_active': False})
                except Exception as e:
                    logging.error(f"Error pausing standup in database: {e}")
                    bot_handler.send_reply(message, "There was an error pausing the standup. Please try again later.")
                    return
            else:
                # Use in-memory storage
                storage_key = f"standup_config_{stream_id}"
                try:
                    config = bot_handler.storage.get(storage_key)
                    if config is None:
                        bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                        return
                except KeyError:
                    bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                    return

                if not config.get('is_active', True):
                    bot_handler.send_reply(message, f"Standup is already paused for {stream_name}.")
                    return

                # Pause the standup
                config['is_active'] = False
                config['updated_at'] = time.time()
                bot_handler.storage.put(storage_key, config)

                # Register the config key
                self._add_to_registry("config", storage_key)

            # Unschedule the standup jobs
            self._unschedule_standup(stream_id)

            bot_handler.send_reply(message, f"Standup has been paused for {stream_name}.")

        def _handle_resume_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
            """
            Handle the /standup resume command to resume standup for a channel.
            """
            # Get the stream (channel) information
            if message['type'] != 'stream':
                bot_handler.send_reply(message, "This command must be used in a stream (channel).")
                return

            stream_id = message['stream_id']
            stream_name = message['display_recipient']

            # Get the standup configuration
            if self.use_database:
                try:
                    # Use database to get channel configuration
                    channel = database.get_channel(stream_id)
                    if channel is None:
                        bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                        return

                    if channel.get('is_active', False):
                        bot_handler.send_reply(message, f"Standup is already active for {stream_name}.")
                        return

                    # Resume the standup
                    database.update_channel(stream_id, {'is_active': True})
                    config = channel  # Use channel data for scheduling
                except Exception as e:
                    logging.error(f"Error resuming standup in database: {e}")
                    bot_handler.send_reply(message, "There was an error resuming the standup. Please try again later.")
                    return
            else:
                # Use in-memory storage
                storage_key = f"standup_config_{stream_id}"
                try:
                    config = bot_handler.storage.get(storage_key)
                    if config is None:
                        bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                        return
                except KeyError:
                    bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                    return

                if config.get('is_active', False):
                    bot_handler.send_reply(message, f"Standup is already active for {stream_name}.")
                    return

                # Resume the standup
                config['is_active'] = True
                config['updated_at'] = time.time()
                bot_handler.storage.put(storage_key, config)

                # Register the config key
                self._add_to_registry("config", storage_key)

            # Schedule the standup
            self._schedule_standup(stream_id, config)

            bot_handler.send_reply(message, f"Standup has been resumed for {stream_name}.")

        def _handle_status_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler) -> None:
            """
            Handle the /standup status command to check the status of standup for a channel.
            """
            # Get the stream (channel) information
            if message['type'] != 'stream':
                bot_handler.send_reply(message, "This command must be used in a stream (channel).")
                return

            stream_id = message['stream_id']
            stream_name = message['display_recipient']

            # Get the standup configuration
            storage_key = f"standup_config_{stream_id}"
            try:
                config = bot_handler.storage.get(storage_key)
                if config is None:
                    bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                    return
            except KeyError:
                bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                return

            # Get the status
            is_active = config.get('is_active', False)
            prompt_time = config.get('prompt_time', '09:30')
            cutoff_time = config.get('cutoff_time', '12:45')
            reminder_time = config.get('reminder_time', '11:45')
            timezone = config.get('timezone', 'Africa/Lagos')
            participants = config.get('participants', [])

            # Get user details for all participants
            client = bot_handler._client
            users_response = client.get_users()
            if users_response['result'] != 'success':
                bot_handler.send_reply(message, "Failed to get user details. Please try again later.")
                return

            # Create a map of user_id to user details
            users_map = {user['user_id']: user for user in users_response.get('members', [])}

            # Format the list of participants for display
            participant_names = []
            for user_id in participants:
                if user_id in users_map:
                    user = users_map[user_id]
                    participant_names.append(f"{user['full_name']} ({user['email']})")
                else:
                    participant_names.append(f"User {user_id}")

            # Format the participant list for display
            participant_list = "\n".join([f"- {name}" for name in participant_names])

            # Create a status message
            status = f"""
    **Standup Status for {stream_name}**

    - Active: {'Yes' if is_active else 'No (Paused)'}
    - Prompt time: {prompt_time} (24h format)
    - Cutoff time: {cutoff_time} (24h format)
    - Reminder time: {reminder_time} (24h format)
    - Timezone: {timezone}
    - Participants: {len(participants)} channel members

    **Participants:**
    {participant_list}
    """

            bot_handler.send_reply(message, status)

        def _handle_config_command(self, message: Dict[str, Any], bot_handler: AbstractBotHandler,
                                   args: List[str]) -> None:
            """
            Handle the /standup config command to configure standup settings.
            """
            # Get the stream (channel) information
            if message['type'] != 'stream':
                bot_handler.send_reply(message, "This command must be used in a stream (channel).")
                return

            stream_id = message['stream_id']
            stream_name = message['display_recipient']

            # Get the standup configuration
            storage_key = f"standup_config_{stream_id}"
            try:
                config = bot_handler.storage.get(storage_key)
                if config is None:
                    bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                    return
            except KeyError:
                bot_handler.send_reply(message, f"Standup is not configured for {stream_name}.")
                return

            if len(args) < 2:
                bot_handler.send_reply(message, "Please specify a configuration option and value.")
                return

            option = args[0].lower()
            value = args[1]

            if option == 'prompt_time':
                if not self._is_valid_time_format(value):
                    bot_handler.send_reply(message, "Invalid time format. Please use HH:MM in 24h format.")
                    return

                config['prompt_time'] = value
                config['updated_at'] = time.time()
                bot_handler.storage.put(storage_key, config)

                # Register the config key
                self._add_to_registry("config", storage_key)

                # Reschedule the standup
                self._unschedule_standup(stream_id)
                self._schedule_standup(stream_id, config)

                bot_handler.send_reply(message, f"Prompt time has been set to {value} for {stream_name}.")

            elif option == 'cutoff_time':
                if not self._is_valid_time_format(value):
                    bot_handler.send_reply(message, "Invalid time format. Please use HH:MM in 24h format.")
                    return

                config['cutoff_time'] = value
                config['updated_at'] = time.time()
                bot_handler.storage.put(storage_key, config)

                # Register the config key
                self._add_to_registry("config", storage_key)

                # Reschedule the standup
                self._unschedule_standup(stream_id)
                self._schedule_standup(stream_id, config)

                bot_handler.send_reply(message, f"Cutoff time has been set to {value} for {stream_name}.")

            elif option == 'reminder_time':
                if not self._is_valid_time_format(value):
                    bot_handler.send_reply(message, "Invalid time format. Please use HH:MM in 24h format.")
                    return

                config['reminder_time'] = value
                config['updated_at'] = time.time()
                bot_handler.storage.put(storage_key, config)

                # Register the config key
                self._add_to_registry("config", storage_key)

                # Reschedule the standup
                self._unschedule_standup(stream_id)
                self._schedule_standup(stream_id, config)

                bot_handler.send_reply(message, f"Reminder time has been set to {value} for {stream_name}.")

            else:
                bot_handler.send_reply(message,
                                       f"Unknown configuration option: {option}. Valid options are: prompt_time, cutoff_time, reminder_time.")

        def _get_registry(self, registry_type: str) -> List[str]:
            """
            Get a list of keys from the registry.
            """
            registry_key = f"standup_registry_{registry_type}"
            try:
                registry = self.bot_handler.storage.get(registry_key)
                if registry is None:
                    return []
                return registry
            except KeyError:
                return []

        def _add_to_registry(self, registry_type: str, key: str) -> None:
            """
            Add a key to the registry.
            """
            registry_key = f"standup_registry_{registry_type}"
            try:
                registry = self.bot_handler.storage.get(registry_key)
                if registry is None:
                    registry = []
            except KeyError:
                registry = []
            if key not in registry:
                registry.append(key)
                self.bot_handler.storage.put(registry_key, registry)

        def _schedule_all_standups(self) -> None:
            """
            Schedule all active standups.
            """
            if self.use_database:
                try:
                    # Use database to get all active channels
                    active_channels = database.get_all_active_channels()
                    for channel in active_channels:
                        stream_id = channel['zulip_stream_id']
                        self._schedule_standup(stream_id, channel)
                    logging.info(f"Scheduled {len(active_channels)} standups from database")
                except Exception as e:
                    logging.error(f"Error scheduling standups from database: {e}")
            else:
                # Use in-memory storage
                config_keys = self._get_registry("config")

                for key in config_keys:
                    try:
                        config = self.bot_handler.storage.get(key)
                        if config and config.get('is_active', False):
                            stream_id = config['stream_id']
                            self._schedule_standup(stream_id, config)
                    except KeyError:
                        logging.warning(f"Config key {key} not found in storage")

        def _schedule_standup(self, stream_id: str, config: Dict[str, Any]) -> None:
            """
            Schedule a standup for a channel.
            """
            # Unschedule any existing jobs for this stream
            self._unschedule_standup(stream_id)

            # Get the configuration
            prompt_time = config.get('prompt_time', '09:30')
            cutoff_time = config.get('cutoff_time', '12:45')
            reminder_time = config.get('reminder_time', '11:45')
            timezone = config.get('timezone', 'Africa/Lagos')

            # Parse the times
            prompt_hour, prompt_minute = map(int, prompt_time.split(':'))
            cutoff_hour, cutoff_minute = map(int, cutoff_time.split(':'))
            reminder_hour, reminder_minute = map(int, reminder_time.split(':'))

            # Schedule the prompt job
            self.scheduler.add_job(
                self._send_standup_prompts,
                CronTrigger(hour=prompt_hour, minute=prompt_minute, timezone=timezone),
                id=f'prompt_{stream_id}',
                args=[stream_id],
                replace_existing=True
            )

            # Schedule the reminder job
            self.scheduler.add_job(
                self._send_standup_reminders,
                CronTrigger(hour=reminder_hour, minute=reminder_minute, timezone=timezone),
                id=f'reminder_{stream_id}',
                args=[stream_id],
                replace_existing=True
            )

            # Schedule the summary job
            self.scheduler.add_job(
                self._generate_and_post_summary,
                CronTrigger(hour=cutoff_hour, minute=cutoff_minute, timezone=timezone),
                id=f'summary_{stream_id}',
                args=[stream_id],
                replace_existing=True
            )

            logging.info(f"Scheduled standup for stream {stream_id}")

        def _unschedule_standup(self, stream_id: str) -> None:
            """
            Unschedule a standup for a channel.
            """
            # Remove all jobs for this stream
            job_ids = [f'prompt_{stream_id}', f'reminder_{stream_id}', f'summary_{stream_id}']

            for job_id in job_ids:
                try:
                    self.scheduler.remove_job(job_id)
                except:
                    pass

            logging.info(f"Unscheduled standup for stream {stream_id}")

        def _send_standup_prompts(self, stream_id: str) -> None:
            """
            Send standup prompts to all participants in a channel.
            """
            # Get the standup configuration
            storage_key = f"standup_config_{stream_id}"
            try:
                config = self.bot_handler.storage.get(storage_key)
                if config is None or not config.get('is_active', False):
                    logging.warning(f"Standup not active for stream {stream_id}")
                    return
            except KeyError:
                logging.warning(f"Standup configuration not found for stream {stream_id}")
                return

            # Get the participants
            participants = config.get('participants', [])
            stream_name = config.get('stream_name', 'Unknown')

            # Get user details for all participants
            client = self.bot_handler._client
            users_response = client.get_users()
            if users_response['result'] != 'success':
                logging.error(f"Failed to get user details for stream {stream_id}")
                return

            # Create a map of user_id to user details
            users_map = {user['user_id']: user for user in users_response.get('members', [])}

            # Get today's date
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Create a prompt record
            prompt_data = {
                'stream_id': stream_id,
                'stream_name': stream_name,
                'date': today,
                'pending_responses': participants.copy(),
                'created_at': time.time()
            }

            if self.use_database:
                try:
                    # Use database to store prompt
                    database.create_standup_prompt(stream_id, stream_name, today, participants.copy())
                    logging.info(f"Standup prompt for stream {stream_id} on {today} stored in database")
                except Exception as e:
                    logging.error(f"Error storing standup prompt in database: {e}")
                    # Fall back to in-memory storage
                    prompt_key = f"standup_prompt_{stream_id}_{today}"
                    self.bot_handler.storage.put(prompt_key, prompt_data)
                    self._add_to_registry("prompt", prompt_key)
            else:
                # Use in-memory storage
                prompt_key = f"standup_prompt_{stream_id}_{today}"
                self.bot_handler.storage.put(prompt_key, prompt_data)
                # Register the prompt key
                self._add_to_registry("prompt", prompt_key)

            # Send prompts to all participants
            for user_id in participants:
                if user_id in users_map:
                    user = users_map[user_id]
                    user_email = user['email']

                    # Send the prompt
                    prompt_message = f"""
    Hi {user['full_name']}! It's time for the daily standup in **{stream_name}**.

    Please answer these questions:
    1. What did you work on yesterday?
    """

                    self._send_private_message(
                        self.bot_handler,
                        user_email,
                        prompt_message
                    )

            logging.info(f"Sent standup prompts for stream {stream_id}")

        def _send_standup_reminders(self, stream_id: str) -> None:
            """
            Send reminders to participants who haven't responded to the standup prompt.
            """
            # Get the standup configuration
            storage_key = f"standup_config_{stream_id}"
            try:
                config = self.bot_handler.storage.get(storage_key)
                if config is None or not config.get('is_active', False):
                    logging.warning(f"Standup not active for stream {stream_id}")
                    return
            except KeyError:
                logging.warning(f"Standup configuration not found for stream {stream_id}")
                return

            # Get today's date
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Get the prompt record
            prompt_key = f"standup_prompt_{stream_id}_{today}"
            try:
                prompt_data = self.bot_handler.storage.get(prompt_key)
                if prompt_data is None:
                    logging.warning(f"No prompt record found for stream {stream_id} on {today}")
                    return
            except KeyError:
                logging.warning(f"No prompt record found for stream {stream_id} on {today}")
                return

            # Get the pending responses
            pending_responses = prompt_data.get('pending_responses', [])
            stream_name = prompt_data.get('stream_name', 'Unknown')

            if not pending_responses:
                logging.info(f"No pending responses for stream {stream_id}")
                return

            # Get user details for all participants
            client = self.bot_handler._client
            users_response = client.get_users()
            if users_response['result'] != 'success':
                logging.error(f"Failed to get user details for stream {stream_id}")
                return

            # Create a map of user_id to user details
            users_map = {user['user_id']: user for user in users_response.get('members', [])}

            # Get the cutoff time
            cutoff_time = config.get('cutoff_time', '12:45')

            # Send reminders to all pending participants
            for user_id in pending_responses:
                if user_id in users_map:
                    user = users_map[user_id]
                    user_email = user['email']

                    # Send the reminder
                    reminder_message = f"""
    Reminder: You haven't completed your standup for **{stream_name}** today.

    Please respond to the standup prompt before {cutoff_time}.
    """

                    self._send_private_message(
                        self.bot_handler,
                        user_email,
                        reminder_message
                    )

            logging.info(f"Sent standup reminders for stream {stream_id}")

        def _generate_and_post_summary(self, stream_id: str) -> None:
            """
            Generate a summary of standup responses and post it to the channel.
            """
            # Get the standup configuration
            storage_key = f"standup_config_{stream_id}"
            try:
                config = self.bot_handler.storage.get(storage_key)
                if config is None or not config.get('is_active', False):
                    logging.warning(f"Standup not active for stream {stream_id}")
                    return
            except KeyError:
                logging.warning(f"Standup configuration not found for stream {stream_id}")
                return

            # Get today's date
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Get the prompt record
            prompt_key = f"standup_prompt_{stream_id}_{today}"
            try:
                prompt_data = self.bot_handler.storage.get(prompt_key)
                if prompt_data is None:
                    logging.warning(f"No prompt record found for stream {stream_id} on {today}")
                    return
            except KeyError:
                logging.warning(f"No prompt record found for stream {stream_id} on {today}")
                return

            # Get the stream name
            stream_name = prompt_data.get('stream_name', 'Unknown')

            # Get all responses for this standup
            if self.use_database:
                try:
                    # Use database to get responses
                    responses = database.get_all_standup_responses_for_stream_and_date(stream_id, today)
                    logging.info(
                        f"Retrieved {len(responses)} responses from database for stream {stream_id} on {today}")
                except Exception as e:
                    logging.error(f"Error retrieving responses from database: {e}")
                    # Fall back to in-memory storage
                    responses = self._get_responses_from_memory(stream_id, today)
            else:
                # Use in-memory storage
                responses = self._get_responses_from_memory(stream_id, today)

            # Get user details for all participants
            client = self.bot_handler._client
            users_response = client.get_users()
            if users_response['result'] != 'success':
                logging.error(f"Failed to get user details for stream {stream_id}")
                return

            # Create a map of user_id to user details
            users_map = {user['user_id']: user for user in users_response.get('members', [])}

            # Generate the summary
            if responses:
                # Format the responses for the AI summary
                formatted_responses = []
                for response in responses:
                    user_id = response.get('user_id')
                    user_name = users_map.get(user_id, {}).get('full_name', f"User {user_id}")

                    response_text = response.get('responses', [])
                    if len(response_text) >= 3:
                        formatted_responses.append({
                            'name': user_name,
                            'yesterday': response_text[0],
                            'today': response_text[1],
                            'blockers': response_text[2]
                        })

                # Generate the AI summary
                summary = self._generate_ai_summary(formatted_responses)

                # Post the summary to the channel
                self._send_stream_message(
                    self.bot_handler,
                    stream_name,
                    "Daily Standup Summary",
                    summary
                )

                logging.info(f"Posted standup summary for stream {stream_id}")
            else:
                # No responses
                self._send_stream_message(
                    self.bot_handler,
                    stream_name,
                    "Daily Standup Summary",
                    "No standup responses were received today."
                )

                logging.info(f"No responses for stream {stream_id}")

        def _get_responses_from_memory(self, stream_id: str, date: str) -> List[Dict[str, Any]]:
            """
            Get standup responses from in-memory storage.
            """
            response_keys = self._get_registry("response")
            response_keys = [key for key in response_keys if key.startswith(f"standup_response_{stream_id}_{date}")]

            responses = []
            for key in response_keys:
                try:
                    response_data = self.bot_handler.storage.get(key)
                    if response_data:
                        responses.append(response_data)
                except KeyError:
                    logging.warning(f"Response data not found for key {key}")
                    continue

            return responses

        def _generate_ai_summary(self, responses: List[Dict[str, str]]) -> str:
            """
            Generate an AI summary of standup responses using OpenAI.
            """
            if not responses:
                return "No standup responses were received today."

            if not openai.api_key:
                # Fallback to manual summary if OpenAI API key is not available
                return self._generate_manual_summary(responses)

            try:
                # Format the responses for the prompt
                formatted_responses = json.dumps(responses, indent=2)

                # Create the prompt
                prompt = f"""
    You are an assistant that summarizes daily standup updates from a team.
    Please create a concise summary of the following standup responses, highlighting key work items and any blockers.
    Format the summary in Markdown with sections for "Team Progress", "Today's Focus", and "Blockers".
    Make sure to highlight any blockers or issues that need attention.

    Standup Responses:
    {formatted_responses}
    """

                # Call the OpenAI API
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system",
                         "content": "You are a helpful assistant that summarizes team standup updates."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )

                # Extract the summary
                summary = response.choices[0].message.content

                return summary

            except Exception as e:
                logging.error(f"Error generating AI summary: {e}")
                # Fallback to manual summary
                return self._generate_manual_summary(responses)

        def _generate_manual_summary(self, responses: List[Dict[str, str]]) -> str:
            """
            Generate a manual summary of standup responses.
            """
            if not responses:
                return "No standup responses were received today."

            # Create the summary
            summary = "# Daily Standup Summary\n\n"

            # Add the date
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            summary += f"**Date:** {today}\n\n"

            # Add the participants
            summary += f"**Participants:** {len(responses)}\n\n"

            # Add the individual updates
            summary += "## Individual Updates\n\n"

            for response in responses:
                name = response.get('name', 'Unknown')
                yesterday = response.get('yesterday', 'No response')
                today = response.get('today', 'No response')
                blockers = response.get('blockers', 'None')

                summary += f"### {name}\n\n"
                summary += f"**Yesterday:** {yesterday}\n\n"
                summary += f"**Today:** {today}\n\n"
                summary += f"**Blockers:** {blockers}\n\n"

            # Add the blockers section
            blockers_exist = any(response.get('blockers', 'None') != 'None' for response in responses)

            if blockers_exist:
                summary += "## Blockers Requiring Attention\n\n"

                for response in responses:
                    name = response.get('name', 'Unknown')
                    blockers = response.get('blockers', 'None')

                    if blockers != 'None':
                        summary += f"- **{name}:** {blockers}\n"

            return summary

        def _send_private_message(self, bot_handler: AbstractBotHandler, user_email: str, content: str) -> None:
            """
            Send a private message to a user.
            """
            message = {
                'type': 'private',
                'to': [user_email],
                'content': content
            }

            bot_handler.send_message(message)

        def _send_stream_message(self, bot_handler: AbstractBotHandler, stream: str, topic: str, content: str) -> None:
            """
            Send a message to a stream.
            """
            message = {
                'type': 'stream',
                'to': stream,
                'subject': topic,
                'content': content
            }

            bot_handler.send_message(message)

        def _is_valid_time_format(self, time_str: str) -> bool:
            """
            Validate that a string is in the format HH:MM (24h format).
            """
            time_pattern = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
            return bool(time_pattern.match(time_str))

        def _is_valid_timezone(self, timezone_str: str) -> bool:
            """
            Validate that a string is a valid timezone.
            """
            try:
                pytz.timezone(timezone_str)
                return True
            except pytz.exceptions.UnknownTimeZoneError:
                return False

        def _get_user_timezone(self, bot_handler: AbstractBotHandler, user_id: str) -> str:
            """
            Get a user's timezone.
            """
            if self.use_database:
                # Use database to get user timezone
                return database.get_user_timezone(user_id)
            else:
                # Use in-memory storage
                storage_key = f"user_config_{user_id}"
                try:
                    user_config = bot_handler.storage.get(storage_key)
                    if user_config and 'timezone' in user_config:
                        return user_config['timezone']
                except KeyError:
                    pass

            return self.config_info.get('default_timezone', 'Africa/Lagos')

        def _get_active_standup_prompts(self, bot_handler: AbstractBotHandler) -> List[Dict[str, Any]]:
            """
            Get all active standup prompts.
            """
            # Get today's date
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Get all prompt keys from registry
            prompt_keys = self._get_registry("prompt")

            # Filter for today's prompts
            prompt_keys = [key for key in prompt_keys if key.endswith(f"_{today}")]

            # Get the prompt data
            prompts = []
            for key in prompt_keys:
                try:
                    prompt_data = bot_handler.storage.get(key)
                    if prompt_data:
                        prompts.append(prompt_data)
                except KeyError:
                    logging.warning(f"Prompt data not found for key {key}")
                    continue

            return prompts


handler_class = StandupHandler
