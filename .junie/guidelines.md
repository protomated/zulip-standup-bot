# Zulip Standup Bot Development Guidelines

## Project Overview

This project aims to create a comprehensive standup meeting automation bot for Zulip. The bot will enable teams to conduct asynchronous standup meetings, collect responses, generate AI-powered summaries, and provide detailed reports. The goal is to create a user-friendly, full-featured bot that can be set up in under 60 seconds.

## Key Features

1. **Fast Setup**: Simple, intuitive commands to create standup meetings quickly
2. **Multiple Teams Support**: Ability to create different standups for different teams/projects
3. **AI-Powered Summaries**: Automatically generate summaries using AI (OpenAI API)
4. **Asynchronous Workflows**: Support for same-timezone or local-timezone meetings
5. **Comprehensive Reports**: Detailed, well-formatted standup reports
6. **Flexible Scheduling**: Powerful scheduling options with out-of-office awareness
7. **Historical Data**: Access to past standup meetings and responses
8. **Activity Statistics**: Participation tracking and analytics
9. **Smart Reminders**: Automatic reminders for participants

## Architecture Overview

The bot follows a modular architecture with clear separation of concerns:

```
standup-bot/
│
├── standup_bot/           # Main package directory
│   ├── __init__.py        # Package initialization
│   ├── bot.py             # Main bot handler class
│   ├── standup_manager.py # Standup meeting management
│   ├── storage_manager.py # Persistent storage handling
│   ├── ai_summary.py      # AI summary generation with OpenAI
│   ├── templates.py       # Message templates
│   ├── report_generator.py# Report generation and formatting
│   ├── scheduler.py       # Scheduling and automation
│   └── reminder_service.py# Reminder functionality
├── tests/                 # Test directory
│   ├── __init__.py        # Test package initialization
│   ├── test_bot.py        # Tests for bot.py
│   ├── test_standup_manager.py  # Tests for standup_manager.py
│   └── ...                # Other test files
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose for local development
├── captain-definition     # CapRover deployment configuration
├── .dockerignore          # Docker ignore file
├── config.py              # Configuration settings
├── run.py                 # Script to run the bot
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── pyproject.toml         # Project metadata and build configuration
└── README.md              # Project documentation
```

## Implementation Priorities

Follow this order when implementing the bot:

1. **Project Setup**: Establish basic structure and Docker configuration
2. **Core Bot Structure**: Set up the basic bot framework with command handling
3. **Storage System**: Implement persistent storage for standup data
4. **Standup Creation**: Implement the standup setup process
5. **Response Collection**: Ability to collect and store user responses
6. **Report Generation**: Basic report generation without AI summaries
7. **Scheduling**: Implement meeting scheduling functionality
8. **Reminders**: Add the reminder system
9. **AI Summaries**: Integrate with OpenAI for summaries
10. **Analytics**: Implement participation tracking and statistics
11. **Advanced Features**: Additional features like timezone support, history browsing

## Code Style Guidelines

### General Principles

- Use Python 3.8+ features
- Follow PEP 8 style guide
- Use type hints throughout the codebase
- Write docstrings for all classes and methods

### Naming Conventions

- Use snake_case for variables, functions, and file names
- Use PascalCase for class names
- Use descriptive, intention-revealing names
- Prefix private methods with underscore (e.g., `_private_method`)

### Error Handling

- Use appropriate exception handling
- Log errors with context information
- Gracefully handle API failures, especially with external services like OpenAI

### Documentation

- Document all public methods with docstrings
- Include parameter descriptions and return value types
- Document complex algorithms or business logic with comments

## Docker and CapRover Deployment

This project will be deployed using Docker containers on CapRover. Follow these guidelines for containerization and deployment:

### Docker Configuration

1. Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user to run the application
RUN useradd -m botuser
USER botuser

