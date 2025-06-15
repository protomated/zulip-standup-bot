You are building an async standup bot for Zulip that collects daily team updates via DMs and posts AI-generated summaries to channels. The bot uses Zulip's outgoing webhook API for production deployment.

## Architecture Decisions

### Bot Implementation Method
- **Use Zulip Botserver**: Deploy using the Zulip Botserver (Flask-based) that implements Zulip's outgoing webhooks API
- **Bot Type**: Create as "Outgoing webhook" bot in Zulip admin panel
- **Development**: Start with zulip-run-bot for local development/testing, then deploy to Botserver for production

### Technology Stack
- **Python 3.8+** with Flask (Zulip Botserver framework)
- **Database**: PostgreSQL for production (user timezones, response storage, settings)
- **Scheduling**: APScheduler for timezone-aware scheduling
- **AI Integration**: OpenAI API for summary generation
- **Configuration**: Environment variables for API keys and settings

## Development Structure

### Project Layout
```
standup_bot/
├── standup_bot.py          # Main bot handler class
├── config.py               # Configuration management
├── database.py             # Database models and operations
├── scheduler.py            # Timezone-aware scheduling
├── ai_summarizer.py        # OpenAI integration
├── utils.py               # Helper functions
├── requirements.txt       # Dependencies
├── captain-definition     # CapRover deployment config
└── tests/                # Unit tests
    ├── test_bot.py
    ├── test_scheduler.py
    └── fixtures/
```

### Core Components

#### Bot Handler Class
Follow Zulip's bot structure with MyBotHandler class containing usage() and handle_message() methods:

```python
class StandupBotHandler:
    def usage(self):
        return """
        Async Standup Bot - Helps teams give daily updates
        Commands:
        - /standup setup - Activate standup for this channel
        - /standup timezone <timezone> - Set your timezone
        - /standup pause/resume - Admin controls
        """

    def handle_message(self, message, bot_handler):
        # Route commands and handle responses
        pass

handler_class = StandupBotHandler
```

#### Database Schema
```sql
-- Users table for timezone and participation tracking
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    zulip_user_id VARCHAR(255) UNIQUE,
    email VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Channels table for standup configuration
CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    zulip_stream_id VARCHAR(255) UNIQUE,
    stream_name VARCHAR(255),
    prompt_time TIME DEFAULT '09:00',
    cutoff_time TIME DEFAULT '17:00',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily standup responses
CREATE TABLE standup_responses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    channel_id INTEGER REFERENCES channels(id),
    standup_date DATE,
    response_text TEXT,
    submitted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, channel_id, standup_date)
);
```

## Code Standards

### Error Handling
- **Graceful Degradation**: Never crash on API failures
- **User-Friendly Messages**: Convert technical errors to helpful user messages
- **Retry Logic**: Implement exponential backoff for transient failures
- **Logging**: Use structured logging for debugging

```python
import logging
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logging.error(f"Final attempt failed: {e}")
                        raise
                    time.sleep(delay * (2 ** attempt))
            return wrapper
    return decorator
```

### Configuration Management
```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    # Zulip Configuration
    zulip_email: str = os.getenv('ZULIP_EMAIL')
    zulip_api_key: str = os.getenv('ZULIP_API_KEY')
    zulip_site: str = os.getenv('ZULIP_SITE')

    # OpenAI Configuration
    openai_api_key: str = os.getenv('OPENAI_API_KEY')

    # Database Configuration
    database_url: str = os.getenv('DATABASE_URL')

    # Bot Configuration
    default_prompt_time: str = os.getenv('DEFAULT_PROMPT_TIME', '09:00')
    default_cutoff_time: str = os.getenv('DEFAULT_CUTOFF_TIME', '17:00')
```

### Timezone Handling
```python
import pytz
from datetime import datetime, time
from typing import Optional

def get_user_local_time(user_timezone: str, utc_time: datetime) -> datetime:
    """Convert UTC time to user's local time"""
    try:
        tz = pytz.timezone(user_timezone)
        return utc_time.replace(tzinfo=pytz.UTC).astimezone(tz)
    except pytz.UnknownTimeZoneError:
        return utc_time.replace(tzinfo=pytz.UTC)

def validate_timezone(timezone_str: str) -> bool:
    """Validate timezone string"""
    try:
        pytz.timezone(timezone_str)
        return True
    except pytz.UnknownTimeZoneError:
        return False
```

