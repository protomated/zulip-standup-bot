from typing import Dict, Any, List, Optional, Union
import re
import json
import logging
from zulip_bots.lib import BotHandler
from storage_manager import StorageManager
from standup_manager import StandupManager

class ResponseType:
    """Enum-like class for response types"""
    TEXT = "text"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"
    BOOLEAN = "boolean"
    NUMBER = "number"

class QuestionTemplate:
    """Class representing a question template with type and validation"""

    def __init__(
        self,
        question: str,
        response_type: str = ResponseType.TEXT,
        required: bool = True,
        choices: Optional[List[str]] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ):
        self.question = question
        self.response_type = response_type
        self.required = required
        self.choices = choices
        self.min_length = min_length
        self.max_length = max_length
        self.min_value = min_value
        self.max_value = max_value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "question": self.question,
            "response_type": self.response_type,
            "required": self.required,
            "choices": self.choices,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "min_value": self.min_value,
            "max_value": self.max_value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestionTemplate':
        """Create from dictionary"""
        return cls(
            question=data["question"],
            response_type=data.get("response_type", ResponseType.TEXT),
            required=data.get("required", True),
            choices=data.get("choices"),
            min_length=data.get("min_length"),
            max_length=data.get("max_length"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value")
        )

    def format_for_display(self, index: int) -> str:
        """Format the question for display to the user"""
        question_text = f"{index}. {self.question}"

        if self.response_type == ResponseType.CHOICE and self.choices:
            options = ", ".join([f"'{choice}'" for choice in self.choices])
            question_text += f" (Choose one: {options})"

        elif self.response_type == ResponseType.MULTI_CHOICE and self.choices:
            options = ", ".join([f"'{choice}'" for choice in self.choices])
            question_text += f" (Choose one or more: {options})"

        elif self.response_type == ResponseType.BOOLEAN:
            question_text += " (Yes/No)"

        elif self.response_type == ResponseType.NUMBER:
            range_text = ""
            if self.min_value is not None and self.max_value is not None:
                range_text = f" between {self.min_value} and {self.max_value}"
            elif self.min_value is not None:
                range_text = f" >= {self.min_value}"
            elif self.max_value is not None:
                range_text = f" <= {self.max_value}"

            if range_text:
                question_text += f" (Enter a number{range_text})"

        if not self.required:
            question_text += " (Optional)"

        return question_text

class ResponseValidator:
    """Class for validating responses based on question templates"""

    @staticmethod
    def validate(response: str, template: QuestionTemplate) -> tuple[bool, Optional[str]]:
        """
        Validate a response against a question template

        Args:
            response: The user's response
            template: The question template

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if required
        if not response and template.required:
            return False, "This question requires an answer."

        # If not required and empty, it's valid
        if not response and not template.required:
            return True, None

        # Validate based on type
        if template.response_type == ResponseType.TEXT:
            return ResponseValidator._validate_text(response, template)

        elif template.response_type == ResponseType.CHOICE:
            return ResponseValidator._validate_choice(response, template)

        elif template.response_type == ResponseType.MULTI_CHOICE:
            return ResponseValidator._validate_multi_choice(response, template)

        elif template.response_type == ResponseType.BOOLEAN:
            return ResponseValidator._validate_boolean(response)

        elif template.response_type == ResponseType.NUMBER:
            return ResponseValidator._validate_number(response, template)

        return True, None

    @staticmethod
    def _validate_text(response: str, template: QuestionTemplate) -> tuple[bool, Optional[str]]:
        """Validate text response"""
        if template.min_length and len(response) < template.min_length:
            return False, f"Response must be at least {template.min_length} characters."

        if template.max_length and len(response) > template.max_length:
            return False, f"Response must be at most {template.max_length} characters."

        return True, None

    @staticmethod
    def _validate_choice(response: str, template: QuestionTemplate) -> tuple[bool, Optional[str]]:
        """Validate choice response"""
        if not template.choices:
            return True, None

        if response not in template.choices:
            return False, f"Response must be one of: {', '.join(template.choices)}"

        return True, None

    @staticmethod
    def _validate_multi_choice(response: str, template: QuestionTemplate) -> tuple[bool, Optional[str]]:
        """Validate multi-choice response"""
        if not template.choices:
            return True, None

        # Split by commas and strip whitespace
        choices = [choice.strip() for choice in response.split(',')]

        for choice in choices:
            if choice not in template.choices:
                return False, f"All choices must be from: {', '.join(template.choices)}"

        return True, None

    @staticmethod
    def _validate_boolean(response: str) -> tuple[bool, Optional[str]]:
        """Validate boolean response"""
        lower_response = response.lower()
        valid_values = ['yes', 'no', 'true', 'false', 'y', 'n', '1', '0']

        if lower_response not in valid_values:
            return False, "Response must be Yes/No (or True/False, Y/N, 1/0)"

        return True, None

    @staticmethod
    def _validate_number(response: str, template: QuestionTemplate) -> tuple[bool, Optional[str]]:
        """Validate number response"""
        try:
            num = float(response)

            if template.min_value is not None and num < template.min_value:
                return False, f"Number must be at least {template.min_value}"

            if template.max_value is not None and num > template.max_value:
                return False, f"Number must be at most {template.max_value}"

            return True, None
        except ValueError:
            return False, "Response must be a valid number"

class ResponseCollector:
    """Class for collecting and validating standup responses"""

    def __init__(self, bot_handler: BotHandler, standup_manager: StandupManager, storage_manager: StorageManager):
        self.bot_handler = bot_handler
        self.standup_manager = standup_manager
        self.storage_manager = storage_manager
        self.logger = logging.getLogger('standup_bot.response_collector')

    def format_questions(self, standup_id: int) -> str:
        """Format questions for display to the user"""
        standup = self.standup_manager.get_standup(standup_id)
        if not standup:
            return "Standup not found."

        response = f"# Status Update for {standup['name']}\n\n"
        response += "Please answer the following questions:\n\n"

        for i, question_data in enumerate(standup.get('question_templates', []), 1):
            template = QuestionTemplate.from_dict(question_data)
            response += template.format_for_display(i) + "\n"

        # If there are no question templates, fall back to simple questions
        if not standup.get('question_templates'):
            for i, question in enumerate(standup['questions'], 1):
                response += f"{i}. {question}\n"

        response += "\nReply with your answers, one per line."
        return response

    def collect_and_validate_responses(self, standup_id: int, user_id: int, content: str) -> tuple[bool, str]:
        """
        Collect and validate user responses

        Args:
            standup_id: ID of the standup
            user_id: ID of the user
            content: Message content containing responses

        Returns:
            Tuple of (success, message)
        """
        standup = self.standup_manager.get_standup(standup_id)
        if not standup:
            return False, "Standup not found."

        # Split answers by line
        answer_lines = content.strip().split('\n')

        # Get question templates or create default ones
        question_templates = []
        if standup.get('question_templates'):
            for q_data in standup['question_templates']:
                question_templates.append(QuestionTemplate.from_dict(q_data))
        else:
            # Create default templates from simple questions
            for question in standup['questions']:
                question_templates.append(QuestionTemplate(question=question))

        # Validate responses
        responses = {}
        validation_errors = []

        for i, template in enumerate(question_templates):
            response = answer_lines[i] if i < len(answer_lines) else ""
            is_valid, error = ResponseValidator.validate(response, template)

            if not is_valid:
                validation_errors.append(f"Question {i+1}: {error}")

            responses[template.question] = response

        # If there are validation errors, return them
        if validation_errors:
            error_message = "Your response has the following issues:\n\n"
            error_message += "\n".join(validation_errors)
            error_message += "\n\nPlease try again."
            return False, error_message

        # Save the responses
        if self.standup_manager.add_response(standup_id, user_id, responses):
            return True, f"Status update submitted for {standup['name']}. Thank you!"
        else:
            return False, "Failed to submit status update. Please try again."

    def create_question_templates(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create question templates from a list of question dictionaries

        Args:
            questions: List of question dictionaries with format:
                      {"question": "text", "type": "text", "required": true, ...}

        Returns:
            List of question template dictionaries
        """
        templates = []

        for q_data in questions:
            template = QuestionTemplate(
                question=q_data["question"],
                response_type=q_data.get("type", ResponseType.TEXT),
                required=q_data.get("required", True),
                choices=q_data.get("choices"),
                min_length=q_data.get("min_length"),
                max_length=q_data.get("max_length"),
                min_value=q_data.get("min_value"),
                max_value=q_data.get("max_value")
            )
            templates.append(template.to_dict())

        return templates
