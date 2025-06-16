Perfect! Here's your updated MVP feature list:

## MVP Feature List - Async Standup Bot

I want to implement the following:

### Core Standup Flow
- **Scheduled Prompts**: Send daily standup prompts via DM at configured times (timezone-aware), default is 09:30
- **Private Collection**: Collect responses to 3 questions via DM (if possible, use input UIs here):
  - What did you work on yesterday?
  - What are you planning to work on today?
  - Any blockers or issues?
- **Smart Reminders**: Send reminder DMs to non-responders before cutoff
- **AI Summary**: Generate compiled summary using OpenAI at daily cutoff time (default is 12:45)
- **Public Posting**: Post summary to channel with participant list and highlighted blockers with markdown formating

### Multi-Timezone Support
- Use the detected timezones of each channel member
- Send prompts and cutoffs based on individual timezones
- Configure channel-wide "summary posting time" in a reference timezone (default is Africa/Lagos)

### Admin Controls
- **Setup Command**: Activate standup for channel with time configuration
- **Pause/Resume**: Simple admin commands for holidays/breaks
- **Member Management**: Automatically detect channel members, with manual override options

### Configuration Options
- Set standup prompt time per user timezone
- Set daily cutoff time for response collection
- Configure reminder timing (e.g., 1 hour before cutoff)

