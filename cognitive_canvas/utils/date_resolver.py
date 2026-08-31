"""
Date and time resolution utilities for Cognitive Canvas.
Provides date context for prompt injection and natural language relative date calculations.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any


def get_date_context() -> Dict[str, Any]:
    """
    Returns rich date context based on current system time.
    """
    now = datetime.now()
    today = now.date()

    # Calculate next occurrences
    tomorrow = today + timedelta(days=1)
    
    # Days until Saturday (weekend)
    days_to_sat = (5 - today.weekday()) % 7
    if days_to_sat == 0:
        days_to_sat = 7  # next Saturday if today is Saturday
    next_saturday = today + timedelta(days=days_to_sat)

    # Days until next Monday
    days_to_mon = (7 - today.weekday()) % 7
    if days_to_mon == 0:
        days_to_mon = 7
    next_monday = today + timedelta(days=days_to_mon)

    in_two_weeks = today + timedelta(weeks=2)
    in_one_month = today + timedelta(days=30)

    return {
        "today_iso": today.isoformat(),
        "today_human": today.strftime("%A, %B %d, %Y"),
        "day_of_week": today.strftime("%A"),
        "current_time": now.strftime("%I:%M %p"),
        "tomorrow_iso": tomorrow.isoformat(),
        "tomorrow_human": tomorrow.strftime("%A, %B %d"),
        "next_saturday_iso": next_saturday.isoformat(),
        "next_monday_iso": next_monday.isoformat(),
        "in_two_weeks_iso": in_two_weeks.isoformat(),
        "in_one_month_iso": in_one_month.isoformat(),
        "current_month_year": today.strftime("%B %Y"),
        "current_year": today.year,
        "current_month": today.month,
        "current_day": today.day,
    }


def get_prompt_date_header() -> str:
    """
    Returns formatted date context block to inject into the system prompt.
    """
    ctx = get_date_context()
    return f"""## CURRENT TEMPORAL CONTEXT
- **Today's Date**: {ctx['today_human']} (ISO: `{ctx['today_iso']}`)
- **Current Time**: {ctx['current_time']}
- **Tomorrow**: {ctx['tomorrow_human']} (`{ctx['tomorrow_iso']}`)
- **Upcoming Saturday**: `{ctx['next_saturday_iso']}`
- **Next Monday**: `{ctx['next_monday_iso']}`
- **In 2 Weeks**: `{ctx['in_two_weeks_iso']}`
- **Current Month & Year**: {ctx['current_month_year']}

Always interpret relative time expressions (e.g. "today", "tomorrow", "this Friday", "next week", "on the 14th", "in 2 weeks") relative to `{ctx['today_iso']}`. Output dates in `YYYY-MM-DD` ISO format when calling tools.
"""
