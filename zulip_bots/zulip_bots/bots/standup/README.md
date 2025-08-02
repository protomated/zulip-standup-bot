# Zulip Standup Bot

A production-ready bot for automating daily team standups in Zulip. Features automated scheduling, multi-timezone support, AI-powered summaries, and SQLite persistence.

## 🎯 Features

- **Automated Scheduling**: Daily prompts, reminders, and summaries
- **Multi-timezone Support**: Each user can set their own timezone
- **AI-Powered Summaries**: Uses Groq API for intelligent team summaries
- **SQLite Persistence**: Reliable data storage with automatic cleanup
- **Production Ready**: Error handling, logging, health checks
- **Easy Deployment**: Docker and CapRover support

## 🚀 Quick Start

### 1. Setup in Zulip Channel

```
/standup setup
```

This activates standup with default times (09:30 prompt, 11:45 reminder, 12:45 summary in UTC).

### 2. Customize Schedule

```
/standup setup 09:30 11:45 13:00
/standup config times 08:00 10:00 12:00
```

### 3. Set Personal Timezone

```
/standup timezone America/New_York
```

## 📋 Commands

### Setup Commands
- `/standup setup` - Activate with default times
- `/standup setup HH:MM` - Custom prompt time
- `/standup setup HH:MM HH:MM HH:MM` - Custom prompt, reminder, cutoff

### Management
- `/standup status` - Check configuration and next scheduled times
- `/standup pause` - Temporarily pause standups
- `/standup resume` - Resume paused standups
- `/standup timezone <tz>` - Set your timezone

### Configuration
- `/standup config prompt_time HH:MM` - When to send prompts
- `/standup config reminder_time HH:MM` - When to send reminders
- `/standup config cutoff_time HH:MM` - When to post summary
- `/standup config times HH:MM HH:MM HH:MM` - Set all at once

### Utilities
- `/standup history [days]` - View recent history
- `/standup search <term>` - Search past responses
- `/standup debug` - Show technical details
- `/standup test-prompt` - Send test prompt immediately

## 🔄 How It Works

1. **Setup**: When setting up standup, the bot automatically identifies human participants (excluding bots)
2. **Daily Prompt** (e.g., 09:30): Bot sends private messages asking "What did you work on yesterday?"
3. **Interactive Questions**: Users respond and get follow-up questions about today's plans and blockers
4. **Reminder** (e.g., 11:45): Non-responders get a friendly reminder
5. **Summary** (e.g., 12:45): AI-generated summary posted to the channel

### Smart Participant Detection
- Automatically excludes bots from standup participants
- Only includes human users in daily prompts and reminders
- Maintains accurate participant counts and statistics

## 🏗️ Architecture

### Database Schema
- **channels**: Stream configuration and settings
- **channel_participants**: Team members for each channel
- **standup_responses**: User responses with completion tracking
- **standup_prompts**: Daily prompt tracking and pending responses
- **users**: User preferences and timezones

### Scheduler
- APScheduler with cron triggers for precise timing
- Timezone-aware scheduling per channel
- Automatic job persistence and recovery
- Daily maintenance and cleanup

### AI Integration
- Groq API for fast, cost-effective summaries
- Fallback to manual summaries when AI unavailable
- Intelligent parsing of team responses

## 🔧 Configuration

### Environment Variables

**Required:**
```bash
ZULIP_EMAIL=standup-bot@your-zulip.com
ZULIP_API_KEY=your_api_key
ZULIP_SITE=https://your-zulip.com
```

**Optional:**
```bash
# AI Summaries
GROQ_API_KEY=gsk_your_groq_key
GROQ_MODEL=llama-3.1-8b-instant

# Database
SQLITE_DB_PATH=./data/standup.db

# Defaults
DEFAULT_TIMEZONE=Africa/Lagos
DEFAULT_PROMPT_TIME=09:30
DEFAULT_CUTOFF_TIME=12:45
DEFAULT_REMINDER_TIME=11:45
LOG_LEVEL=INFO
```

## 🐳 Deployment

### Local Development

1. Install dependencies:
```bash
./tools/provision
```

2. Set environment variables in `.env`

3. Run the bot:
```bash
python run_standup_bot.py
```

### Docker

```bash
# Build and run
docker-compose -f docker-compose.standup.yml up -d

# View logs
docker-compose -f docker-compose.standup.yml logs -f
```

### CapRover

1. Create a new app in CapRover
2. Set environment variables in the app settings
3. Deploy from Git repository
4. The `captain-definition` file will handle the build

## 🔍 Monitoring

### Health Check
The bot includes a health endpoint at `http://localhost:5002/health`

### Logging
- Structured logging with timestamps
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- Automatic log rotation in production

### Debug Tools
- `/standup debug` - Shows scheduler status and job details
- Database query logging
- Performance metrics for database operations

## 🛠️ Maintenance

### Automatic Cleanup
- Old standup data (>90 days) is automatically cleaned up
- Daily maintenance runs at 02:00 UTC
- Database optimization and job rescheduling

### Manual Cleanup
```python
import zulip_bots.bots.standup.database as db
db.cleanup_old_data(days_to_keep=30)
```

## 🔒 Security

- Non-root user in Docker containers
- SQL injection protection with parameterized queries
- Rate limiting and input validation
- Secure API key handling

## 📊 Performance

- SQLite with WAL mode for better concurrency
- Connection pooling for database efficiency
- Threaded job execution for non-blocking operations
- Optimized queries with proper indexing

## 🐛 Troubleshooting

### Bot Not Responding
1. Check `/standup debug` for scheduler status
2. Verify environment variables are set
3. Check database connectivity
4. Review logs for errors

### Prompts Not Sent
1. Verify channel is active: `/standup status`
2. Check timezone configuration
3. Ensure participants are added to channel
4. Use `/standup test-prompt` to test manually

### AI Summaries Not Working
1. Verify `GROQ_API_KEY` is set
2. Check API key has sufficient credits
3. Bot will fall back to manual summaries

### Database Issues
1. Check `SQLITE_DB_PATH` permissions
2. Ensure data directory exists and is writable
3. Database will auto-initialize on first run

## 📈 Performance Tuning

For large teams (50+ people):
- Consider increasing APScheduler thread pool size
- Monitor database performance and add indexes if needed
- Use log aggregation for better monitoring
- Consider database backups for critical data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
