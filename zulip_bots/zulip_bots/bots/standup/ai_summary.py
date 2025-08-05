import os
import logging
import json
import datetime
from typing import Any, Dict, List, Optional
import requests

class GroqSummaryGenerator:
    """
    AI Summary generator using Groq API for fast, cheap LLM inference.
    """

    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.api_base = "https://api.groq.com/openai/v1"
        self.model = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')  # Fast, cheap model

        if not self.api_key:
            logging.warning("GROQ_API_KEY not set. AI summary generation will not be available.")

    def is_available(self) -> bool:
        """Check if AI summary generation is available."""
        return bool(self.api_key)

    def generate_summary(self, responses: List[Dict[str, str]], last_day_description: str = "yesterday") -> str:
        """
        Generate an AI summary of standup responses using Groq.
        """
        if not responses:
            return "No standup responses were received today."

        if not self.api_key:
            logging.warning("Groq API key not available, falling back to manual summary")
            return self._generate_manual_summary(responses, last_day_description)

        try:
            # Format the responses for the prompt
            formatted_responses = json.dumps(responses, indent=2)

            # Create the prompt optimized for Llama
            last_day_label = last_day_description.capitalize()
            prompt = f"""You are an assistant that creates concise team standup summaries.

Analyze these standup responses and create a brief summary with:
1. Key work completed {last_day_description}
2. Today's planned work
3. Any blockers that need attention

Keep it concise and highlight important items. Use bullet points for clarity.

Here's an example of a response:
```
##### Key Work Completed {last_day_label}:
* **User**:

  * Summary 1

  * Summary 2

* **Another User**:

  * Summary 1

  * Summary 2

##### Today's Planned Work:
* **User**:

  * Summary 1

  * Summary 2

* **Another User**:

  * Summary 1

  * Summary 2

##### Blockers:
* **User**: Blocker Summary
```

Standup Responses:
{formatted_responses}

Summary:"""

            # Call the Groq API
            response = self._call_groq_api(prompt)

            if response:
                return response
            else:
                logging.warning("Groq API call failed, falling back to manual summary")
                return self._generate_manual_summary(responses, last_day_description)

        except Exception as e:
            logging.error(f"Error generating AI summary with Groq: {e}")
            return self._generate_manual_summary(responses, last_day_description)

    def _call_groq_api(self, prompt: str) -> Optional[str]:
        """
        Make a request to the Groq API.
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates concise, professional team standup summaries."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 500,  # Keep it concise
                "temperature": 0.3,  # Lower temperature for consistent summaries
                "top_p": 1,
                "stream": False
            }

            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()

            result = response.json()

            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content'].strip()
            else:
                logging.error(f"Unexpected Groq API response format: {result}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error calling Groq API: {e}")
            return None
        except Exception as e:
            logging.error(f"Error parsing Groq API response: {e}")
            return None

    def _generate_manual_summary(self, responses: List[Dict[str, str]], last_day_description: str = "yesterday") -> str:
        """
        Generate a manual summary when AI is not available.
        """
        if not responses:
            return "No standup responses were received today."

        # Create the summary
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        summary = f"# Daily Standup Summary - {today}\n\n"
        summary += f"**Participants:** {len(responses)}\n\n"

        # Add individual updates
        summary += "## Individual Updates\n\n"

        for response in responses:
            name = response.get('name', 'Unknown')
            yesterday = response.get('yesterday', 'No response')
            today_work = response.get('today', 'No response')
            blockers = response.get('blockers', 'None')

            day_label = last_day_description.capitalize()
            summary += f"### {name}\n"
            summary += f"**{day_label}:** {yesterday}\n"
            summary += f"**Today:** {today_work}\n"
            summary += f"**Blockers:** {blockers}\n\n"

        # Add blockers section if any exist
        blockers_exist = any(
            response.get('blockers', 'None').lower() not in ['none', 'no', 'n/a', '']
            for response in responses
        )

        if blockers_exist:
            summary += "## ⚠️ Blockers Requiring Attention\n\n"
            for response in responses:
                name = response.get('name', 'Unknown')
                blockers = response.get('blockers', 'None')
                if blockers.lower() not in ['none', 'no', 'n/a', '']:
                    summary += f"- **{name}:** {blockers}\n"

        return summary

# Create a singleton instance
summary_generator = GroqSummaryGenerator()
