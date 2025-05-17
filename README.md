# Zulip Standup Bot

A comprehensive standup meeting automation bot for Zulip. This bot enables teams to conduct asynchronous standup meetings, collect responses, generate AI-powered summaries, and provide detailed reports.

## Features

- **Fast Setup**: Set up in under 60 seconds with minimal configuration
- **Multiple Teams Support**: Create different standups for different teams/projects
- **AI-Powered Summaries**: Automatically generate summaries using OpenAI
- **Asynchronous Workflows**: Support for same-timezone or local-timezone meetings
- **Comprehensive Reports**: Detailed, well-formatted standup reports
- **Flexible Scheduling**: Powerful scheduling options with out-of-office awareness
- **Historical Data**: Access to past standup meetings and responses
- **Activity Statistics**: Participation tracking and analytics
- **Smart Reminders**: Automatic reminders for participants

## Quick Start

### Using Docker (Recommended)

The easiest way to run the bot is using Docker:

```bash
# Pull the image
docker pull protomated/standup-bot:latest

# Run the container with PostgreSQL
docker run -d \
  -e ZULIP_EMAIL=your-bot@example.com \
  -e ZULIP_API_KEY=your_api_key \
  -e ZULIP_SITE=https://your-zulip-site.zulipchat.com \
  -e OPENAI_API_KEY=your_openai_api_key \
  -e DB_HOST=your-postgres-host \
  -e DB_NAME=your-postgres-db \
  -e DB_USER=your-postgres-user \
  -e DB_PASSWORD=your-postgres-password \
  --name standup-bot \
  protomated/standup-bot:latest
```

### Using Docker Compose (Recommended for Production)

For local development or production setups, use Docker Compose which includes a PostgreSQL database:

1. Clone this repository:
   ```bash
   git clone https://github.com/protomated/standup-bot.git
   cd standup-bot
   ```

2. Create a `.env` file with your configuration:
   ```
   ZULIP_EMAIL=your-bot@example.com
   ZULIP_API_KEY=your_api_key
   ZULIP_SITE=https://your-zulip-site.zulipchat.com
   OPENAI_API_KEY=your_openai_api_key

   # PostgreSQL configuration
   POSTGRES_DB=standup_bot
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_secure_password
   ```

3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

This will start both the bot and a PostgreSQL database container. The database data will be persisted in a Docker volume.

### Manual Installation

If you prefer to run without Docker:

