# Standup Bot

A Zulip bot that helps teams run asynchronous standups in Zulip channels. The bot collects daily updates from team members via DM and posts AI-generated summaries to channels.

## Setup

To use the Standup Bot, you need to:

1. Create an "Outgoing webhook" bot in your Zulip organization settings
2. Deploy the bot using the Zulip Botserver
3. Configure the bot with required API keys (OpenAI)
4. Activate the bot in your team channel

### Configuration

The bot requires the following configuration:

- `openai_api_key`: Your OpenAI API key for generating summaries

You can set these in the bot configuration or as environment variables.

## Usage

### Activating Standup in a Channel

To activate standup in a channel, use the following command in the channel where you want to run standups:

```
/standup setup
```

This will activate standup with the default settings:
- Prompt time: 09:30 AM
- Cutoff time: 12:45 PM
- Reminder time: 11:45 AM
- Timezone: Africa/Lagos

To specify a custom prompt time, use:

```
/standup setup HH:MM
```

Where HH:MM is the time in 24-hour format (e.g., 14:30 for 2:30 PM).

### Setting Your Timezone

Each user can set their own timezone to receive prompts at the appropriate time:

```
/standup timezone Africa/Lagos
```

### Managing Standups

Pause standups (e.g., for holidays):

```
/standup pause
```

Resume standups:

```
/standup resume
```

Check the current status:

```
/standup status
```

### Configuring Standup Settings

Change the prompt time:

```
/standup config prompt_time 10:00
```

Change the cutoff time:

```
/standup config cutoff_time 13:00
```

Change the reminder time:

```
/standup config reminder_time 12:00
```

### Responding to Standup Prompts

The bot will send you a private message at the configured prompt time with the first question. Simply reply to the message with your answer, and the bot will ask the next question. After answering all three questions, the bot will confirm that your responses have been recorded.

## Features

### Core Standup Flow
- **Scheduled Prompts**: Sends daily standup prompts via DM at configured times (timezone-aware)
- **Private Collection**: Collects responses to 3 questions via DM:
  - What did you work on yesterday?
  - What are you planning to work on today?
  - Any blockers or issues?
- **Smart Reminders**: Sends reminder DMs to non-responders before cutoff
- **AI Summary**: Generates compiled summary using OpenAI at daily cutoff time
- **Public Posting**: Posts summary to channel with participant list and highlighted blockers with markdown formatting

### Multi-Timezone Support
- Uses individual timezones for each channel member
- Sends prompts and cutoffs based on individual timezones
- Configures channel-wide "summary posting time" in a reference timezone

### Admin Controls
- **Setup Command**: Activates standup for channel with time configuration
- **Pause/Resume**: Simple admin commands for holidays/breaks
- **Member Management**: Automatically detects channel members

### Configuration Options
- Set standup prompt time per user timezone
- Set daily cutoff time for response collection
- Configure reminder timing

## Notes

- The bot must be added to the channel before it can be activated
- The bot requires the "Outgoing webhook" type in Zulip settings
- All channel members will be included in the standup by default
- For the AI summary generation to work, an OpenAI API key must be provided
- If no OpenAI API key is available, the bot will fall back to a manual summary format
