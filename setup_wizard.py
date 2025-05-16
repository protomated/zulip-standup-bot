from typing import Dict, Any, List, Optional, Callable
import re
import logging
from zulip_bots.lib import BotHandler

from standup_manager import StandupManager
from templates import Templates


class SetupWizard:
    """
    Handles the interactive setup flow for creating a new standup meeting
    """

    def __init__(self, bot_handler: BotHandler, standup_manager: StandupManager, templates: Templates):
        self.bot_handler = bot_handler
        self.standup_manager = standup_manager
        self.templates = templates
        self.setup_states = {}  # Stores setup state for each user
        self.logger = logging.getLogger('standup_bot.setup_wizard')

    def start_setup(self, user_id: int) -> None:
        """
        Start the setup process for a user
        """
        # Initialize setup state
        self.setup_states[user_id] = {
            'step': 'name',
            'name': '',
            'stream': '',
            'days': [],
            'time': '',
            'questions': [],
            'participants': [],
            'timezone_handling': 'same',  # Default to same timezone
            'team_tag': '',
            'project_tag': '',
            'permissions': {
                'admin_users': [user_id],  # Creator is admin by default
                'can_edit': 'admin',  # Only admins can edit
                'can_view': 'participants'  # Only participants can view
            },
            'settings': {
                'reminder_time': 30,  # Minutes before standup to send reminder
                'report_format': 'detailed',  # Default report format
                'ai_summary': True  # Enable AI summary by default
            }
        }

        # Send intro message
        self._send_message(user_id, self.templates.setup_intro())

        # Send first prompt
        self._send_message(user_id, self.templates.setup_name_prompt())

    def handle_response(self, user_id: int, message_content: str) -> bool:
        """
        Handle a response from the user during setup
        Returns True if setup is complete, False otherwise
        """
        # Check if user is in setup process
        if user_id not in self.setup_states:
            return False

        # Check for cancel command
        if message_content.lower() == 'cancel':
            self._send_message(user_id, self.templates.setup_cancelled())
            del self.setup_states[user_id]
            return True

        # Get current step
        current_step = self.setup_states[user_id]['step']

        # Process response based on current step
        if current_step == 'name':
            return self._handle_name_response(user_id, message_content)
        elif current_step == 'stream':
            return self._handle_stream_response(user_id, message_content)
        elif current_step == 'days':
            return self._handle_days_response(user_id, message_content)
        elif current_step == 'time':
            return self._handle_time_response(user_id, message_content)
        elif current_step == 'questions':
            return self._handle_questions_response(user_id, message_content)
        elif current_step == 'participants':
            return self._handle_participants_response(user_id, message_content)
        elif current_step == 'team_tag':
            return self._handle_team_tag_response(user_id, message_content)
        elif current_step == 'project_tag':
            return self._handle_project_tag_response(user_id, message_content)
        elif current_step == 'confirmation':
            return self._handle_confirmation_response(user_id, message_content)

        return False

    def is_user_in_setup(self, user_id: int) -> bool:
        """Check if a user is currently in the setup process"""
        return user_id in self.setup_states

    def _handle_name_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for standup name"""
        name = message_content.strip()
        if not name:
            self._send_message(user_id, self.templates.error_message("Standup name cannot be empty. Please try again."))
            self._send_message(user_id, self.templates.setup_name_prompt())
            return False

        # Store name and move to next step
        self.setup_states[user_id]['name'] = name
        self.setup_states[user_id]['step'] = 'stream'

        # Send next prompt
        self._send_message(user_id, self.templates.setup_stream_prompt())
        return False

    def _handle_stream_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for team stream"""
        stream = message_content.strip().lstrip('#')  # Remove # if present
        if not stream:
            self._send_message(user_id, self.templates.error_message("Stream name cannot be empty. Please try again."))
            self._send_message(user_id, self.templates.setup_stream_prompt())
            return False

        # Store stream and move to next step
        self.setup_states[user_id]['stream'] = stream
        self.setup_states[user_id]['step'] = 'days'

        # Send next prompt
        self._send_message(user_id, self.templates.setup_days_prompt())
        return False

    def _handle_days_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for standup days"""
        # Default to weekdays if empty
        if not message_content.strip():
            days = [1, 2, 3, 4, 5]  # Monday to Friday
        else:
            try:
                # Parse comma-separated day numbers
                days = [int(day.strip()) for day in message_content.split(',')]
                # Validate day numbers
                if not all(1 <= day <= 7 for day in days):
                    raise ValueError("Day numbers must be between 1 and 7")
            except ValueError:
                self._send_message(user_id, self.templates.error_message(
                    "Invalid day format. Please enter numbers 1-7 separated by commas."))
                self._send_message(user_id, self.templates.setup_days_prompt())
                return False

        # Convert day numbers to day names
        day_names = {
            1: 'monday', 2: 'tuesday', 3: 'wednesday',
            4: 'thursday', 5: 'friday', 6: 'saturday', 7: 'sunday'
        }
        day_list = [day_names[day] for day in days]

        # Store days and move to next step
        self.setup_states[user_id]['days'] = day_list
        self.setup_states[user_id]['step'] = 'time'

        # Send next prompt
        self._send_message(user_id, self.templates.setup_time_prompt())
        return False

    def _handle_time_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for standup time"""
        # Default to 9:00 AM if empty
        if not message_content.strip():
            time = "09:00"
        else:
            time = message_content.strip()
            # Validate time format (HH:MM)
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time):
                self._send_message(user_id, self.templates.error_message(
                    "Invalid time format. Please use HH:MM in 24-hour format."))
                self._send_message(user_id, self.templates.setup_time_prompt())
                return False

        # Store time and move to next step
        self.setup_states[user_id]['time'] = time
        self.setup_states[user_id]['step'] = 'questions'

        # Send next prompt
        self._send_message(user_id, self.templates.setup_questions_prompt())
        return False

    def _handle_questions_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for standup questions"""
        # Use default questions if requested
        if message_content.strip().lower() == 'default':
            questions = self.templates.default_questions()
        else:
            # Parse questions (one per line)
            questions = [q.strip() for q in message_content.split('\n') if q.strip()]
            if not questions:
                questions = self.templates.default_questions()

        # Store questions and move to next step
        self.setup_states[user_id]['questions'] = questions
        self.setup_states[user_id]['step'] = 'participants'

        # Send next prompt
        self._send_message(user_id, self.templates.setup_participants_prompt())
        return False

    def _handle_participants_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for standup participants"""
        # Store participants as a string for now (will be processed when creating the standup)
        self.setup_states[user_id]['participants_raw'] = message_content.strip()

        # Move to team tag step
        self.setup_states[user_id]['step'] = 'team_tag'

        # Send team tag prompt
        self._send_message(user_id, "What team does this standup belong to? (optional, press Enter to skip)")
        return False

    def _handle_team_tag_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for team tag"""
        # Store team tag
        self.setup_states[user_id]['team_tag'] = message_content.strip()

        # Move to project tag step
        self.setup_states[user_id]['step'] = 'project_tag'

        # Send project tag prompt
        self._send_message(user_id, "What project does this standup belong to? (optional, press Enter to skip)")
        return False

    def _handle_project_tag_response(self, user_id: int, message_content: str) -> bool:
        """Handle response for project tag"""
        # Store project tag
        self.setup_states[user_id]['project_tag'] = message_content.strip()

        # Move to confirmation step
        self.setup_states[user_id]['step'] = 'confirmation'

        # Format days for display
        day_names = {
            'monday': 'Monday', 'tuesday': 'Tuesday', 'wednesday': 'Wednesday',
            'thursday': 'Thursday', 'friday': 'Friday', 'saturday': 'Saturday', 'sunday': 'Sunday'
        }
        days_formatted = ', '.join([day_names[day] for day in self.setup_states[user_id]['days']])

        # Prepare team and project tag display
        team_tag_display = f"Team: {self.setup_states[user_id]['team_tag']}" if self.setup_states[user_id]['team_tag'] else "Team: None"
        project_tag_display = f"Project: {self.setup_states[user_id]['project_tag']}" if self.setup_states[user_id]['project_tag'] else "Project: None"

        # Send confirmation message with tags
        confirmation_message = self.templates.setup_confirmation(
            name=self.setup_states[user_id]['name'],
            stream=self.setup_states[user_id]['stream'],
            days=days_formatted,
            time=self.setup_states[user_id]['time'],
            questions=self.setup_states[user_id]['questions'],
            participants=self.setup_states[user_id]['participants_raw']
        )

        # Add tags to confirmation message
        confirmation_message += f"\n\n{team_tag_display}\n{project_tag_display}"

        self._send_message(user_id, confirmation_message)
        return False

    def _handle_confirmation_response(self, user_id: int, message_content: str) -> bool:
        """Handle confirmation response"""
        response = message_content.strip().lower()

        if response == 'yes':
            # Create the standup
            try:
                # Process participants
                participants_raw = self.setup_states[user_id]['participants_raw']
                participants = self._process_participants(participants_raw, user_id)

                # Create schedule dict
                schedule = {
                    'days': self.setup_states[user_id]['days'],
                    'time': self.setup_states[user_id]['time'],
                    'timezone': 'UTC',  # Default timezone
                    'duration': 86400  # Default duration (24 hours)
                }

                # Create the standup
                standup_id = self.standup_manager.create_standup(
                    creator_id=user_id,
                    name=self.setup_states[user_id]['name'],
                    team_stream=self.setup_states[user_id]['stream'],
                    schedule=schedule,
                    questions=self.setup_states[user_id]['questions'],
                    participants=participants,
                    timezone_handling=self.setup_states[user_id]['timezone_handling'],
                    team_tag=self.setup_states[user_id]['team_tag'],
                    project_tag=self.setup_states[user_id]['project_tag'],
                    permissions=self.setup_states[user_id]['permissions']
                )

                # Send success message
                self._send_message(user_id, self.templates.setup_success(
                    standup_id=standup_id,
                    name=self.setup_states[user_id]['name']
                ))

                # Clean up setup state
                del self.setup_states[user_id]
                return True

            except Exception as e:
                self._send_message(user_id, self.templates.error_message(
                    f"Error creating standup: {str(e)}"
                ))
                # Clean up setup state
                del self.setup_states[user_id]
                return True

        elif response == 'no':
            # Start over
            self._send_message(user_id, "Let's start over.")
            self.start_setup(user_id)
            return False

        else:
            # Invalid response
            self._send_message(user_id, self.templates.error_message(
                "Please type 'yes' to create the standup or 'no' to start over."
            ))
            return False

    def _process_participants(self, participants_raw: str, creator_id: int = None) -> List[int]:
        """Process participants string into a list of user IDs"""
        # Check for 'all' keyword
        if participants_raw.lower() == 'all':
            # In a real implementation, you would get all users in the stream
            # For now, we'll just return a placeholder list with the creator included
            if creator_id is not None:
                return [creator_id, 1, 2, 3]  # Include creator and placeholder users
            else:
                return [1, 2, 3]  # Placeholder for all users

        # Parse @mentions
        # In Zulip, mentions look like "@**User Name**"
        participants = []

        # Simple regex to extract user IDs from mentions
        # In a real implementation, you would use the Zulip API to resolve user names to IDs
        mention_pattern = r'@\*\*([^*]+)\*\*'
        mentions = re.findall(mention_pattern, participants_raw)

        for mention in mentions:
            try:
                # In a real implementation, you would look up the user ID by name
                # For now, we'll use a placeholder mapping
                user_mapping = {
                    'Alice': 101,
                    'Bob': 102,
                    'Charlie': 103,
                    # Add more mappings as needed
                }

                user_id = user_mapping.get(mention, 1)  # Default to 1 if not found
                participants.append(user_id)
            except Exception as e:
                self.logger.error(f"Error processing participant {mention}: {str(e)}")

        # Always include the creator in the participants list if provided
        if creator_id is not None and creator_id not in participants:
            participants.append(creator_id)

        # If no valid participants were found, include a placeholder
        if not participants:
            if creator_id is not None:
                participants = [creator_id]  # Use the actual creator ID
            else:
                participants = [1]  # Placeholder for creator

        return participants

    def _send_message(self, user_id: int, content: str) -> None:
        """Send a message to a user"""
        self.bot_handler.send_message({
            'type': 'private',
            'to': [user_id],
            'content': content
        })
