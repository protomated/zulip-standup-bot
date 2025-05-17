# Zulip Standup Bot Development Guidelines

## Project Overview
A standup meeting automation bot for Zulip that enables asynchronous standups, collects responses, generates AI summaries, and provides detailed reports. Should be setup-ready in under 60 seconds.

## Key Features
1. **Fast Setup**: Simple commands to create standups quickly
2. **Multiple Teams Support**: Different standups for different teams/projects
3. **AI-Powered Summaries**: Generated using OpenAI API
4. **Asynchronous Workflows**: Same-timezone or local-timezone meetings
5. **Comprehensive Reports**: Detailed, well-formatted standup reports
6. **Flexible Scheduling**: With out-of-office awareness
7. **Historical Data**: Access to past standups and responses
8. **Activity Statistics**: Participation tracking
9. **Smart Reminders**: Automatic reminders

## Architecture Overview
Modular architecture with separation of concerns:
- Main bot handler
- Standup meeting management
- Persistent storage handling
- AI summary generation
- Message templates
- Report generation
- Scheduling and automation
- Reminder functionality

## Implementation Priorities
1. Project setup
2. Core bot structure
3. Storage system
4. Standup creation
5. Response collection
6. Report generation
7. Scheduling
8. Reminders
9. AI summaries
10. Analytics
11. Advanced features

## Code Style Guidelines
- Python 3.8+
- PEP 8 style guide
- Type hints
- Docstrings for all classes and methods
- snake_case for variables, functions, files
- PascalCase for classes
- Descriptive names
- Proper error handling and logging

## Docker and Deployment
- Use Docker for containerization
- CapRover for deployment
- Store config in environment variables
- CI/CD with GitHub Actions

## Storage Design
Use Zulip's bot storage system for persistence with this structure:
- Standups with IDs
- Team and schedule information
- Questions and participants
- Response data organized by date
- Historical data and analytics

## Command Interface
Core commands:
- `help`: Display help information
- `setup`: Interactive setup for a new standup
- `list`: List all standups
- `status [standup_id]`: Submit status
- `remind [standup_id]`: Send reminders
- `report [standup_id] [date]`: Generate report
- `cancel [standup_id]`: Cancel a standup
- `settings [standup_id]`: Adjust settings

## Standup Creation Flow
Interactive process:
1. User types `setup`
2. Bot asks for standup name
3. Bot asks for team stream
4. Bot asks for schedule
5. Bot asks for questions
6. Bot asks for participants
7. Bot confirms and creates

## AI Summary Generation
- Format standup data as a prompt
- Request structured summary
- Limit token usage
- Format AI response for readability

## Security and Performance
- No hardcoded API keys
- Input validation
- Cached storage to minimize API calls
- Efficient scheduling
- Resource management
- Graceful error handling

## Dependencies
- Use `uv` for dependency management
- Modern Python project structure with pyproject.toml

## Development Priorities
1. Reliability
2. Usability
3. Performance
4. Flexibility
5. Security
6. Docker containerization
7. Cloud-native deployment
