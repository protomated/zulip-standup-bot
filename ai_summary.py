import openai
from typing import Dict, Any, List


class AISummaryGenerator:
    """
    Handles AI-generated summaries of standup responses
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key

    def generate_summary(self, standup_name: str, responses: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate a summary of standup responses using AI

        Args:
            standup_name: Name of the standup
            responses: Dictionary of user responses

        Returns:
            Generated summary text
        """
        if not responses:
            return "No responses to summarize."

        # Prepare the prompt with standup responses
        prompt = self._prepare_prompt(standup_name, responses)

        try:
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",
                     "content": "You are an assistant that creates concise and insightful summaries of team standup meetings. Focus on progress, blockers, and action items."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )

            # Extract and return the summary
            return response.choices[0].message.content.strip()

        except Exception as e:
            # Handle API errors
            print(f"Error generating AI summary: {e}")
            return "Unable to generate summary at this time. Please try again later."

    def _prepare_prompt(self, standup_name: str, responses: Dict[str, Dict[str, Any]]) -> str:
        """Prepare the prompt for the AI model"""
        prompt = f"Please summarize the following '{standup_name}' standup meeting responses:\n\n"

        for user_id, data in responses.items():
            prompt += f"User {user_id}:\n"
            for question, answer in data['responses'].items():
                prompt += f"Q: {question}\nA: {answer}\n"
            prompt += "\n"

        prompt += "\nPlease create a concise summary that highlights key progress points, common blockers, and action items. Format the summary with sections for 'Accomplishments', 'In Progress', 'Blockers', and 'Action Items'."

        return prompt