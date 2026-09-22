# Temporal Reasoner
# Deterministic time parsing and range reasoning for marine queries

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class TemporalReasoner:
    """
    Provides deterministic time parsing and range operations.
    All operations are pure functions - no LLM dependency.
    """
    
    # Named regions with typical time ranges for marine analysis
    NAMED_REGION_TIME_RANGES = {
        "arabian_sea": {"default_days": 30, "monsoon": {"summer": (6, 9), "winter": (12, 3)}},
        "bay_of_bengal": {"default_days": 45, "monsoon": {"summer": (6, 9), "winter": (12, 3)}},
        "equatorial_indian_ocean": {"default_days": 90},
    }
    
    @staticmethod
    def parse_relative_time(
        text: str,
        reference_date: Optional[datetime] = None
    ) -> Optional[Dict[str, str]]:
        """
        Parse relative time expressions like 'tomorrow', 'last month', 'next week'.
        Returns {start, end} in ISO format or None if not recognized.
        """
        if reference_date is None:
            reference_date = datetime.utcnow()
        
        text_lower = text.lower().strip()
        
        # Today
        if text_lower == "today":
            start = reference_date.strftime("%Y-%m-%d")
            end = reference_date.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # Tomorrow
        if text_lower == "tomorrow":
            tomorrow = reference_date + timedelta(days=1)
            start = tomorrow.strftime("%Y-%m-%d")
            end = tomorrow.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # This week
        if "this week" in text_lower:
            days_since_monday = reference_date.weekday()
            start = (reference_date - timedelta(days=days_since_monday)).strftime("%Y-%m-%d")
            end = (start + timedelta(days=6)).strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # Last week
        if "last week" in text_lower:
            days_since_monday = reference_date.weekday()
            last_sunday = reference_date - timedelta(days=days_since_monday + 1)
            start = (last_sunday - timedelta(days=6)).strftime("%Y-%m-%d")
            end = last_sunday.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # This month
        if "this month" in text_lower:
            start = reference_date.replace(day=1).strftime("%Y-%m-%d")
            # First day of next month
            if reference_date.month == 12:
                next_month = reference_date.replace(year=reference_date.year + 1, month=1, day=1)
            else:
                next_month = reference_date.replace(month=reference_date.month + 1, day=1)
            end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # Last month
        if "last month" in text_lower:
            first_this_month = reference_date.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            first_last_month = last_month_end.replace(day=1)
            end = last_month_end.strftime("%Y-%m-%d")
            start = first_last_month.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # Next week
        if "next week" in text_lower:
            days_until_monday = (7 - reference_date.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            start = (reference_date + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
            end = (start + timedelta(days=6)).strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # Specific month year (e.g., "january 2024")
        month_year_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})'
        month_match = re.search(month_year_pattern, text_lower)
        if month_match:
            month_name = month_match.group(1)
            year = int(month_match.group(2))
            month_nums = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            month_num = month_nums[month_name]
            start = datetime(year, month_num, 1).strftime("%Y-%m-%d")
            # Last day of month
            if month_num == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month_num + 1, 1) - timedelta(days=1)
            end = last_day.strftime("%Y-%m-%d")
            return {"start": start, "end": end}
        
        # Season patterns
        season_patterns = {
            "summer": (6, 8),
            "monsoon": (6, 9),
            "winter": (12, 2),
            "pre_monsoon": (3, 5),
            "post_monsoon": (9, 11),
        }
        for season, (start_m, end_m) in season_patterns.items():
            if season in text_lower:
                start_date = reference_date.replace(month=start_m, day=1)
                if start_m == 12:
                    end_date = datetime(reference_date.year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = reference_date.replace(month=end_m + 1, day=1) - timedelta(days=1)
                # Adjust year if we've passed the season
                if reference_date.month > end_m:
                    start_date = start_date.replace(year=reference_date.year + 1)
                    end_date = end_date.replace(year=reference_date.year + 1)
                return {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                }
        
        return None
    
    @staticmethod
    def parse_time_range_from_query(
        query_text: str,
        reference_date: Optional[datetime] = None
    ) -> Optional[Dict[str, str]]:
        """
        Parse time range from a user query string.
        Tries relative time first, then specific patterns.
        """
        return TemporalReasoner.parse_relative_time(query_date, reference_date)
    
    @staticmethod
    def determine_season(month: int) -> str:
        """Determine season from month number (1-12)."""
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "pre_monsoon"
        elif month in [6, 7, 8]:
            return "monsoon"
        else:
            return "post_monsoon"
    
    @staticmethod
    def month_range_for_season(season: str, year: Optional[int] = None) -> Dict[str, str]:
        """Get month range for a given season."""
        if year is None:
            year = datetime.utcnow().year
        
        season_months = {
            "winter": (12, 2),
            "pre_monsoon": (3, 5),
            "monsoon": (6, 9),
            "post_monsoon": (10, 11),
        }
        
        start_month, end_month = season_months.get(season, (1, 12))
        
        start = datetime(year, start_month, 1).strftime("%Y-%m-%d")
        if end_month >= start_month:
            end = datetime(year, end_month + 1, 1) - timedelta(days=1)
        else:
            # Wraps around year end
            end = datetime(year + 1, 1, 1) - timedelta(days=1)
        
        return {"start": start, "end": end.strftime("%Y-%m-%d")}
    
    @staticmethod
    def days_between(start_str: str, end_str: str) -> int:
        """Calculate exact number of days between two ISO date strings."""
        try:
            from datetime import datetime
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            return (end - start).days
        except Exception:
            return 0


# Global temporal reasoner instance
_temporal_reasoner: Optional[TemporalReasoner] = None


def get_temporal_reasoner() -> TemporalReasoner:
    global _temporal_reasoner
    if _temporal_reasoner is None:
        _temporal_reasoner = TemporalReasoner()
    return _temporal_reasoner