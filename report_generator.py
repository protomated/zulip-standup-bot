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
                ai_summary = self.ai_summary.generate_summary(standup['name'], responses)

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

    def format_report_message(self, report: Dict[str, Any]) -> str:
        """Format a report as a message to be sent in Zulip"""
        if "error" in report:
            return f"Error generating report: {report['error']}"

        message = f"# Standup Report: {report['standup_name']} - {report['date']}\n\n"

        # Participation stats
        message += f"**Participation:** {report['response_count']} out of {report['participant_count']} ({int(report['participation_rate'] * 100)}%)\n\n"

        # AI Summary
        if report['ai_summary']:
            message += f"## AI Summary\n\n{report['ai_summary']}\n\n"

        # Individual responses
        message += "## Individual Updates\n\n"
        if report['responses']:
            for user_id, data in report['responses'].items():
                message += f"### @_**User {user_id}**\n\n"
                for question, answer in data['responses'].items():
                    message += f"**{question}**\n{answer}\n\n"
        else:
            message += "No responses submitted for this standup."

        return message