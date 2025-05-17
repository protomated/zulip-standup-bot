from typing import Dict, Any, List
import datetime
from storage_manager import StorageManager
from ai_summary import AISummaryGenerator


class ReportGenerator:
    """
    Generates reports for standup meetings
    """

    def __init__(self, storage_manager: StorageManager, ai_summary_generator: AISummaryGenerator):
        self.storage = storage_manager
        self.ai_summary = ai_summary_generator

    def generate_report(self, standup_id: int, date: str = None) -> Dict[str, Any]:
        """
        Generate a report for a standup meeting

        Args:
            standup_id: ID of the standup
            date: Date to generate report for (defaults to today)

        Returns:
            Report dictionary
        """
        # Get the date to report on
        if not date:
            date = datetime.datetime.now().strftime('%Y-%m-%d')

        # Get the standup
        with self.storage.use_storage(['standups']) as cache:
            standups = cache.get('standups') or {}
            if str(standup_id) not in standups:
                return {"error": "Standup not found"}

            standup = standups[str(standup_id)]

            # Get responses for the date
            responses = standup['responses'].get(date, {})

            # Generate basic stats
            participant_count = len(standup['participants'])
            response_count = len(responses)
            participation_rate = response_count / participant_count if participant_count > 0 else 0

            # Generate AI summary if responses exist
            ai_summary = ""
            if responses:
                ai_summary = self.ai_summary.generate_summary(
                    standup['name'],
                    responses,
                    standup_id=str(standup_id),
                    date=date
                )

            # Create and return the report
            report = {
                "standup_id": standup_id,
                "standup_name": standup['name'],
                "date": date,
                "participant_count": participant_count,
                "response_count": response_count,
                "participation_rate": participation_rate,
                "responses": responses,
                "ai_summary": ai_summary,
                "generated_at": datetime.datetime.now().isoformat()
            }

            # Store the report in history
            standup['history'].append({
                "date": date,
                "participation_rate": participation_rate,
                "ai_summary": ai_summary
            })

            cache.put('standups', standups)

            return report

    def format_report_message(self, report: Dict[str, Any], report_format: str = 'standard') -> str:
        """
        Format a report as a message to be sent in Zulip with improved formatting

        Args:
            report: The report data dictionary
            report_format: The format to use ('standard', 'detailed', 'summary', 'compact')

        Returns:
            Formatted report message
        """
        if "error" in report:
            return f"Error generating report: {report['error']}"

        # Choose the appropriate formatting function based on the format
        if report_format == 'detailed':
            return self._format_detailed_report(report)
        elif report_format == 'summary':
            return self._format_summary_report(report)
        elif report_format == 'compact':
            return self._format_compact_report(report)
        else:
            # Default to standard format
            return self._format_standard_report(report)

    def _format_standard_report(self, report: Dict[str, Any]) -> str:
        """Format a report using the standard template"""
        message = f"# Standup Report: {report['standup_name']} - {report['date']}\n\n"

        # Participation stats with visual indicator
        participation_percent = int(report['participation_rate'] * 100)
        participation_indicator = "🟢" if participation_percent >= 75 else "🟡" if participation_percent >= 50 else "🔴"
        message += f"{participation_indicator} **Participation:** {report['response_count']} out of {report['participant_count']} ({participation_percent}%)\n\n"

        # AI Summary with clear separation
        if report['ai_summary']:
            # Check if the summary already has section headers
            has_sections = any(line.startswith('##') for line in report['ai_summary'].split('\n'))

            if has_sections:
                # If the summary already has section headers, just add it directly
                message += f"## AI Summary\n\n{report['ai_summary']}\n\n"
            else:
                # If the summary doesn't have section headers, add a simple wrapper
                message += f"## AI Summary\n\n{report['ai_summary']}\n\n"

            # Add a separator between AI summary and individual updates
            message += "---\n\n"

        # Individual responses with collapsible sections
        message += "## Individual Updates\n\n"
        if report['responses']:
            # Sort responses by user ID for consistent ordering
            sorted_responses = sorted(report['responses'].items(), key=lambda x: x[0])

            for user_id, data in sorted_responses:
                # Format timestamp if available
                timestamp_str = ""
                if 'timestamp' in data:
                    try:
                        # Try to parse and format the timestamp
                        timestamp = datetime.datetime.fromisoformat(data['timestamp'])
                        timestamp_str = f" (submitted at {timestamp.strftime('%H:%M')})"
                    except (ValueError, TypeError):
                        # If parsing fails, use the raw timestamp
                        timestamp_str = f" (submitted at {data['timestamp']})"

                message += f"### @_**User {user_id}**{timestamp_str}\n\n"

                # Format responses with better visual separation
                for question, answer in data['responses'].items():
                    message += f"**{question}**\n{answer}\n\n"
        else:
            message += "No responses submitted for this standup."

        # Add footer with generation timestamp
        message += f"\n\n*Report generated at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"

        return message

    def _format_detailed_report(self, report: Dict[str, Any]) -> str:
        """Format a report using the detailed template with more comprehensive information"""
        message = f"# 📊 Detailed Standup Report\n\n"
        message += f"## {report['standup_name']} - {report['date']}\n\n"

        # Standup metadata section
        message += "### 📋 Standup Information\n\n"
        message += f"**Date:** {report['date']}\n"
        message += f"**Generated at:** {report['generated_at']}\n"

        # Participation statistics with visual indicators and more details
        participation_percent = int(report['participation_rate'] * 100)
        participation_indicator = "🟢" if participation_percent >= 75 else "🟡" if participation_percent >= 50 else "🔴"
        message += f"\n### {participation_indicator} Participation Statistics\n\n"
        message += f"**Response Rate:** {participation_percent}%\n"
        message += f"**Responses Received:** {report['response_count']} out of {report['participant_count']}\n"

        # Missing participants (if any)
        if report['participant_count'] > report['response_count']:
            missing_count = report['participant_count'] - report['response_count']
            message += f"**Missing Responses:** {missing_count}\n"

            # Get list of missing participants if available
            missing_participants = self.storage.get_missing_responses(str(report['standup_id']), report['date'])
            if missing_participants:
                message += "\n**Missing Participants:**\n"
                for user_id in missing_participants:
                    message += f"- User {user_id}\n"

        # AI Summary section with enhanced formatting
        if report['ai_summary']:
            message += f"\n### 🤖 AI-Generated Summary\n\n"

            # Check if the summary already has section headers
            has_sections = any(line.startswith('##') for line in report['ai_summary'].split('\n'))

            if has_sections:
                # If the summary already has section headers, just add it directly
                message += f"{report['ai_summary']}\n\n"
            else:
                # If the summary doesn't have section headers, add a simple wrapper
                message += f"{report['ai_summary']}\n\n"

        # Individual responses with more detailed formatting
        message += "\n### 👥 Individual Updates\n\n"
        if report['responses']:
            # Sort responses by user ID for consistent ordering
            sorted_responses = sorted(report['responses'].items(), key=lambda x: x[0])

            for user_id, data in sorted_responses:
                # Format timestamp if available
                timestamp_str = ""
                if 'timestamp' in data:
                    try:
                        # Try to parse and format the timestamp
                        timestamp = datetime.datetime.fromisoformat(data['timestamp'])
                        timestamp_str = f" (submitted at {timestamp.strftime('%H:%M')})"
                    except (ValueError, TypeError):
                        # If parsing fails, use the raw timestamp
                        timestamp_str = f" (submitted at {data['timestamp']})"

                message += f"#### @_**User {user_id}**{timestamp_str}\n\n"

                # Format responses with better visual separation and numbering
                for i, (question, answer) in enumerate(data['responses'].items(), 1):
                    message += f"**Q{i}: {question}**\n{answer}\n\n"
        else:
            message += "No responses submitted for this standup.\n"

        # Add footer with additional information
        message += "\n---\n"
        message += f"*This detailed report was generated for {report['standup_name']} on {report['date']}*\n"
        message += "*To customize report formats, use the `report [standup_id] [date] [format]` command*"

        return message

    def _format_summary_report(self, report: Dict[str, Any]) -> str:
        """Format a report using the summary template focusing on the AI summary"""
        message = f"# 📝 Standup Summary: {report['standup_name']}\n\n"
        message += f"**Date:** {report['date']}\n\n"

        # Participation stats with visual indicator
        participation_percent = int(report['participation_rate'] * 100)
        participation_indicator = "🟢" if participation_percent >= 75 else "🟡" if participation_percent >= 50 else "🔴"
        message += f"{participation_indicator} **Participation:** {report['response_count']} out of {report['participant_count']} ({participation_percent}%)\n\n"

        # AI Summary as the main focus
        if report['ai_summary']:
            message += f"## Summary\n\n{report['ai_summary']}\n\n"
        else:
            message += "## Summary\n\nNo AI summary available for this standup.\n\n"

        # Add a note about viewing the full report
        message += "\n---\n"
        message += "*This is a summary report. For full details, use `report " + str(report['standup_id']) + " " + report['date'] + " detailed`*\n"
        message += f"*Report generated at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"

        return message

    def _format_compact_report(self, report: Dict[str, Any]) -> str:
        """Format a report using the compact template for quick overview"""
        message = f"# Standup: {report['standup_name']} - {report['date']}\n\n"

        # Participation stats
        participation_percent = int(report['participation_rate'] * 100)
        participation_indicator = "🟢" if participation_percent >= 75 else "🟡" if participation_percent >= 50 else "🔴"
        message += f"{participation_indicator} **{participation_percent}%** participation ({report['response_count']}/{report['participant_count']})\n\n"

        # Compact AI Summary
        if report['ai_summary']:
            # Extract just the first paragraph of the summary
            first_paragraph = report['ai_summary'].split('\n\n')[0]
            message += f"**Summary:** {first_paragraph}\n\n"

            # Add a note that this is truncated
            message += "*Summary truncated. View full report for details.*\n\n"

        # List of participants who responded
        if report['responses']:
            message += "**Participants:** "
            user_ids = sorted(report['responses'].keys())
            message += ", ".join([f"User {user_id}" for user_id in user_ids])
            message += "\n\n"

        # Add a note about viewing the full report
        message += "\n---\n"
        message += f"*Compact report generated at {datetime.datetime.now().strftime('%H:%M')}*"

        return message
