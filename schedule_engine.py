"""
Flexible scheduling engine for Standup Bot with cron-like functionality.
Supports various recurring patterns, one-time meetings, and advanced scheduling features.
"""

import re
import time
import datetime
import calendar
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
import pytz
import holidays
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU


class SchedulePattern:
    """
    Represents a schedule pattern with cron-like functionality.
    Supports various recurring patterns (daily, weekly, monthly, yearly) and one-time schedules.
    """

    # Pattern types
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'
    ONE_TIME = 'one_time'

    # Weekday mapping
    WEEKDAY_MAP = {
        'monday': MO, 'tuesday': TU, 'wednesday': WE, 'thursday': TH,
        'friday': FR, 'saturday': SA, 'sunday': SU
    }

    # Weekday number mapping (0 = Monday, 6 = Sunday)
    WEEKDAY_NUM_MAP = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }

    def __init__(self, pattern_type: str, **kwargs):
        """Initialize a schedule pattern."""
        self.pattern_type = pattern_type
        self.time = kwargs.get('time', '00:00')
        self.timezone = kwargs.get('timezone', 'UTC')
        self.end_date = kwargs.get('end_date')
        self.exclusions = kwargs.get('exclusions', [])

        # Pattern-specific parameters
        if pattern_type == self.DAILY:
            self.interval = kwargs.get('interval', 1)

        elif pattern_type == self.WEEKLY:
            self.days = kwargs.get('days', ['monday'])
            self.interval = kwargs.get('interval', 1)

        elif pattern_type == self.MONTHLY:
            self.interval = kwargs.get('interval', 1)
            if 'day' in kwargs:
                self.day = kwargs['day']
                self.nth_weekday = None
            elif 'nth_weekday' in kwargs:
                self.nth_weekday = kwargs['nth_weekday']
                self.day = None
            else:
                self.day = 1  # Default to first day of month
                self.nth_weekday = None

        elif pattern_type == self.YEARLY:
            self.month = kwargs.get('month', 1)
            self.day = kwargs.get('day', 1)
            self.interval = kwargs.get('interval', 1)

        elif pattern_type == self.ONE_TIME:
            self.date = kwargs.get('date')
            if not self.date:
                raise ValueError("One-time schedule requires a date parameter")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the pattern to a dictionary for storage"""
        result = {
            'pattern_type': self.pattern_type,
            'time': self.time,
            'timezone': self.timezone
        }

        if self.end_date:
            result['end_date'] = self.end_date

        if self.exclusions:
            result['exclusions'] = self.exclusions

        if self.pattern_type == self.DAILY:
            result['interval'] = self.interval

        elif self.pattern_type == self.WEEKLY:
            result['days'] = self.days
            result['interval'] = self.interval

        elif self.pattern_type == self.MONTHLY:
            result['interval'] = self.interval
            if self.day:
                result['day'] = self.day
            elif self.nth_weekday:
                result['nth_weekday'] = self.nth_weekday

        elif self.pattern_type == self.YEARLY:
            result['month'] = self.month
            result['day'] = self.day
            result['interval'] = self.interval

        elif self.pattern_type == self.ONE_TIME:
            result['date'] = self.date

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SchedulePattern':
        """Create a pattern from a dictionary"""
        pattern_type = data.get('pattern_type')
        if not pattern_type:
            raise ValueError("Pattern type is required")

        return cls(pattern_type, **data)

    @classmethod
    def from_legacy_schedule(cls, schedule: Dict[str, Any]) -> 'SchedulePattern':
        """Convert a legacy schedule format to a SchedulePattern."""
        return cls(
            cls.WEEKLY,
            days=schedule.get('days', ['monday']),
            time=schedule.get('time', '00:00'),
            timezone=schedule.get('timezone', 'UTC'),
            interval=1
        )

    def next_occurrence(self, after: Optional[datetime.datetime] = None) -> Optional[datetime.datetime]:
        """Calculate the next occurrence of this schedule pattern after the given datetime."""
        if after is None:
            after = datetime.datetime.now(pytz.timezone(self.timezone))
        elif after.tzinfo is None:
            # If after is naive, assume it's in the pattern's timezone
            after = pytz.timezone(self.timezone).localize(after)

        # Check end date
        if self.end_date:
            end_date = datetime.datetime.strptime(self.end_date, '%Y-%m-%d').date()
            if after.date() > end_date:
                return None

        # Parse time
        try:
            hours, minutes = map(int, self.time.split(':'))
        except (ValueError, AttributeError):
            hours, minutes = 0, 0

        # Handle different pattern types
        if self.pattern_type == self.ONE_TIME:
            # For one-time schedules
            try:
                date_parts = self.date.split('-')
                year, month, day = map(int, date_parts)
                tz = pytz.timezone(self.timezone)
                dt = tz.localize(datetime.datetime(year, month, day, hours, minutes))

                if dt > after and self.date not in self.exclusions:
                    return dt
                return None
            except (ValueError, AttributeError):
                return None

        # For recurring patterns, use dateutil.rrule
        if self.pattern_type == self.DAILY:
            rule = rrule(
                DAILY,
                interval=self.interval,
                dtstart=after.replace(hour=0, minute=0, second=0, microsecond=0),
                count=100  # Limit search to avoid infinite loops
            )

        elif self.pattern_type == self.WEEKLY:
            # Convert day names to rrule weekdays
            weekdays = [self.WEEKDAY_MAP[day.lower()] for day in self.days if day.lower() in self.WEEKDAY_MAP]
            if not weekdays:
                return None

            rule = rrule(
                WEEKLY,
                interval=self.interval,
                byweekday=weekdays,
                dtstart=after.replace(hour=0, minute=0, second=0, microsecond=0),
                count=100  # Limit search to avoid infinite loops
            )

        elif self.pattern_type == self.MONTHLY:
            if self.day:
                # Simple day of month
                rule = rrule(
                    MONTHLY,
                    interval=self.interval,
                    bymonthday=self.day,
                    dtstart=after.replace(hour=0, minute=0, second=0, microsecond=0),
                    count=100  # Limit search to avoid infinite loops
                )
            elif self.nth_weekday:
                # For nth weekday patterns, handle specially
                # This is a simplified implementation
                current = after.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                for _ in range(12):  # Check next 12 months
                    # Move to the next month based on interval
                    if _ > 0:
                        current += relativedelta(months=self.interval)

                    # Try to find the nth weekday in this month
                    # This is a simplified implementation
                    match = re.match(r'^(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last) (monday|tuesday|wednesday|thursday|friday|saturday|sunday)$', self.nth_weekday.lower())
                    if not match:
                        continue

                    position, weekday = match.groups()
                    weekday_num = self.WEEKDAY_NUM_MAP.get(weekday)

                    # Calculate the date
                    if position == 'last':
                        # Get the last day of the month
                        last_day = calendar.monthrange(current.year, current.month)[1]
                        dt = datetime.date(current.year, current.month, last_day)
                        while dt.weekday() != weekday_num:
                            dt -= datetime.timedelta(days=1)
                    else:
                        # Convert position to a number
                        if position in ('first', '1st'):
                            n = 1
                        elif position in ('second', '2nd'):
                            n = 2
                        elif position in ('third', '3rd'):
                            n = 3
                        elif position in ('fourth', '4th'):
                            n = 4
                        elif position in ('fifth', '5th'):
                            n = 5
                        else:
                            continue

                        # Find the nth occurrence of the weekday
                        dt = datetime.date(current.year, current.month, 1)
                        days_until_weekday = (weekday_num - dt.weekday()) % 7
                        dt += datetime.timedelta(days=days_until_weekday)
                        dt += datetime.timedelta(days=(n - 1) * 7)

                        # Check if the date is still in the same month
                        if dt.month != current.month:
                            continue

                    # Create datetime with the pattern's time
                    tz = pytz.timezone(self.timezone)
                    dt_with_time = tz.localize(datetime.datetime.combine(dt, datetime.time(hours, minutes)))

                    if dt_with_time > after and dt_with_time.strftime('%Y-%m-%d') not in self.exclusions:
                        return dt_with_time

                return None
            else:
                return None

        elif self.pattern_type == self.YEARLY:
            rule = rrule(
                YEARLY,
                interval=self.interval,
                bymonth=self.month,
                bymonthday=self.day,
                dtstart=after.replace(hour=0, minute=0, second=0, microsecond=0),
                count=100  # Limit search to avoid infinite loops
            )

        else:
            return None

        # Find the next occurrence
        for dt in rule:
            # Convert to the pattern's timezone
            dt = dt.replace(hour=hours, minute=minutes)
            if dt.tzinfo is None:
                dt = pytz.timezone(self.timezone).localize(dt)

            if dt > after and dt.strftime('%Y-%m-%d') not in self.exclusions:
                return dt

        return None


class ScheduleEngine:
    """
    Advanced scheduling engine with cron-like functionality.
    Supports various recurring patterns, one-time meetings, and advanced scheduling features.
    """

    def __init__(self):
        """Initialize the schedule engine"""
        self.scheduled_tasks = []
        self.task_map = {}  # Maps task_id to index in scheduled_tasks

    def schedule_task(self, task_id: str, pattern: SchedulePattern, task_func: Callable, *args) -> bool:
        """Schedule a task according to a pattern."""
        # Calculate the next occurrence
        next_time = pattern.next_occurrence()
        if not next_time:
            return False

        # Convert to timestamp
        next_timestamp = next_time.timestamp()

        # Store the task
        task = (next_timestamp, task_id, pattern, task_func, args)

        # If this task_id already exists, remove the old entry
        if task_id in self.task_map:
            old_index = self.task_map[task_id]
            self.scheduled_tasks[old_index] = None  # Mark as deleted

        # Add the new task
        self.scheduled_tasks.append(task)
        self.task_map[task_id] = len(self.scheduled_tasks) - 1

        # Sort the tasks by timestamp
        self._sort_tasks()

        return True

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self.task_map:
            index = self.task_map[task_id]
            self.scheduled_tasks[index] = None  # Mark as deleted
            del self.task_map[task_id]
            return True
        return False

    def get_due_tasks(self, current_time: Optional[float] = None) -> List[Tuple[str, Callable, tuple]]:
        """Get tasks that are due to be executed."""
        if current_time is None:
            current_time = time.time()

        due_tasks = []
        reschedule_tasks = []

        # Clean up the task list by removing None entries
        self.scheduled_tasks = [task for task in self.scheduled_tasks if task is not None]

        # Rebuild the task map
        self.task_map = {task[1]: i for i, task in enumerate(self.scheduled_tasks)}

        # Sort tasks by timestamp
        self._sort_tasks()

        # Check for tasks that need to be executed
        while self.scheduled_tasks and self.scheduled_tasks[0][0] <= current_time:
            next_time, task_id, pattern, task_func, args = self.scheduled_tasks.pop(0)
            del self.task_map[task_id]

            # Add to due tasks
            due_tasks.append((task_id, task_func, args))

            # If this is a recurring pattern, schedule the next occurrence
            if pattern.pattern_type != SchedulePattern.ONE_TIME:
                # Calculate the next occurrence after the current occurrence
                after_time = datetime.datetime.fromtimestamp(next_time, pytz.timezone(pattern.timezone))
                next_occurrence = pattern.next_occurrence(after_time)

                if next_occurrence:
                    # Schedule the next occurrence
                    reschedule_tasks.append((task_id, pattern, task_func, args))

        # Reschedule recurring tasks
        for task_id, pattern, task_func, args in reschedule_tasks:
            self.schedule_task(task_id, pattern, task_func, *args)

        return due_tasks

    def get_next_occurrence(self, task_id: str) -> Optional[datetime.datetime]:
        """Get the next occurrence of a scheduled task."""
        if task_id in self.task_map:
            index = self.task_map[task_id]
            task = self.scheduled_tasks[index]
            if task:
                timestamp = task[0]
                return datetime.datetime.fromtimestamp(timestamp, pytz.timezone(task[2].timezone))
        return None

    def _sort_tasks(self) -> None:
        """Sort the scheduled tasks by timestamp"""
        # Filter out None entries
        self.scheduled_tasks = [task for task in self.scheduled_tasks if task is not None]

        # Sort by timestamp
        self.scheduled_tasks.sort(key=lambda x: x[0])

        # Rebuild the task map
        self.task_map = {task[1]: i for i, task in enumerate(self.scheduled_tasks)}


class HolidayCalendar:
    """Calendar for tracking holidays and weekends."""

    def __init__(self, country_code: str = 'US'):
        """Initialize the holiday calendar."""
        self.country_code = country_code
        self.custom_holidays = {}  # Custom holidays defined by the user
        self._load_holidays()

    def _load_holidays(self) -> None:
        """Load holidays for the configured country using the holidays library"""
        try:
            # Get the current year and the next year
            current_year = datetime.datetime.now().year
            years = range(current_year, current_year + 3)

            # Initialize the holidays library with the specified country code
            self.holiday_lib = holidays.country_holidays(self.country_code, years=years)
        except (KeyError, AttributeError) as e:
            # If the country code is not supported, fall back to US holidays
            import logging
            logging.warning(f"Country code '{self.country_code}' not supported by holidays library. Falling back to US holidays. Error: {e}")
            self.country_code = 'US'
            self.holiday_lib = holidays.US(years=years)

    def add_custom_holiday(self, date_str: str, name: str) -> None:
        """Add a custom holiday."""
        self.custom_holidays[date_str] = name

    def is_holiday(self, date_obj: Union[datetime.date, datetime.datetime, str]) -> bool:
        """Check if a date is a holiday."""
        # Convert to date object
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.datetime.strptime(date_obj, '%Y-%m-%d').date()
            except ValueError:
                return False
        elif isinstance(date_obj, datetime.datetime):
            date_obj = date_obj.date()

        # Check if it's a custom holiday
        date_str = date_obj.strftime('%Y-%m-%d')
        if date_str in self.custom_holidays:
            return True

        # Check if it's a holiday in the holidays library
        return date_obj in self.holiday_lib

    def is_weekend(self, date_obj: Union[datetime.date, datetime.datetime, str]) -> bool:
        """Check if a date is a weekend (Saturday or Sunday)."""
        # Convert to date object
        if isinstance(date_obj, str):
            date_obj = datetime.datetime.strptime(date_obj, '%Y-%m-%d').date()
        elif isinstance(date_obj, datetime.datetime):
            date_obj = date_obj.date()

        # Check if it's a weekend (5=Saturday, 6=Sunday)
        return date_obj.weekday() >= 5

    def is_business_day(self, date_obj: Union[datetime.date, datetime.datetime, str]) -> bool:
        """Check if a date is a business day (not a weekend or holiday)."""
        return not (self.is_weekend(date_obj) or self.is_holiday(date_obj))

    def get_holiday_name(self, date_obj: Union[datetime.date, datetime.datetime, str]) -> Optional[str]:
        """Get the name of a holiday for a given date."""
        # Convert to date object
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.datetime.strptime(date_obj, '%Y-%m-%d').date()
            except ValueError:
                return None
        elif isinstance(date_obj, datetime.datetime):
            date_obj = date_obj.date()

        # Check if it's a custom holiday
        date_str = date_obj.strftime('%Y-%m-%d')
        if date_str in self.custom_holidays:
            return self.custom_holidays[date_str]

        # Check if it's a holiday in the holidays library
        if date_obj in self.holiday_lib:
            return self.holiday_lib.get(date_obj)

        return None

    def get_next_business_day(self, date_obj: Union[datetime.date, datetime.datetime, str]) -> datetime.date:
        """Get the next business day after a given date."""
        # Convert to date object
        if isinstance(date_obj, str):
            date_obj = datetime.datetime.strptime(date_obj, '%Y-%m-%d').date()
        elif isinstance(date_obj, datetime.datetime):
            date_obj = date_obj.date()

        # Start with the next day
        next_day = date_obj + datetime.timedelta(days=1)

        # Keep checking days until we find a business day
        while not self.is_business_day(next_day):
            next_day += datetime.timedelta(days=1)

        return next_day


class CalendarIntegration:
    """Integration with external calendars for OOO (Out of Office) awareness."""

    def __init__(self):
        """Initialize the calendar integration"""
        self.user_ooo = {}  # Map of user_id -> list of OOO periods

    def add_ooo(self, user_id: int, start_date: str, end_date: str, reason: Optional[str] = None) -> None:
        """Add an Out of Office period for a user."""
        if user_id not in self.user_ooo:
            self.user_ooo[user_id] = []

        # Add the OOO period
        self.user_ooo[user_id].append({
            'start_date': start_date,
            'end_date': end_date,
            'reason': reason
        })

        # Sort by start date
        self.user_ooo[user_id].sort(key=lambda x: x['start_date'])

    def remove_ooo(self, user_id: int, start_date: str, end_date: str) -> bool:
        """Remove an Out of Office period for a user."""
        if user_id not in self.user_ooo:
            return False

        # Find the OOO period to remove
        for i, ooo in enumerate(self.user_ooo[user_id]):
            if ooo['start_date'] == start_date and ooo['end_date'] == end_date:
                del self.user_ooo[user_id][i]
                return True

        return False

    def is_user_ooo(self, user_id: int, date: Union[str, datetime.date, datetime.datetime]) -> bool:
        """Check if a user is Out of Office on a specific date."""
        if user_id not in self.user_ooo:
            return False

        # Convert date to string if needed
        if isinstance(date, datetime.datetime) or isinstance(date, datetime.date):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = date

        # Check if the date is within any OOO period
        for ooo in self.user_ooo[user_id]:
            if ooo['start_date'] <= date_str <= ooo['end_date']:
                return True

        return False

    def get_ooo_users(self, date: Union[str, datetime.date, datetime.datetime]) -> List[int]:
        """Get all users who are Out of Office on a specific date."""
        # Convert date to string if needed
        if isinstance(date, datetime.datetime) or isinstance(date, datetime.date):
            date_str = date.strftime('%Y-%m-%d')
        else:
            date_str = date

        # Find all users who are OOO on this date
        ooo_users = []
        for user_id, ooo_periods in self.user_ooo.items():
            for ooo in ooo_periods:
                if ooo['start_date'] <= date_str <= ooo['end_date']:
                    ooo_users.append(user_id)
                    break

        return ooo_users

    def get_user_ooo_periods(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all Out of Office periods for a user."""
        return self.user_ooo.get(user_id, [])


