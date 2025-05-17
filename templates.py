class Templates:
    """
    Contains templates for various messages sent by the bot
    """

    def welcome_message(self) -> str:
        """Welcome message when the bot is first added"""
        return """
# Welcome to StandupBot! 👋

I'm here to help you run efficient standup meetings with your team. Let's get started!

## Quick Setup
To set up your first standup meeting, just type:
```
setup
```

I'll guide you through a simple process to create your first standup in under 60 seconds.

## Need Help?
Type `help` anytime to see what I can do.
"""

    def setup_intro(self) -> str:
        """Introduction message for the setup process"""
        return """
# Let's set up your standup meeting! 🚀

I'll ask you a few quick questions to get your standup configured.
You can type `cancel` at any time to abort the setup process.

Let's start with the basics:
"""

    def setup_name_prompt(self) -> str:
        """Prompt for standup name"""
        return "**What would you like to name this standup?** (e.g., 'Engineering Team Standup')"

    def setup_stream_prompt(self) -> str:
        """Prompt for team stream"""
        return "**Which stream should I post standup reports to?** (e.g., 'engineering')"

    def setup_days_prompt(self) -> str:
        """Prompt for standup days"""
        return """
**Which days should this standup run?** 
Type the numbers for each day:
1. Monday
2. Tuesday
3. Wednesday
4. Thursday
5. Friday
6. Saturday
7. Sunday

Example: `1,3,5` for Monday, Wednesday, Friday
Default: `1,2,3,4,5` (weekdays)
"""

    def setup_time_prompt(self) -> str:
        """Prompt for standup time"""
        return """
**What time should the standup start?** (24-hour format)
Example: `09:00` for 9:00 AM
Default: `09:00`
"""

    def setup_questions_prompt(self) -> str:
        """Prompt for standup questions"""
        return """
**What questions would you like to ask in the standup?**
Enter one question per line, or type `default` to use the standard questions:
1. What did you accomplish yesterday?
2. What are you working on today?
3. Any blockers or challenges?

Example:
```
What did you accomplish yesterday?
What are you working on today?
Any blockers or challenges?
```
"""

    def setup_participants_prompt(self) -> str:
        """Prompt for standup participants"""
        return """
**Who should participate in this standup?**
Tag users with @mentions, separated by commas.
Example: `@alice, @bob, @charlie`

Or type `all` to include everyone in the stream.
"""

    def setup_confirmation(self, name: str, stream: str, days: str, time: str,
                          questions: list, participants: str) -> str:
        """Confirmation message with standup details"""
        questions_formatted = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])

        return f"""
# Standup Configuration Summary

Here's what I've got for your standup:

**Name:** {name}
**Stream:** #{stream}
**Schedule:** {days} at {time}
**Questions:**
{questions_formatted}
**Participants:** {participants}

Does this look correct? Type `yes` to create the standup or `no` to start over.
"""

    def setup_success(self, standup_id: int, name: str) -> str:
        """Success message after standup creation"""
        return f"""
# 🎉 Standup Created Successfully!

Your standup **{name}** has been set up (ID: {standup_id}).

The first standup will run at the scheduled time. Participants will receive a direct message with the standup questions.

## What's Next?
- Type `list` to see all your standups
- Type `settings {standup_id}` to modify this standup
- Type `help` to see all available commands

Thank you for using StandupBot!
"""

    def setup_cancelled(self) -> str:
        """Message when setup is cancelled"""
        return "Setup cancelled. Type `setup` anytime to start again."

    def default_questions(self) -> list:
        """Default questions for standups"""
        return [
            "What did you accomplish yesterday?",
            "What are you working on today?",
            "Any blockers or challenges?"
        ]

    def help_message(self) -> str:
        """Detailed help message"""
        return """
# StandupBot Help Guide

## Basic Commands
- `help` - Show this help message
- `setup` - Set up a new standup meeting
- `list` - List all standups you're part of
- `switch [standup_id]` - Set your active standup
- `status [standup_id]` - Submit your status for a standup
- `remind [standup_id]` - Send reminders to users who haven't submitted their status
- `report [standup_id] [date] [format] [email]` - Generate a report for a standup
- `report settings` - Manage your report preferences
- `cancel [standup_id]` - Cancel a standup meeting
- `settings [standup_id]` - Change settings for a standup
- `permissions [standup_id] [action] [parameters]` - Manage standup permissions

## Multiple Standups
You can be part of multiple standups for different teams or projects:
- Use `list` to see all your standups
- Filter standups with `list team:TEAM` or `list project:PROJECT`
- Set your active standup with `switch [standup_id]`
- Use `status` without an ID to submit for your active standup

## Report Generation
Generate well-formatted reports for your standups:
- `report [standup_id]` - Generate a report for today
- `report [standup_id] YYYY-MM-DD` - Generate a report for a specific date
- `report [standup_id] [date] [format]` - Generate a report in a specific format
- `report [standup_id] [date] [format] [email]` - Send the report to an email address

### Report Formats
- `standard` - Basic report with participation stats and individual updates
- `detailed` - Comprehensive report with more detailed information
- `summary` - Concise report focusing on the AI summary
- `compact` - Minimal report with just the essential information

### Report Settings
Customize your report preferences:
- `report settings` - View your current report settings
- `report settings format [standard|detailed|summary|compact]` - Set default format
- `report settings email [on|off]` - Enable/disable automatic email reports
- `report settings set-email [email]` - Set your default email address

## Permissions Management
Manage who can access and modify standups:
- `permissions [standup_id] add-admin @user` - Add an admin
- `permissions [standup_id] remove-admin @user` - Remove an admin
- `permissions [standup_id] set-edit [admin|participants|all]` - Set who can edit
- `permissions [standup_id] set-view [admin|participants|all]` - Set who can view

## Setup Process
The `setup` command will guide you through creating a new standup with:
1. A name for your standup
2. The stream where reports will be posted
3. Schedule (days and time)
4. Questions to ask participants
5. List of participants
6. Team and project tags (optional)

## Submitting Status
When it's time for a standup, I'll send you a direct message with questions.
You can also manually submit your status with:
```
status [standup_id]
```
Or just `status` if you have an active standup set.

## Need more help?
Contact your administrator or visit our documentation.
"""

    def error_message(self, error: str) -> str:
        """Generic error message"""
        return f"""
⚠️ **Error**

{error}

Type `help` for assistance.
"""
