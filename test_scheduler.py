"""
Test script for the new scheduling functionality.
"""

import datetime
import pytz
from schedule_engine import SchedulePattern, ScheduleEngine, HolidayCalendar, CalendarIntegration
from schedule_adapter import ScheduleAdapter

def test_schedule_patterns():
    """Test different schedule patterns."""
    print("Testing schedule patterns...")

    # Test daily pattern
    daily_pattern = ScheduleAdapter.create_daily_pattern(
        time="09:00",
        timezone="UTC",
        interval=1
    )

    # Test weekly pattern
    weekly_pattern = ScheduleAdapter.create_weekly_pattern(
        days=["monday", "wednesday", "friday"],
        time="10:00",
        timezone="UTC",
        interval=1
    )

    # Test monthly pattern (specific day)
    monthly_day_pattern = ScheduleAdapter.create_monthly_pattern(
        day=15,
        time="11:00",
        timezone="UTC",
        interval=1
    )

    # Test monthly pattern (nth weekday)
    monthly_nth_weekday_pattern = ScheduleAdapter.create_monthly_nth_weekday_pattern(
        nth_weekday="first monday",
        time="12:00",
        timezone="UTC",
        interval=1
    )

    # Test yearly pattern
    yearly_pattern = ScheduleAdapter.create_yearly_pattern(
        month=1,
        day=1,
        time="13:00",
        timezone="UTC",
        interval=1
    )

    # Test one-time pattern
    # Use a date in the future
    future_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    one_time_pattern = ScheduleAdapter.create_one_time_pattern(
        date=future_date,
        time="14:00",
        timezone="UTC"
    )

    # Test next occurrence calculation
    now = datetime.datetime.now(pytz.UTC)
    print(f"Current time: {now}")

    print("\nDaily pattern:")
    next_daily = daily_pattern.next_occurrence(now)
    print(f"Next occurrence: {next_daily}")

    print("\nWeekly pattern:")
    next_weekly = weekly_pattern.next_occurrence(now)
    print(f"Next occurrence: {next_weekly}")

    print("\nMonthly pattern (specific day):")
    next_monthly_day = monthly_day_pattern.next_occurrence(now)
    print(f"Next occurrence: {next_monthly_day}")

    print("\nMonthly pattern (nth weekday):")
    next_monthly_nth_weekday = monthly_nth_weekday_pattern.next_occurrence(now)
    print(f"Next occurrence: {next_monthly_nth_weekday}")

    print("\nYearly pattern:")
    next_yearly = yearly_pattern.next_occurrence(now)
    print(f"Next occurrence: {next_yearly}")

    print("\nOne-time pattern:")
    next_one_time = one_time_pattern.next_occurrence(now)
    print(f"Next occurrence: {next_one_time}")

def test_schedule_engine():
    """Test the schedule engine."""
    print("\nTesting schedule engine...")

    engine = ScheduleEngine()

    # Create a test pattern
    pattern = ScheduleAdapter.create_daily_pattern(
        time="09:00",
        timezone="UTC",
        interval=1
    )

    # Define a test task function
    def test_task(task_id):
        print(f"Executing task {task_id} at {datetime.datetime.now()}")

    # Schedule the task
    engine.schedule_task("test_task", pattern, test_task, "test_task")

    # Get the next occurrence
    next_occurrence = engine.get_next_occurrence("test_task")
    print(f"Next occurrence of test_task: {next_occurrence}")

    # Get due tasks (should be empty since the task is scheduled for the future)
    due_tasks = engine.get_due_tasks()
    print(f"Due tasks: {due_tasks}")