## API Integration Patterns

### Zulip API Usage
Use bot_handler.storage for persistent data and bot_handler.send_message() for responses:

```python
def send_private_message(self, bot_handler, user_email: str, content: str):
    """Send DM to specific user"""
    bot_handler.send_message({
        'type': 'private',
        'to': [user_email],
        'content': content
    })

def send_channel_message(self, bot_handler, stream: str, topic: str, content: str):
    """Send message to channel"""
    bot_handler.send_message({
        'type': 'stream',
        'to': stream,
        'topic': topic,
        'content': content
    })
```

### OpenAI Integration
```python
import openai
from typing import List, Dict

async def generate_summary(self, responses: List[Dict]) -> str:
    """Generate AI summary of standup responses"""
    prompt = self._build_summary_prompt(responses)

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes team standup updates."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return self._generate_fallback_summary(responses)
```

## Testing Strategy

### Unit Tests
Use Zulip's testing framework with StubBotTestCase for bot testing:

```python
from zulip_bots.test_lib import StubBotTestCase

class TestStandupBot(StubBotTestCase):
    bot_name = 'standup_bot'

    def test_setup_command(self):
        with self.mock_config_info({'key': 'value'}):
            self.verify_reply('/standup setup', 'Standup activated for this channel!')

    def test_timezone_command(self):
        dialog = [
            ('/standup timezone America/New_York', 'Timezone set to America/New_York'),
            ('/standup timezone Invalid/Zone', 'Invalid timezone. Please use format like America/New_York')
        ]
        self.verify_dialog(dialog)
```

### Integration Tests
```python
def test_end_to_end_standup_flow():
    """Test complete standup cycle"""
    # Setup channel
    # Send prompts
    # Collect responses
    # Generate summary
    # Verify summary posted
    pass
```

## Security & Privacy

### Data Handling
- **Minimal Storage**: Only store essential data (timezones, responses for current day)
- **Response Cleanup**: Delete old standup responses after summary generation
- **API Key Security**: Never log or expose API keys
- **User Privacy**: Responses only visible in final summary, not individually

### Input Validation
```python
def validate_command_input(command: str, args: List[str]) -> bool:
    """Validate user input for commands"""
    sanitized_args = [arg.strip() for arg in args if arg.strip()]

    if command == 'timezone':
        return len(sanitized_args) == 1 and validate_timezone(sanitized_args[0])
    elif command == 'time':
        return len(sanitized_args) == 1 and validate_time_format(sanitized_args[0])

    return True
```

## Deployment Preparation

### Environment Variables Required
```bash
# Zulip Configuration
ZULIP_EMAIL=standup-bot@your-org.zulipchat.com
ZULIP_API_KEY=your_bot_api_key
ZULIP_SITE=https://your-org.zulipchat.com

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Database Configuration
DATABASE_URL=postgresql://user:password@host:port/database

# Optional Configuration
DEFAULT_PROMPT_TIME=09:00
DEFAULT_CUTOFF_TIME=17:00
```

### Dependencies (requirements.txt)
```
zulip==0.8.2
zulip-bots==0.8.2
psycopg2-binary==2.9.5
openai==1.3.0
APScheduler==3.10.4
pytz==2023.3
python-dotenv==1.0.0
```

## Performance Considerations

### Async Operations
- Use async/await for OpenAI API calls
- Batch database operations when possible
- Implement connection pooling for database

### Scheduling Efficiency
- Single scheduler instance with timezone-aware jobs
- Avoid polling; use event-driven architecture
- Cache user timezone data to reduce database queries

### Error Recovery
- Implement circuit breaker pattern for external APIs
- Queue failed operations for retry
- Graceful degradation when services unavailable

## Development Workflow

1. **Start with Local Bot**: Use zulip-run-bot for development and testing
2. **Implement Core Logic**: Build handler class with command routing
3. **Add Database Layer**: Implement models and data persistence
4. **Integrate Scheduling**: Add timezone-aware prompt scheduling
5. **Add AI Summary**: Integrate OpenAI for summary generation
6. **Production Deploy**: Deploy to Zulip Botserver with CapRover

Remember: Your bot code should work exactly like it does with zulip-run-bot when deployed to Botserver. Focus on making the core bot logic robust and testable before adding deployment complexity.
