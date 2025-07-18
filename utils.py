# ==============================================================================
# utils.py - Utility and Helper Functions
# ==============================================================================
# This file contains small, reusable functions that help with common tasks
# like parsing dates from filenames and formatting numbers for display.
# Keeping them here makes the main `core.py` file cleaner and more focused
# on the main business logic.
# ==============================================================================

import re
import datetime as dt
from dateutil import parser
import logging

def parse_file_date(name: str) -> dt.datetime | None:
    """
    A very flexible function to parse a date from a filename, robust against
    different separators (like space, underscore, or hyphen).
    It uses regular expressions to find all numbers in the filename.
    """
    # Remove the file extension (e.g., ".json").
    stem = name.rsplit('.', 1)[0]
    
    # A regular expression to find all sequences of digits in the filename.
    # For "2025-07-18 10_30.json", this will find ['2025', '07', '18', '10', '30'].
    numbers = re.findall(r'\d+', stem)
    
    # We expect between 3 (Y, M, D) and 6 (Y, M, D, h, m, s) number groups.
    if not (3 <= len(numbers) <= 6):
        logging.warning(f"Found an unexpected number of date components in '{name}'. Skipping file.")
        return None
        
    try:
        # Pad the list with '0' for any missing parts (hour, minute, second).
        while len(numbers) < 6:
            numbers.append('0')
            
        # Convert the found strings into integers.
        parts = [int(n) for n in numbers]
        
        # Create and return a datetime object from the parts.
        return dt.datetime(year=parts[0], month=parts[1], day=parts[2], 
                           hour=parts[3], minute=parts[4], second=parts[5])
                           
    except (ValueError, IndexError) as e:
        logging.error(f"Failed to assemble date from components {numbers} for file '{name}'. Error: {e}")
        return None


def pretty_usd(n: float | int) -> str:
    """
    Formats a number as a human-readable USD currency string (e.g., $1.23M, $45K).
    """
    if not isinstance(n, (int, float)):
        return "$0"
        
    sign = "-" if n < 0 else ""
    n = abs(n)
    
    if n >= 1_000_000_000:
        return f"{sign}${n/1_000_000_000:.2f}B" # Billions
    if n >= 1_000_000:
        return f"{sign}${n/1_000_000:.2f}M"   # Millions
    if n >= 1000:
        return f"{sign}${n/1000:.1f}K"      # Thousands
    return f"{sign}${n:.2f}"


def format_percentage(n: float | int) -> str:
    """Formats a number as a percentage string with a leading sign (+ or -)."""
    if not isinstance(n, (int, float)):
        return "0.0%"
    sign = "+" if n > 0 else ""
    return f"{sign}{n:.2f}%"