1. Clone this repository:
   ```bash
   git clone https://github.com/protomated/standup-bot.git
   cd standup-bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   OR
   ```bash
   uv install
   ```

3. Set up a PostgreSQL database:
   - Install PostgreSQL if not already installed
   - Create a new database for the bot
   - Create a user with permissions to access the database
   - Note the connection details (host, port, database name, username, password)

4. Create a `zuliprc` file or set environment variables:
   ```
   [api]
   email=your-bot@example.com
   key=your_api_key
   site=https://your-zulip-site.zulipchat.com

   [database]
   host=localhost
   port=5432
   name=standup_bot
   user=postgres
   password=your_password
   ```

5. Run the bot:
   ```bash
   # Using zuliprc file
   python run_bot.py --config-file zuliprc

   # Using environment variables
   export ZULIP_EMAIL=your-bot@example.com
   export ZULIP_API_KEY=your_api_key
   export ZULIP_SITE=https://your-zulip-site.zulipchat.com
   export DB_HOST=localhost
   export DB_PORT=5432
   export DB_NAME=standup_bot
   export DB_USER=postgres
   export DB_PASSWORD=your_password
   python run_bot.py
   ```

   Note: If you don't configure PostgreSQL, the bot will fall back to using Zulip's built-in storage system.

## Deployment with CapRover

This bot can be easily deployed to a CapRover instance:

1. Set up a CapRover server if you don't have one already
2. Create a new app in CapRover
3. Set up a PostgreSQL database:
   - Either use CapRover's One-Click PostgreSQL app
   - Or use an external PostgreSQL service
4. Set the required environment variables in the CapRover dashboard:
   - `ZULIP_EMAIL`
   - `ZULIP_API_KEY`
   - `ZULIP_SITE`
   - `OPENAI_API_KEY` (optional)
   - `DB_HOST` (PostgreSQL hostname)
   - `DB_PORT` (PostgreSQL port, default: 5432)
   - `DB_NAME` (PostgreSQL database name)
   - `DB_USER` (PostgreSQL username)
   - `DB_PASSWORD` (PostgreSQL password)
5. Deploy using the CapRover CLI or GitHub Actions

For automated deployments with GitHub Actions, set the following secrets in your GitHub repository:
- `CAPROVER_SERVER`
- `CAPROVER_APP`
- `CAPROVER_TOKEN`

### Using CapRover's One-Click PostgreSQL

If you're using CapRover's One-Click PostgreSQL app:

1. Deploy the PostgreSQL app from the One-Click Apps section
2. Note the database credentials provided during setup
3. Use the app name (e.g., `srv-captain--postgres`) as the `DB_HOST` value
4. Set the other database environment variables according to the credentials you set up

## Bot Commands

Once the bot is running, you can interact with it using the following commands:

- `help` - Show help information
- `setup` - Set up a new standup meeting
- `list` - List all standups you're part of
- `status` - Submit your status for a standup
- `remind` - Send reminders to users who haven't submitted their status
- `report` - Generate a report for a standup
- `cancel` - Cancel a standup meeting
- `settings` - Change settings for a standup
- `timezone` - Set your timezone preference (e.g., `timezone America/New_York`)

## Timezone Support

The bot supports two modes of timezone handling for standup meetings:

### Same Timezone for All Participants

In this mode, all participants receive standup questions and submit their responses based on the same timezone. This is useful for teams that work in the same or similar timezones.

### Local Timezone Adaptation

In this mode, the bot adapts to each participant's local timezone. Participants receive standup questions at the scheduled time in their local timezone, allowing teams across different time zones to participate at a convenient time for them.

### Setting Up Timezone Preferences

1. When creating a new standup using the `setup` command, you'll be asked how timezones should be handled:
   ```
   How should timezones be handled?

   1. Same timezone for all participants
   2. Adapt to each participant's local timezone

   Please enter 1 or 2:
   ```

2. After selecting the timezone handling mode, you'll be asked to specify the base timezone for the standup:
   ```
   What timezone should be used for the standup? (e.g., UTC, America/New_York)
   ```

3. Individual users can set their timezone preference using the `timezone` command:
   ```
   timezone America/Los_Angeles
   ```

### How It Works

- In "same timezone" mode, all standup notifications are sent at the scheduled time in the specified timezone.
- In "local timezone" mode, the bot converts the standup time to each participant's local timezone and sends notifications accordingly.
- Standup reports include timezone information to provide context for the responses.
- The standup remains open long enough to accommodate all participants' timezones, ensuring everyone has a chance to respond.

## Configuration

The bot can be configured using environment variables or a `.zuliprc` file:

### Zulip and OpenAI Configuration

| Environment Variable | Description | Required |
|----------------------|-------------|----------|
| `ZULIP_EMAIL` | Bot email address | Yes |
| `ZULIP_API_KEY` | Bot API key | Yes |
| `ZULIP_SITE` | Zulip instance URL | Yes |
| `OPENAI_API_KEY` | OpenAI API key for AI summaries | No |

### PostgreSQL Database Configuration

The bot now uses PostgreSQL for data storage, providing better data consistency and modularity.

| Environment Variable | Description | Required for PostgreSQL |
|----------------------|-------------|------------------------|
| `DB_HOST` | PostgreSQL server hostname | Yes |
| `DB_PORT` | PostgreSQL server port | No (default: 5432) |
| `DB_NAME` | PostgreSQL database name | Yes |
| `DB_USER` | PostgreSQL username | Yes |
| `DB_PASSWORD` | PostgreSQL password | Yes |

If PostgreSQL configuration is not provided, the bot will fall back to using Zulip's built-in storage system.

## License

[MIT License](LICENSE)
