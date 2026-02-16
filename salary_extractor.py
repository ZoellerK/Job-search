"""
Extract salary/compensation information from job description text.

Catches patterns like:
  $60,000 - $80,000       $75k-$100k         $120,000/year
  $45-$55 per hour        $80,000 to $100,000
  Salary: $90,000         Compensation: $60k-$80k
  USD 80,000-100,000      80,000 - 100,000 annually
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Pre-compiled patterns ordered from most specific to least specific.
# Each pattern captures the full salary string (including range separators).

_CURRENCY = r'\$'
_NUMBER = r'\d{1,3}(?:,\d{3})*'          # e.g. 120,000
_NUMBER_K = r'\d{2,3}(?:\.\d)?k'          # e.g. 75k, 120.5k
# Try k-notation first so "100k" isn't consumed as just "100"
_NUMBER_ANY = rf'(?:{_NUMBER_K}|{_NUMBER})'
_RANGE_SEP = r'\s*(?:-|–|—|to|through)\s*'
_PERIOD = r'(?:\s*(?:/|per\s+)?\s*(?:year|yr|annually|annual|annum|hour|hr|hourly|month|monthly|week|weekly))?'

_PATTERNS = [
    # "$60,000 - $80,000 /year" or "$75k-$100k"
    re.compile(
        rf'({_CURRENCY}\s*{_NUMBER_ANY}{_RANGE_SEP}{_CURRENCY}?\s*{_NUMBER_ANY}{_PERIOD})',
        re.IGNORECASE,
    ),
    # "USD 80,000 - 100,000"
    re.compile(
        rf'(USD\s*{_NUMBER_ANY}{_RANGE_SEP}{_NUMBER_ANY}{_PERIOD})',
        re.IGNORECASE,
    ),
    # Standalone "$120,000/year" or "$55/hour"
    re.compile(
        rf'({_CURRENCY}\s*{_NUMBER_ANY}\s*/?\s*(?:year|yr|annually|annual|per\s+annum|hour|hr|hourly|month|monthly|week|weekly))',
        re.IGNORECASE,
    ),
    # Standalone "$120,000" or "$75k" (only if preceded by salary-like context word)
    re.compile(
        rf'(?:salary|compensation|pay|earning|wage|stipend|range)[:\s]*({_CURRENCY}\s*{_NUMBER_ANY})',
        re.IGNORECASE,
    ),
]

# Reject obviously wrong matches (phone numbers, ZIP codes, revenue figures, etc.)
_REJECT = re.compile(
    r'(?:budget|revenue|endowment|grant|award|fund|donation|assets?|portfolio)',
    re.IGNORECASE,
)


def extract_salary(text: str) -> Optional[str]:
    """
    Return the first salary-like string found in *text*, or None.

    The returned string is lightly cleaned (trimmed whitespace, collapsed
    internal spaces) but otherwise preserved as-is from the source text so
    that downstream code can display it verbatim.
    """
    if not text:
        return None

    for pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1)
            # Check surrounding context (40 chars before match) for reject words
            start = max(0, match.start() - 40)
            context = text[start:match.start()]
            if _REJECT.search(context):
                continue

            cleaned = re.sub(r'\s+', ' ', raw).strip()
            if cleaned:
                return cleaned

    return None
