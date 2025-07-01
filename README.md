# Zulip Standup Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

A production-ready bot that automates daily team standups in Zulip. Features automated scheduling, AI-powered summaries, multi-timezone support, and robust database persistence.

## 📑 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
  - [Prerequisites](#1-prerequisites)
  - [Create Bot Account](#2-create-bot-account)
  - [Installation Options](#3-installation-options)
  - [Configuration](#4-configuration)
  - [Setup in Zulip](#5-setup-in-zulip)
- [📋 Commands Reference](#-commands-reference)
- [🔄 How It Works](#-how-it-works)
- [🏗️ Architecture](#️-architecture)
- [🐳 Deployment](#-deployment)
- [⚙️ Configuration Reference](#️-configuration-reference)
- [🔧 Customization](#-customization)
- [📊 Monitoring & Maintenance](#-monitoring--maintenance)
- [🐛 Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🙏 Acknowledgments](#-acknowledgments)
- [📞 Support](#-support)

## ✨ Features

- 🕐 **Automated Scheduling**: Daily prompts, reminders, and summaries with precise timing
- 🌍 **Multi-timezone Support**: Each team member can set their own timezone
- 🤖 **AI-Powered Summaries**: Intelligent team summaries using OpenAI GPT or Groq
- 💾 **PostgreSQL/SQLite Support**: Reliable data storage with connection pooling
- 🛡️ **Production Ready**: Comprehensive error handling, logging, and monitoring
- 🐳 **Easy Deployment**: Docker, Docker Compose, and CapRover support
- 🔄 **Interactive Workflow**: Three-step questionnaire for comprehensive updates
- 📊 **Rich Analytics**: Search history, view trends, and track participation

## 🚀 Quick Start

### 1. Prerequisites

- **Zulip Server**: A running Zulip instance with admin access
- **Bot Account**: Create a bot account in your Zulip organization
- **Python 3.8+** or **Docker**

### 2. Create Bot Account

1. Go to your Zulip organization settings
2. Navigate to "Bots" section
3. Add a new bot:
   - **Name**: Standup Bot
   - **Username**: standup-bot
   - **Bot type**: Generic bot
4. Download the bot's configuration file (`.zuliprc`)

### 3. Installation Options

#### Option A: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/protomated/zulip-standup-bot.git
cd zulip-standup-bot

# Copy environment configuration
cp .env.example .env

# Edit .env with your configuration
nano .env

# Run with Docker Compose
docker-compose up -d
```

#### Option B: Local Development

```bash
# Clone repository
git clone https://github.com/protomated/zulip-standup-bot.git
cd zulip-standup-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the bot
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the bot
python run_standup_bot.py
```

### 4. Configuration

Edit your `.env` file with the following required settings:

```bash
# Zulip Configuration (Required)
ZULIP_EMAIL=standup-bot@your-zulip.com
ZULIP_API_KEY=your_api_key_here
ZULIP_SITE=https://your-zulip.com

# AI Configuration (Optional - for smart summaries)
OPENAI_API_KEY=sk-your_openai_key  # Or use Groq
GROQ_API_KEY=gsk_your_groq_key     # Alternative to OpenAI

# Database (Optional - defaults to SQLite)
DATABASE_URL=postgresql://user:pass@localhost/standup

# Bot Behavior (Optional - has sensible defaults)
DEFAULT_TIMEZONE=America/New_York
DEFAULT_PROMPT_TIME=09:30
DEFAULT_REMINDER_TIME=11:45
DEFAULT_CUTOFF_TIME=12:45
LOG_LEVEL=INFO
```

### 5. Setup in Zulip

1. Add the bot to your team channel
2. Send the setup command:

```
@standup-bot /standup setup
```

The bot will automatically:
- Configure daily standups with default times
- Add all human channel members as participants
- Schedule the first standup for the next business day

## 📋 Commands Reference

### Setup & Configuration

| Command | Description |
|---------|-------------|
| `/standup setup` | Activate standup with default times (9:30 AM prompt, 11:45 AM reminder, 12:45 PM summary) |
| `/standup setup HH:MM` | Set custom prompt time only |
| `/standup setup HH:MM HH:MM HH:MM` | Set prompt, reminder, and cutoff times |
| `/standup config prompt_time HH:MM` | Change when daily prompts are sent |
| `/standup config reminder_time HH:MM` | Change when reminders are sent |
| `/standup config cutoff_time HH:MM` | Change when summaries are posted |
| `/standup config timezone <tz>` | Set channel timezone (e.g., America/New_York) |

### Personal Settings

| Command | Description |
|---------|-------------|
| `/standup timezone <tz>` | Set your personal timezone |
| `/standup timezone` | View your current timezone |

### Management

| Command | Description |
|---------|-------------|
| `/standup status` | View configuration and next scheduled events |
| `/standup pause` | Temporarily pause standups for this channel |
| `/standup resume` | Resume paused standups |
| `/standup participants` | View and manage team participants |
| `/standup test-prompt` | Send a test prompt immediately |

### History & Analytics

| Command | Description |
|---------|-------------|
| `/standup history [days]` | View recent standup history (default: 7 days) |
| `/standup search <term>` | Search past standup responses |
| `/standup stats` | View participation statistics |

### Debug & Support

| Command | Description |
|---------|-------------|
| `/standup debug` | Show technical details and scheduler status |
| `/standup help` | Show command help |

## 🔄 How It Works

### Daily Workflow

1. **Morning Prompt** (e.g., 9:30 AM)
   - Bot sends private messages to all participants
   - Asks: "What did you work on yesterday?"

2. **Interactive Questionnaire**
   - After first response: "What are you planning to work on today?"
   - After second response: "Any blockers or issues?"
   - After third response: Thanks user and marks complete

3. **Reminder** (e.g., 11:45 AM)
   - Friendly reminder sent to non-responders
   - Includes quick action buttons for easy participation

4. **Summary** (e.g., 12:45 PM)
   - AI-generated summary posted to channel
   - Includes participation stats and key highlights
   - Falls back to manual summary if AI unavailable

### Smart Features

- **Timezone Intelligence**: Each user's prompts arrive at their local time
- **Weekend Detection**: Automatically skips weekends and holidays
- **Participant Management**: Automatically excludes bots and inactive users
- **Graceful Degradation**: Works without AI, database, or network issues

## 🏗️ Architecture

### Components

- **Main Bot Handler** (`standup.py`): Core bot logic and command routing
- **Database Layer** (`database.py`): PostgreSQL/SQLite operations with pooling
- **Scheduler** (`APScheduler`): Timezone-aware job scheduling
- **AI Integration** (`ai_summary.py`): OpenAI/Groq integration for summaries
- **Configuration** (`config.py`): Environment and default settings

### Database Schema

The bot uses a PostgreSQL or SQLite database with the following tables:

- **users**: User preferences and timezone settings
- **channels**: Channel configuration and scheduling
- **channel_participants**: Team membership tracking
- **standup_responses**: Daily response storage with JSONB
- **standup_prompts**: Prompt tracking and pending responses

### Dual Storage Strategy

- **Primary**: Database storage for persistence and reliability
- **Fallback**: In-memory storage for temporary operation
- **Automatic**: Switches based on database availability

## 🐳 Deployment

### Docker Compose (Recommended)

```yaml
version: '3.8'
services:
  standup-bot:
    build: .
    environment:
      - ZULIP_EMAIL=standup-bot@your-zulip.com
      - ZULIP_API_KEY=your_api_key
      - ZULIP_SITE=https://your-zulip.com
      - DATABASE_URL=postgresql://user:pass@db:5432/standup
    depends_on:
      - db
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=standup
      - POSTGRES_USER=standup_user
      - POSTGRES_PASSWORD=your_secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### CapRover Deployment

1. Fork this repository
2. Create a new CapRover app
3. Connect your Git repository
4. Set environment variables in app settings
5. Deploy using the included `captain-definition`

### Manual Deployment

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3 python3-pip postgresql

# Clone and setup
git clone https://github.com/protomated/zulip-standup-bot.git
cd zulip-standup-bot
pip3 install -r requirements.txt

# Configure systemd service
sudo cp standup-bot.service /etc/systemd/system/
sudo systemctl enable standup-bot
sudo systemctl start standup-bot
```

## ⚙️ Configuration Reference

### Environment Variables

#### Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `ZULIP_EMAIL` | Bot's email address | `standup-bot@company.zulipchat.com` |
| `ZULIP_API_KEY` | Bot's API key from Zulip | `abcd1234...` |
| `ZULIP_SITE` | Zulip server URL | `https://company.zulipchat.com` |

#### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | None | OpenAI API key for AI summaries |
| `GROQ_API_KEY` | None | Groq API key (alternative to OpenAI) |
| `DATABASE_URL` | SQLite file | PostgreSQL connection string |
| `DEFAULT_TIMEZONE` | `Africa/Lagos` | Default timezone for new channels |
| `DEFAULT_PROMPT_TIME` | `09:30` | Default time to send prompts |
| `DEFAULT_REMINDER_TIME` | `11:45` | Default time to send reminders |
| `DEFAULT_CUTOFF_TIME` | `12:45` | Default time to post summaries |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Advanced Configuration

#### Database Settings

```bash
# PostgreSQL (recommended for production)
DATABASE_URL=postgresql://user:password@localhost:5432/standup

# SQLite (good for development)
DATABASE_URL=sqlite:///./data/standup.db
```

#### AI Provider Settings

```bash
# OpenAI (more accurate, higher cost)
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo

# Groq (faster, lower cost)
GROQ_API_KEY=gsk-your-key-here
GROQ_MODEL=llama-3.1-8b-instant
```

## 🔧 Customization

### Custom AI Providers

To add support for other AI providers, extend the `ai_summary.py` module:

```python
class CustomAIProvider:
    def generate_summary(self, responses):
        # Your implementation here
        return summary_text
```

### Custom Questions

Modify the questions in `standup.py`:

```python
STANDUP_QUESTIONS = [
    "What did you accomplish yesterday?",
    "What are your goals for today?",
    "What challenges are you facing?"
]
```

### Custom Time Zones

The bot supports all standard timezone names. Common examples:

- `America/New_York` (Eastern Time)
- `America/Chicago` (Central Time)
- `America/Denver` (Mountain Time)
- `America/Los_Angeles` (Pacific Time)
- `Europe/London` (GMT/BST)
- `Europe/Berlin` (CET/CEST)
- `Asia/Tokyo` (JST)

## 📊 Monitoring & Maintenance

### Health Checks

The bot includes built-in health monitoring:

```bash
# Check bot status
curl http://localhost:5002/health

# View metrics
curl http://localhost:5002/metrics
```

### Logging

Logs are structured and include:

- Timestamp and log level
- Component and operation context
- Performance metrics
- Error details and stack traces

### Database Maintenance

The bot automatically:

- Cleans up old data (>90 days)
- Optimizes database performance
- Manages connection pooling
- Handles schema migrations

### Backup Strategy

For production deployments:

```bash
# PostgreSQL backup
pg_dump standup > backup_$(date +%Y%m%d).sql

# SQLite backup
cp data/standup.db backup_$(date +%Y%m%d).db
```

## 🐛 Troubleshooting

### Common Issues

#### Bot Not Responding

1. **Check Status**: Use `/standup debug` to see scheduler status
2. **Verify Configuration**: Ensure all environment variables are set
3. **Check Logs**: Look for error messages in application logs
4. **Test Connection**: Verify bot can connect to Zulip

#### Prompts Not Being Sent

1. **Verify Setup**: Check `/standup status` shows active configuration
2. **Check Timezone**: Ensure timezone settings are correct
3. **Verify Participants**: Confirm users are added to channel
4. **Test Manually**: Use `/standup test-prompt` to test immediately

#### AI Summaries Not Working

1. **Check API Key**: Verify `OPENAI_API_KEY` or `GROQ_API_KEY` is set
2. **Check Credits**: Ensure API account has sufficient credits
3. **Review Logs**: Look for API error messages
4. **Fallback Mode**: Bot continues with manual summaries

#### Database Connection Issues

1. **Check URL**: Verify `DATABASE_URL` format is correct
2. **Check Permissions**: Ensure database user has required permissions
3. **Test Connection**: Use database client to verify connectivity
4. **Fallback Mode**: Bot switches to in-memory storage automatically

### Debug Commands

```bash
# Show detailed status
/standup debug

# Test immediate prompt
/standup test-prompt

# Check configuration
/standup status

# View recent activity
/standup history 1
```

### Performance Tuning

For large teams (50+ members):

1. **Database Optimization**:
   - Use PostgreSQL instead of SQLite
   - Enable connection pooling
   - Add database indexes

2. **Scheduler Tuning**:
   - Increase APScheduler thread pool size
   - Optimize job execution intervals

3. **Monitoring**:
   - Enable detailed logging
   - Set up metrics collection
   - Monitor database performance

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

### Development Setup

```bash
# Fork and clone
git clone https://github.com/protomated/zulip-standup-bot.git
cd zulip-standup-bot

# Setup development environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Run tests
python -m pytest

# Code formatting
python -m black .
python -m isort .
```

### Code Style

- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **pytest** for testing

### Submitting Changes

1. Create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on the [Zulip Bot Framework](https://zulip.com/api/bots-guide)
- Powered by [APScheduler](https://apscheduler.readthedocs.io/) for reliable scheduling
- AI summaries by [OpenAI](https://openai.com/) and [Groq](https://groq.com/)
- Database support via [PostgreSQL](https://postgresql.org/) and [SQLite](https://sqlite.org/)

## 📞 Support

- **Documentation**: [Full documentation](https://github.com/protomated/zulip-standup-bot/wiki)
- **Issues**: [GitHub Issues](https://github.com/protomated/zulip-standup-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/protomated/zulip-standup-bot/discussions)

---

**Made with ❤️ for distributed teams everywhere by Protomated**