class ScheduleConflictDetector:
    """Detects scheduling conflicts between standups and user availability."""

    def __init__(self, calendar_integration: CalendarIntegration, holiday_calendar: HolidayCalendar):
        """Initialize the conflict detector."""
        self.calendar_integration = calendar_integration
        self.holiday_calendar = holiday_calendar

    def check_conflicts(self, standup_id: str, pattern: SchedulePattern, participants: List[int],
                        start_date: str, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Check for scheduling conflicts.

        Returns a dictionary with:
        - conflicts: List of conflict details
        - ooo_users: Map of date -> list of OOO users
        - holidays: Map of date -> holiday name
        - weekends: List of weekend dates
        """
        conflicts = {
            'conflicts': [],
            'ooo_users': {},
            'holidays': {},
            'weekends': []
        }

        # Convert dates to datetime objects
        start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')
        else:
            # Default to 3 months from start date
            end_dt = start_dt + datetime.timedelta(days=90)

        # Get all occurrences in the date range
        current = start_dt
        while current <= end_dt:
            next_occurrence = pattern.next_occurrence(current)
            if not next_occurrence or next_occurrence.date() > end_dt.date():
                break

            date_str = next_occurrence.strftime('%Y-%m-%d')

            # Check for holidays
            if self.holiday_calendar.is_holiday(date_str):
                conflicts['holidays'][date_str] = self.holiday_calendar.get_holiday_name(date_str)
                conflicts['conflicts'].append({
                    'date': date_str,
                    'type': 'holiday',
                    'details': self.holiday_calendar.get_holiday_name(date_str)
                })

            # Check for weekends
            if self.holiday_calendar.is_weekend(date_str):
                conflicts['weekends'].append(date_str)
                conflicts['conflicts'].append({
                    'date': date_str,
                    'type': 'weekend',
                    'details': 'Weekend'
                })

            # Check for OOO users
            ooo_users = self.calendar_integration.get_ooo_users(date_str)
            ooo_participants = [user_id for user_id in ooo_users if user_id in participants]
            if ooo_participants:
                conflicts['ooo_users'][date_str] = ooo_participants
                conflicts['conflicts'].append({
                    'date': date_str,
                    'type': 'ooo',
                    'details': f"{len(ooo_participants)} participants OOO",
                    'users': ooo_participants
                })

            # Move to the next day
            current = next_occurrence + datetime.timedelta(days=1)

        return conflicts