def test_holiday_calendar():
    """Test the holiday calendar."""
    print("\nTesting holiday calendar...")

    # Test US holidays
    us_calendar = HolidayCalendar('US')

    # Test built-in holidays
    today = datetime.date.today()
    new_years_day = f"{today.year}-01-01"
    independence_day = f"{today.year}-07-04"
    christmas_day = f"{today.year}-12-25"

    print(f"Is {new_years_day} a holiday in US? {us_calendar.is_holiday(new_years_day)}")
    print(f"Holiday name for {new_years_day}: {us_calendar.get_holiday_name(new_years_day)}")
    print(f"Is {independence_day} a holiday in US? {us_calendar.is_holiday(independence_day)}")
    print(f"Holiday name for {independence_day}: {us_calendar.get_holiday_name(independence_day)}")
    print(f"Is {christmas_day} a holiday in US? {us_calendar.is_holiday(christmas_day)}")
    print(f"Holiday name for {christmas_day}: {us_calendar.get_holiday_name(christmas_day)}")

    # Test custom holidays
    custom_holiday = f"{today.year}-03-14"  # Pi Day
    us_calendar.add_custom_holiday(custom_holiday, "Pi Day")
    print(f"Is {custom_holiday} a holiday? {us_calendar.is_holiday(custom_holiday)}")
    print(f"Holiday name for {custom_holiday}: {us_calendar.get_holiday_name(custom_holiday)}")

    # Test other countries
    uk_calendar = HolidayCalendar('GB')
    boxing_day = f"{today.year}-12-26"  # Boxing Day in UK
    print(f"Is {boxing_day} a holiday in UK? {uk_calendar.is_holiday(boxing_day)}")
    print(f"Holiday name for {boxing_day} in UK: {uk_calendar.get_holiday_name(boxing_day)}")

    # Test weekends
    # Find the next Saturday
    next_saturday = today
    while next_saturday.weekday() != 5:  # 5 = Saturday
        next_saturday += datetime.timedelta(days=1)

    next_saturday_str = next_saturday.strftime('%Y-%m-%d')
    print(f"Is {next_saturday_str} a weekend? {us_calendar.is_weekend(next_saturday_str)}")

    # Test business days
    print(f"Is {today.strftime('%Y-%m-%d')} a business day? {us_calendar.is_business_day(today)}")
    next_business_day = us_calendar.get_next_business_day(today)
    print(f"Next business day after {today.strftime('%Y-%m-%d')}: {next_business_day}")

    # Test invalid country code (should fall back to US)
    invalid_calendar = HolidayCalendar('INVALID')
    print(f"Is {new_years_day} a holiday with invalid country code? {invalid_calendar.is_holiday(new_years_day)}")
    print(f"Holiday name for {new_years_day} with invalid country code: {invalid_calendar.get_holiday_name(new_years_day)}")

def test_calendar_integration():
    """Test the calendar integration."""
    print("\nTesting calendar integration...")

    calendar = CalendarIntegration()

    # Test OOO periods
    user_id = 123
    start_date = datetime.date.today().strftime('%Y-%m-%d')
    end_date = (datetime.date.today() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

    # Add OOO period
    calendar.add_ooo(user_id, start_date, end_date, "Vacation")
    print(f"Added OOO period for user {user_id} from {start_date} to {end_date}")

    # Check if user is OOO
    check_date = (datetime.date.today() + datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    is_ooo = calendar.is_user_ooo(user_id, check_date)
    print(f"Is user {user_id} OOO on {check_date}? {is_ooo}")

    # Get OOO users
    ooo_users = calendar.get_ooo_users(check_date)
    print(f"Users OOO on {check_date}: {ooo_users}")

    # Get user OOO periods
    ooo_periods = calendar.get_user_ooo_periods(user_id)
    print(f"OOO periods for user {user_id}: {ooo_periods}")

    # Remove OOO period
    calendar.remove_ooo(user_id, start_date, end_date)
    print(f"Removed OOO period for user {user_id} from {start_date} to {end_date}")

    # Check if user is still OOO
    is_ooo = calendar.is_user_ooo(user_id, check_date)
    print(f"Is user {user_id} still OOO on {check_date}? {is_ooo}")

if __name__ == "__main__":
    test_schedule_patterns()
    test_schedule_engine()
    test_holiday_calendar()
    test_calendar_integration()
