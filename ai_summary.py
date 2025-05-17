import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
import tiktoken
import time
import json


class AISummaryGenerator:
    """
    Handles AI-generated summaries of standup responses with caching,
    token optimization, and error handling
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.logger = logging.getLogger('standup_bot.ai_summary')
        self.cache = {}  # Simple in-memory cache
        self.cache_timestamps = {}  # Track when entries were added to cache
        self.max_cache_age = 7 * 24 * 60 * 60  # 7 days in seconds
        self.max_cache_size = 100  # Maximum number of entries in cache
        self.max_tokens = 4000  # Maximum tokens for input
        self.model = "gpt-3.5-turbo"  # Default model
        self.encoding = tiktoken.encoding_for_model(self.model)
        self.last_cache_cleanup = time.time()  # Track when cache was last cleaned

    def generate_summary(self, standup_name: str, responses: Dict[str, Dict[str, Any]],
                         standup_id: str = None, date: str = None) -> str:
        """
        Generate a summary of standup responses using AI with caching

        Args:
            standup_name: Name of the standup
            responses: Dictionary of user responses
            standup_id: ID of the standup (for caching)
            date: Date of the standup (for caching)

        Returns:
            Generated summary text
        """
        if not responses:
            return "No responses to summarize."

        if not self.client:
            self.logger.warning("OpenAI API key not configured. AI summaries are disabled.")
            return "AI summaries are not available (API key not configured)."

        # Check if cache cleanup is needed (every hour)
        if time.time() - self.last_cache_cleanup > 3600:  # 1 hour in seconds
            self._cleanup_cache()

        # Check cache if standup_id and date are provided
        cache_key = f"{standup_id}_{date}" if standup_id and date else None
        if cache_key and cache_key in self.cache:
            self.logger.info(f"Using cached summary for standup {standup_id} on {date}")
            # Update the timestamp to mark this entry as recently used
            self.cache_timestamps[cache_key] = time.time()
            return self.cache[cache_key]

        # Prepare the prompt with standup responses
        prompt = self._prepare_prompt(standup_name, responses)

        # Optimize token usage
        prompt = self._optimize_tokens(prompt)

        # Retry logic for API calls
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Call OpenAI API with enhanced system message
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system",
                         "content": """You are an expert project manager who creates clear, actionable summaries of team standup meetings.
Your summaries should:
1. Identify key accomplishments and progress across the team
2. Highlight ongoing work and priorities
3. Surface blockers and dependencies that need attention
4. Extract clear action items that require follow-up
5. Recognize patterns and themes across multiple team members' updates