# Command to run the application
CMD ["python", "run.py"]
```

2. Create a `.dockerignore` file:

```
.git
.github
.venv
**/__pycache__
**/*.pyc
.pytest_cache
.coverage
htmlcov
tests/
```

### CapRover Deployment

1. Add a `captain-definition` file to the root of the project:

```json
{
  "schemaVersion": 2,
  "dockerfilePath": "./Dockerfile"
}
```

2. Create environment variable handling:
   - Store sensitive information like API keys in CapRover's environment variables
   - In the application, read these from environment variables

```python
# config.py example
import os

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ZULIP_EMAIL = os.environ.get('ZULIP_EMAIL')
ZULIP_API_KEY = os.environ.get('ZULIP_API_KEY')
ZULIP_SITE = os.environ.get('ZULIP_SITE')
```

3. Configure CapRover application:
   - Set up persistent storage for bot data if needed
   - Configure environment variables in the CapRover dashboard
   - Set up automatic deployment from your Git repository

### Docker Compose for Local Development

Create a `docker-compose.yml` file for local testing:

```yaml
version: '3.8'

services:
  standup-bot:
    build: .
    volumes:
      - .:/app
    environment:
      - OPENAI_API_KEY=your_test_key_here
      - ZULIP_EMAIL=bot-email@example.com
      - ZULIP_API_KEY=your_bot_api_key
      - ZULIP_SITE=https://your-zulip-site.example.com
```

### CI/CD Integration

Set up GitHub Actions to automatically deploy to CapRover:

1. Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to CapRover

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to CapRover
        uses: caprover/deploy-from-github@v1.0.1
        with:
          server: '${{ secrets.CAPROVER_SERVER }}'
          app: '${{ secrets.CAPROVER_APP }}'
          token: '${{ secrets.CAPROVER_TOKEN }}'
```

## Storage Design

The bot should use Zulip's bot storage system for persistence. Data should be organized as follows:

### Standups

```json
{
  "standups": {
    "12345": {
      "id": 12345,
      "name": "Engineering Standup",
      "creator_id": 101,
      "team_stream": "Engineering",
      "schedule": {
        "days": ["monday", "wednesday", "friday"],
        "time": "09:00",
        "timezone": "UTC",
        "duration": 86400
      },
      "questions": [
        "What did you accomplish yesterday?",
        "What do you plan to do today?",
        "Any blockers?"
      ],
      "participants": [101, 102, 103],
      "timezone_handling": "same",
      "active": true,
      "created_at": "2023-05-01T10:00:00Z",
      "responses": {
        "2023-05-01": {
          "101": {
            "responses": {
              "What did you accomplish yesterday?": "Implemented feature X",
              "What do you plan to do today?": "Working on feature Y",
              "Any blockers?": "None"
            },
            "timestamp": "2023-05-01T09:15:00Z"
          }
        }
      },
      "history": [
        {
          "date": "2023-05-01",
          "participation_rate": 0.33,
          "ai_summary": "The team is making progress on feature X..."
        }
      ]
    }
  }
}
```

## Command Interface Design

The bot should support the following commands:

1. `help` - Display help information
2. `setup` - Interactive setup for a new standup
3. `list` - List all standups the user is part of
4. `status [standup_id]` - Submit status for a standup
5. `remind [standup_id]` - Send reminders to participants
6. `report [standup_id] [date]` - Generate a report
7. `cancel [standup_id]` - Cancel a standup
8. `settings [standup_id]` - Adjust standup settings

Design the commands to be intuitive and provide helpful feedback.

## Zulip API Usage

Use the Zulip Python API client (`zulip`) for interacting with Zulip. Key API functionalities to use:

- Send messages to streams and users
- Get user information
- Subscribe to streams

## Error Handling Strategy

- Use a centralized error handling approach
- Provide user-friendly error messages
- Log detailed error information for debugging
- Gracefully recover from transient failures
- Handle API rate limits, especially for OpenAI

## AI Integration Guidelines

When implementing the OpenAI integration:

1. Use the most appropriate model (e.g., `gpt-3.5-turbo` or `gpt-4`)
2. Design effective prompts that generate concise, useful summaries
3. Handle API errors and rate limits gracefully
4. Include fallback mechanisms when AI is unavailable
5. Consider token usage and optimization
6. Make AI optional to avoid dependency on external services

## Testing Guidelines

### Unit Tests

- Create unit tests for each module
- Use pytest as the testing framework
- Mock external services like Zulip API and OpenAI
- Aim for high test coverage, especially for critical components

Example test structure:
```
tests/
├── test_standup_manager.py
├── test_storage_manager.py
├── test_scheduler.py
└── ...
```

### Integration Tests

- Create integration tests that verify the interaction between modules
- Test the end-to-end functionality using a test Zulip instance
- Include Docker-based tests to ensure the application works in the container environment

### Docker Testing

Test the Docker container locally before deployment:

```bash
# Build the Docker image
docker build -t standup-bot .

# Run the container with test configuration
docker run -e ZULIP_EMAIL=test@example.com -e ZULIP_API_KEY=test_key standup-bot
```

## Security Considerations

- Never hardcode API keys or sensitive information
- Use environment variables or secure configuration files
- Follow the principle of least privilege
- Properly validate and sanitize user inputs
- Be cautious with message formatting to avoid injection attacks

## Performance Optimization

- Use cached storage to minimize API calls
- Batch operations when possible
- Be mindful of memory usage, especially with large standups
- Optimize scheduling to minimize resource usage
- Handle concurrent operations gracefully

## Documentation Requirements

Create comprehensive documentation:

1. **README.md**: Installation, usage, feature overview, and Docker deployment instructions
2. **SETUP.md**: Detailed setup instructions focused on Docker and CapRover
3. **COMMANDS.md**: Complete command reference
4. **ARCHITECTURE.md**: Technical architecture documentation
5. **DOCKER.md**: Docker-specific configuration and best practices
6. **DEVELOPMENT.md**: Development workflow using Docker

## Implementation Notes

### Standup Creation Flow

The standup creation flow should be interactive:

1. User types `setup`
2. Bot asks for standup name
3. Bot asks for team stream
4. Bot asks for schedule (days of week, time)
5. Bot asks for questions (default questions provided)
6. Bot asks for participants
7. Bot confirms and creates the standup

### AI Summary Generation

When generating AI summaries:

1. Format the standup data into a clear prompt
2. Request a structured summary with sections
3. Limit token usage to control costs
4. Parse and format the AI response for readability

### Scheduler Implementation

The scheduler should:

1. Run in a background thread
2. Use a priority queue for scheduled tasks
3. Handle system restarts gracefully
4. Properly calculate next occurrence dates
5. Support timezone conversions

## Resource Management

- Use connection pooling for API clients
- Implement proper cleanup of resources
- Handle bot shutdown gracefully
- Consider persistence across bot restarts

## Modern Python Project Structure

This project follows modern Python project practices:

1. Use `pyproject.toml` for project configuration:
   ```toml
   [build-system]
   requires = ["setuptools>=42", "wheel"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "standup-bot"
   version = "0.1.0"
   description = "A Zulip bot for automating standup meetings"
   authors = [{name = "Your Name", email = "your.email@example.com"}]
   requires-python = ">=3.8"
   readme = "README.md"
   license = {text = "MIT"}
   
   [project.optional-dependencies]
   dev = [
       "pytest>=7.0.0",
       "pytest-cov",
       "pytest-mock",
   ]
   
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   python_files = "test_*.py"
   ```

2. Add a `setup.py` for compatibility (minimal):
   ```python
   from setuptools import setup

   setup()
   ```

3. Create an `__init__.py` in the main package folder to enable imports

## Final Notes

This project prioritizes:

1. **Reliability**: The bot should work consistently
2. **Usability**: Commands should be intuitive and user-friendly
3. **Performance**: The bot should be responsive and efficient
4. **Flexibility**: Support various standup configurations
5. **Security**: Handle user data securely
6. **Containerization**: Proper Docker configuration for deployment
7. **Cloud-Native**: CapRover deployment compatible

Remember that the primary goal is to save time for teams by automating standup meetings effectively. Focus on creating a smooth, hassle-free experience that truly delivers on the promise of "from install to first meeting in under 60 seconds."