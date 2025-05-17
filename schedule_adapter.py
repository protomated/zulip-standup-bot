"""
Adapter for converting between legacy schedule formats and the new SchedulePattern format.
Provides compatibility with existing storage schema while enabling new scheduling features.
"""

from typing import Dict, Any, Optional, List
from schedule_engine import SchedulePattern, HolidayCalendar, CalendarIntegration, ScheduleConflictDetector


class ScheduleAdapter:
    """
    Adapter for converting between legacy schedule formats and the new SchedulePattern format.
    """

    @staticmethod
    def legacy_to_pattern(legacy_schedule: Dict[str, Any]) -> SchedulePattern:
        """
        Convert a legacy schedule format to a SchedulePattern.

        Legacy format example:
        {
            'days': ['monday', 'wednesday', 'friday'],
            'time': '09:00',
            'timezone': 'UTC',
            'duration': 86400  # 24 hours in seconds
        }

        Args:
            legacy_schedule: Legacy schedule dictionary

        Returns:
            SchedulePattern object
        """
        # Check if the legacy schedule has a pattern_type field
        if 'pattern_type' in legacy_schedule:
            # This is already a new format schedule
            return SchedulePattern.from_dict(legacy_schedule)

        # Convert legacy format to SchedulePattern
        return SchedulePattern.from_legacy_schedule(legacy_schedule)

    @staticmethod
    def pattern_to_storage(pattern: SchedulePattern, duration: int = 86400) -> Dict[str, Any]:
        """
        Convert a SchedulePattern to a format suitable for storage.

        Args:
            pattern: SchedulePattern object
            duration: Duration of the standup in seconds (default: 24 hours)

        Returns:
            Dictionary suitable for storage
        """
        # Convert pattern to dictionary
        pattern_dict = pattern.to_dict()

        # Add duration
        pattern_dict['duration'] = duration

        return pattern_dict

    @staticmethod
    def create_daily_pattern(time: str, timezone: str = 'UTC',
                            interval: int = 1, exclusions: List[str] = None) -> SchedulePattern:
        """
        Create a daily schedule pattern.

        Args:
            time: Time in HH:MM format
            timezone: Timezone string
            interval: Interval in days (default: 1)
            exclusions: List of dates to exclude (YYYY-MM-DD format)

        Returns:
            SchedulePattern object
        """
        return SchedulePattern(
            SchedulePattern.DAILY,
            time=time,
            timezone=timezone,
            interval=interval,
            exclusions=exclusions or []
        )

    @staticmethod
    def create_weekly_pattern(days: List[str], time: str, timezone: str = 'UTC',
                             interval: int = 1, exclusions: List[str] = None) -> SchedulePattern:
        """
        Create a weekly schedule pattern.

        Args:
            days: List of days of the week (e.g., ['monday', 'wednesday', 'friday'])
            time: Time in HH:MM format
            timezone: Timezone string
            interval: Interval in weeks (default: 1)
            exclusions: List of dates to exclude (YYYY-MM-DD format)

        Returns:
            SchedulePattern object
        """
        return SchedulePattern(
            SchedulePattern.WEEKLY,
            days=days,
            time=time,
            timezone=timezone,
            interval=interval,
            exclusions=exclusions or []
        )

    @staticmethod
    def create_monthly_pattern(day: int, time: str, timezone: str = 'UTC',
                              interval: int = 1, exclusions: List[str] = None) -> SchedulePattern:
        """
        Create a monthly schedule pattern with a specific day of the month.

        Args:
            day: Day of the month (1-31)
            time: Time in HH:MM format
            timezone: Timezone string
            interval: Interval in months (default: 1)
            exclusions: List of dates to exclude (YYYY-MM-DD format)

        Returns:
            SchedulePattern object
        """
        return SchedulePattern(
            SchedulePattern.MONTHLY,
            day=day,
            time=time,
            timezone=timezone,
            interval=interval,
            exclusions=exclusions or []
        )

    @staticmethod
    def create_monthly_nth_weekday_pattern(nth_weekday: str, time: str, timezone: str = 'UTC',
                                          interval: int = 1, exclusions: List[str] = None) -> SchedulePattern:
        """
        Create a monthly schedule pattern with an nth weekday (e.g., "first monday", "last friday").

        Args:
            nth_weekday: String specifying the nth weekday (e.g., "first monday", "last friday")
            time: Time in HH:MM format
            timezone: Timezone string
            interval: Interval in months (default: 1)
            exclusions: List of dates to exclude (YYYY-MM-DD format)

        Returns:
            SchedulePattern object
        """
        return SchedulePattern(
            SchedulePattern.MONTHLY,
            nth_weekday=nth_weekday,
            time=time,
            timezone=timezone,
            interval=interval,
            exclusions=exclusions or []
        )

    @staticmethod
    def create_yearly_pattern(month: int, day: int, time: str, timezone: str = 'UTC',
                             interval: int = 1, exclusions: List[str] = None) -> SchedulePattern:
        """
        Create a yearly schedule pattern.

        Args:
            month: Month (1-12)
            day: Day of the month (1-31)
            time: Time in HH:MM format
            timezone: Timezone string
            interval: Interval in years (default: 1)
            exclusions: List of dates to exclude (YYYY-MM-DD format)

        Returns:
            SchedulePattern object
        """
        return SchedulePattern(
            SchedulePattern.YEARLY,
            month=month,
            day=day,
            time=time,
            timezone=timezone,
            interval=interval,
            exclusions=exclusions or []
        )

    @staticmethod
    def create_one_time_pattern(date: str, time: str, timezone: str = 'UTC') -> SchedulePattern:
        """
        Create a one-time schedule pattern.

        Args:
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            timezone: Timezone string

        Returns:
            SchedulePattern object
        """
        return SchedulePattern(
            SchedulePattern.ONE_TIME,
            date=date,
            time=time,
            timezone=timezone
        )
