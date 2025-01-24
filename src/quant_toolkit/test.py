# from datetime_API import get_holiday_list, find_current_weekday
import datetime
from typing import Union
import calendar


def find_last_weekday(
    today_date: datetime.date, target_day: Union[int, str] = "Thursday"
) -> datetime.date:
    """
    Find the date of the specified weekday in the last week of the month.

    Args:
        today_date (datetime.date): A date within the target month
        target_day (int or str): Target weekday either as:
            - int (0-6, where 0=Monday, 6=Sunday)
            - str (full name like "Monday" or abbreviated "Mon")

    Returns:
        datetime.date: Date of the last occurrence of the target weekday in the month
    """
    # Get the last day of the month
    last_day = datetime.date(
        today_date.year,
        today_date.month,
        calendar.monthrange(today_date.year, today_date.month)[1],
    )

    # Find the current weekday for this last day
    current_weekday = last_day.weekday()

    # Convert target_day to integer if it's a string
    WEEKDAY_MAP = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }

    if isinstance(target_day, str):
        target_day = WEEKDAY_MAP.get(target_day.lower())

    # Calculate days to subtract to reach the last occurrence of target weekday
    days_to_subtract = (current_weekday - target_day + 7) % 7

    return last_day - datetime.timedelta(days=days_to_subtract)


print(find_last_weekday(datetime.date(2021, 1, 1), "Thu"))  # 2021-01-28