Keep your summary concise but comprehensive, focusing on information that would be most valuable to a team lead or project manager.
Use clear section headings and bullet points for readability. Be specific about what was accomplished and what's being worked on.
Avoid vague statements and focus on concrete details from the standup responses."""},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=600,  # Increased token limit for more detailed summaries
                    temperature=0.5  # Lower temperature for more consistent, focused output
                )

                # Extract the summary
                summary = response.choices[0].message.content.strip()

                # Cache the result if caching is enabled
                if cache_key:
                    self.cache[cache_key] = summary
                    self.cache_timestamps[cache_key] = time.time()
                    self.logger.debug(f"Cached summary for standup {standup_id} on {date}")

                    # Check if cache is too large and remove oldest entries if needed
                    if len(self.cache) > self.max_cache_size:
                        self._trim_cache()

                return summary

            except Exception as e:
                # Check if this is a rate limit error
                is_rate_limit = False
                retry_time = retry_delay

                if hasattr(e, 'status_code') and e.status_code == 429:
                    is_rate_limit = True
                    # Try to extract retry-after header if available
                    if hasattr(e, 'headers') and 'retry-after' in e.headers:
                        try:
                            retry_time = int(e.headers['retry-after'])
                            self.logger.warning(f"Rate limited. Retrying after {retry_time} seconds as specified by API")
                        except (ValueError, TypeError):
                            # If parsing fails, use exponential backoff
                            retry_time = retry_delay * (2 ** attempt)
                            self.logger.warning(f"Rate limited. Using exponential backoff: {retry_time} seconds")
                    else:
                        # If no retry-after header, use exponential backoff with longer base time
                        retry_time = (retry_delay * 2) * (2 ** attempt)
                        self.logger.warning(f"Rate limited without retry-after header. Using longer backoff: {retry_time} seconds")

                error_msg = "Rate limit exceeded" if is_rate_limit else str(e)
                self.logger.error(f"Error generating AI summary (attempt {attempt+1}/{max_retries}): {error_msg}")

                if attempt < max_retries - 1:
                    # Use the calculated retry time for rate limits, or standard exponential backoff for other errors
                    if not is_rate_limit:
                        retry_time = retry_delay * (2 ** attempt)

                    self.logger.info(f"Retrying in {retry_time} seconds...")
                    time.sleep(retry_time)
                else:
                    # Return a fallback summary on final failure
                    self.logger.warning("All retry attempts failed. Generating fallback summary.")
                    return self._generate_fallback_summary(responses)

    def _prepare_prompt(self, standup_name: str, responses: Dict[str, Dict[str, Any]]) -> str:
        """Prepare the prompt for the AI model with improved formatting and structure"""
        prompt = f"# Standup Meeting: {standup_name}\n\n"

        # Extract common questions to organize responses by topic
        questions = set()
        for user_data in responses.values():
            questions.update(user_data['responses'].keys())

        questions_list = list(questions)

        # Group responses by question for better context
        prompt += "## Team Updates\n\n"

        # First, add a section with all participants for context
        prompt += "### Participants\n"
        for user_id in responses.keys():
            prompt += f"- User {user_id}\n"
        prompt += "\n"

        # Then organize by question/topic
        for question in questions_list:
            prompt += f"### {question}\n\n"
            for user_id, data in responses.items():
                if question in data['responses']:
                    prompt += f"**User {user_id}**: {data['responses'][question]}\n\n"

        # Enhanced summary instructions
        prompt += "\n## Summary Instructions\n"
        prompt += "Create a concise, actionable summary of this standup meeting with the following sections:\n\n"
        prompt += "1. **Key Accomplishments**: What has the team completed recently? Highlight significant progress and milestones.\n"
        prompt += "2. **Work in Progress**: What is the team currently working on? Identify main focus areas and ongoing tasks.\n"
        prompt += "3. **Blockers & Challenges**: What issues is the team facing? Highlight any dependencies, technical problems, or resource constraints.\n"
        prompt += "4. **Action Items**: What needs attention or follow-up? List specific tasks, decisions needed, or important next steps.\n\n"
        prompt += "Format your response with clear section headings. Be specific and concise, focusing on the most important information. Identify patterns and common themes across team members' updates."

        return prompt

    def _optimize_tokens(self, prompt: str) -> str:
        """
        Optimize token usage by intelligently truncating the prompt while preserving structure
        and ensuring all question categories are represented
        """
        tokens = self.encoding.encode(prompt)

        if len(tokens) <= self.max_tokens:
            return prompt

        # If prompt is too long, truncate it while preserving structure
        self.logger.warning(f"Prompt too long ({len(tokens)} tokens). Truncating to {self.max_tokens} tokens.")

        # Split the prompt into sections
        try:
            header = prompt.split("## Team Updates")[0] + "## Team Updates\n\n"
            updates_section = prompt.split("## Team Updates")[1].split("## Summary Instructions")[0]
            footer = "\n\n## Summary Instructions" + prompt.split("## Summary Instructions")[1]
        except IndexError:
            # If the prompt doesn't have the expected structure, fall back to a simple truncation
            self.logger.error("Prompt doesn't have the expected structure for intelligent truncation")
            simple_tokens = tokens[:self.max_tokens]
            return self.encoding.decode(simple_tokens)

        # Encode the header and footer to calculate available tokens
        header_tokens = self.encoding.encode(header)
        footer_tokens = self.encoding.encode(footer)

        # Calculate how many tokens we can keep for the updates section
        available_tokens = self.max_tokens - len(header_tokens) - len(footer_tokens)

        if available_tokens <= 0:
            # If we can't fit updates, return a minimal prompt
            return "Please summarize the standup meeting with sections for 'Key Accomplishments', 'Work in Progress', 'Blockers & Challenges', and 'Action Items'."

        # Split the updates section into question categories
        question_sections = []
        current_section = ""
        lines = updates_section.split("\n")

        for line in lines:
            if line.startswith("### ") and current_section:
                question_sections.append(current_section)
                current_section = line + "\n"
            else:
                current_section += line + "\n"

        if current_section:
            question_sections.append(current_section)

        # If we have the participants section, keep it separate
        participants_section = ""
        if question_sections and "### Participants" in question_sections[0]:
            participants_section = question_sections.pop(0)

        # Calculate tokens per question section
        if not question_sections:
            # If no question sections found, fall back to simple truncation
            updates_tokens = self.encoding.encode(updates_section)
            truncated_updates = self.encoding.decode(updates_tokens[:available_tokens])
            return header + truncated_updates + footer

        # Distribute available tokens evenly across question sections
        tokens_per_section = available_tokens // len(question_sections)

        # Keep participants section if it exists and there are enough tokens
        if participants_section:
            participants_tokens = self.encoding.encode(participants_section)
            if len(participants_tokens) < available_tokens * 0.1:  # Use at most 10% for participants
                available_tokens -= len(participants_tokens)
                tokens_per_section = available_tokens // len(question_sections)
            else:
                # If participants section is too large, truncate it
                max_participants_tokens = int(available_tokens * 0.1)
                participants_section = self.encoding.decode(participants_tokens[:max_participants_tokens])
                available_tokens -= len(self.encoding.encode(participants_section))
                tokens_per_section = available_tokens // len(question_sections)

        # Truncate each question section to fit within its token allocation
        truncated_sections = []
        remaining_tokens = available_tokens

        for section in question_sections:
            section_tokens = self.encoding.encode(section)

            # If this section is smaller than its allocation, use fewer tokens
            tokens_for_section = min(tokens_per_section, len(section_tokens))

            # If this is the last section, use all remaining tokens
            if section == question_sections[-1]:
                tokens_for_section = remaining_tokens

            truncated_section = self.encoding.decode(section_tokens[:tokens_for_section])
            truncated_sections.append(truncated_section)

            remaining_tokens -= len(self.encoding.encode(truncated_section))
            if remaining_tokens <= 0:
                break

        # Reassemble the prompt
        truncated_updates = participants_section + "".join(truncated_sections)

        return header + truncated_updates + footer

    def _generate_fallback_summary(self, responses: Dict[str, Dict[str, Any]]) -> str:
        """
        Generate a more structured fallback summary when the API call fails,
        organized by the standard sections we want in the summary
        """
        summary = "# Standup Summary (AI-generated summary unavailable)\n\n"

        # Count participants
        participant_count = len(responses)
        summary += f"**Participants:** {participant_count}\n\n"

        # Extract common questions to organize responses by topic
        questions = set()
        for user_data in responses.values():
            questions.update(user_data['responses'].keys())

        # Identify common question patterns to categorize them
        accomplishment_questions = []
        progress_questions = []
        blocker_questions = []

        for question in questions:
            q_lower = question.lower()
            if any(term in q_lower for term in ['accomplish', 'complete', 'finish', 'done', 'yesterday']):
                accomplishment_questions.append(question)
            elif any(term in q_lower for term in ['today', 'working on', 'progress', 'plan']):
                progress_questions.append(question)
            elif any(term in q_lower for term in ['blocker', 'challenge', 'issue', 'problem', 'obstacle']):
                blocker_questions.append(question)

        # Extract responses by category
        accomplishment_responses = []
        progress_responses = []
        blocker_responses = []

        for user_id, data in responses.items():
            for question, answer in data['responses'].items():
                if question in accomplishment_questions:
                    accomplishment_responses.append(answer)
                elif question in progress_questions:
                    progress_responses.append(answer)
                elif question in blocker_questions:
                    blocker_responses.append(answer)

        # Generate section summaries using keyword extraction
        summary += "## Key Accomplishments\n"
        if accomplishment_responses:
            keywords = self._extract_keywords(accomplishment_responses, max_keywords=8)
            if keywords:
                summary += f"Team members mentioned: {', '.join(keywords)}\n\n"
            else:
                summary += "No clear accomplishments identified.\n\n"
        else:
            summary += "No accomplishment information available.\n\n"

        summary += "## Work in Progress\n"
        if progress_responses:
            keywords = self._extract_keywords(progress_responses, max_keywords=8)
            if keywords:
                summary += f"Team is working on: {', '.join(keywords)}\n\n"
            else:
                summary += "No clear work in progress identified.\n\n"
        else:
            summary += "No information on current work available.\n\n"

        summary += "## Blockers & Challenges\n"
        if blocker_responses:
            keywords = self._extract_keywords(blocker_responses, max_keywords=8)
            if keywords:
                summary += f"Potential issues: {', '.join(keywords)}\n\n"
            else:
                summary += "No clear blockers identified.\n\n"
        else:
            summary += "No blocker information available.\n\n"

        # Extract all keywords for action items (less structured)
        all_responses = []
        for user_id, data in responses.items():
            for question, answer in data['responses'].items():
                all_responses.append(answer)

        summary += "## Action Items\n"
        action_keywords = self._extract_action_items(all_responses)
        if action_keywords:
            summary += "Potential action items:\n"
            for item in action_keywords[:5]:  # Limit to top 5
                summary += f"- {item}\n"
        else:
            summary += "No clear action items identified.\n"

        summary += "\n*This is an automated summary generated when AI processing was unavailable. Please review individual updates for more details.*"
        return summary

    def _extract_keywords(self, texts: List[str], max_keywords: int = 5) -> List[str]:
        """Extract common keywords from a list of texts"""
        # Simple keyword extraction based on frequency
        word_count = {}
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'as',
                     'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
                     'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'this', 'that',
                     'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}

        for text in texts:
            words = text.lower().split()
            for word in words:
                # Clean the word
                word = word.strip('.,!?()[]{}":;')
                if len(word) > 3 and word not in stop_words:
                    word_count[word] = word_count.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)

        # Return top keywords
        return [word for word, count in sorted_words[:max_keywords]]

    def _extract_action_items(self, texts: List[str]) -> List[str]:
        """
        Extract potential action items from text responses
        Looks for phrases that suggest tasks, follow-ups, or decisions
        """
        action_items = []

        # Action item indicators
        action_phrases = [
            'need to', 'needs to', 'should', 'will', 'going to',
            'plan to', 'planning to', 'must', 'have to', 'has to',
            'required to', 'scheduled to', 'pending', 'waiting for',
            'blocked by', 'depends on', 'follow up', 'follow-up',
            'todo', 'to-do', 'to do', 'action item', 'next step'
        ]

        # Process each text
        for text in texts:
            # Split into sentences
            sentences = text.replace('\n', ' ').split('.')

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # Check if sentence contains action phrases
                sentence_lower = sentence.lower()
                if any(phrase in sentence_lower for phrase in action_phrases):
                    # Clean up the sentence
                    clean_sentence = sentence.strip()

                    # Truncate very long sentences
                    if len(clean_sentence) > 100:
                        clean_sentence = clean_sentence[:97] + '...'

                    # Add to action items if not already present
                    if clean_sentence not in action_items:
                        action_items.append(clean_sentence)

        # If no action items found with phrases, look for sentences with verbs at the beginning
        if not action_items:
            verb_starters = ['review', 'complete', 'finish', 'implement', 'create', 'update', 'fix', 'resolve',
                            'discuss', 'meet', 'schedule', 'prepare', 'send', 'check', 'investigate']

            for text in texts:
                sentences = text.replace('\n', ' ').split('.')

                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    words = sentence.lower().split()
                    if words and words[0] in verb_starters:
                        # Clean up the sentence
                        clean_sentence = sentence.strip()

                        # Truncate very long sentences
                        if len(clean_sentence) > 100:
                            clean_sentence = clean_sentence[:97] + '...'

                        # Add to action items if not already present
                        if clean_sentence not in action_items:
                            action_items.append(clean_sentence)

        return action_items

    def _cleanup_cache(self) -> None:
        """
        Remove old entries from the cache based on age
        """
        current_time = time.time()
        self.last_cache_cleanup = current_time

        # Find keys of entries that are too old
        keys_to_remove = []
        for key, timestamp in self.cache_timestamps.items():
            if current_time - timestamp > self.max_cache_age:
                keys_to_remove.append(key)

        # Remove old entries
        for key in keys_to_remove:
            if key in self.cache:
                del self.cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]

        if keys_to_remove:
            self.logger.debug(f"Removed {len(keys_to_remove)} old entries from AI summary cache")

        # Also trim the cache if it's still too large
        if len(self.cache) > self.max_cache_size:
            self._trim_cache()

    def _trim_cache(self) -> None:
        """
        Trim the cache to the maximum size by removing the oldest entries
        """
        # Sort entries by timestamp (oldest first)
        sorted_entries = sorted(self.cache_timestamps.items(), key=lambda x: x[1])

        # Calculate how many entries to remove
        entries_to_remove = len(self.cache) - self.max_cache_size

        if entries_to_remove <= 0:
            return

        # Remove the oldest entries
        for i in range(entries_to_remove):
            if i < len(sorted_entries):
                key = sorted_entries[i][0]
                if key in self.cache:
                    del self.cache[key]
                if key in self.cache_timestamps:
                    del self.cache_timestamps[key]

        self.logger.debug(f"Trimmed AI summary cache by removing {entries_to_remove} oldest entries")

    def clear_cache(self) -> None:
        """Clear the summary cache"""
        self.cache = {}
        self.cache_timestamps = {}
        self.last_cache_cleanup = time.time()
        self.logger.debug("AI summary cache cleared")

    def get_cached_summary(self, standup_id: str, date: str) -> Optional[str]:
        """Get a cached summary if available"""
        cache_key = f"{standup_id}_{date}"
        summary = self.cache.get(cache_key)

        # Update timestamp if entry exists to mark it as recently used
        if summary and cache_key in self.cache_timestamps:
            self.cache_timestamps[cache_key] = time.time()

        return summary
