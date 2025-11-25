"""
Input validation and parsing for Discord DM onboarding flow.

This module provides validators and parsers for user inputs during onboarding,
including date parsing, deadline validation, tone preference validation,
and check-in frequency parsing.

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import re
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of input validation."""
    
    def __init__(
        self,
        is_valid: bool,
        value: Optional[any] = None,
        error_message: Optional[str] = None,
        is_ambiguous: bool = False,
        clarification_needed: Optional[str] = None
    ):
        """
        Initialize validation result.
        
        Args:
            is_valid: Whether the input is valid
            value: The parsed/validated value
            error_message: Error message if invalid
            is_ambiguous: Whether the input is ambiguous
            clarification_needed: Clarification question if ambiguous
        """
        self.is_valid = is_valid
        self.value = value
        self.error_message = error_message
        self.is_ambiguous = is_ambiguous
        self.clarification_needed = clarification_needed


class DateParser:
    """
    Parser for date inputs with multiple format support.
    
    Supports various date formats including:
    - ISO format: 2024-12-31
    - US format: 12/31/2024
    - European format: 31/12/2024
    - Natural language: "next Friday", "in 2 weeks"
    - Relative dates: "tomorrow", "next month"
    - Conversational: "end of the month", "middle of next week"
    """
    
    # Common date formats to try
    DATE_FORMATS = [
        "%Y-%m-%d",           # 2024-12-31
        "%m/%d/%Y",           # 12/31/2024
        "%d/%m/%Y",           # 31/12/2024
        "%B %d, %Y",          # December 31, 2024
        "%b %d, %Y",          # Dec 31, 2024
        "%d %B %Y",           # 31 December 2024
        "%d %b %Y",           # 31 Dec 2024
        "%Y/%m/%d",           # 2024/12/31
        "%m-%d-%Y",           # 12-31-2024
        "%d-%m-%Y",           # 31-12-2024
    ]
    
    # Relative date keywords with more natural language variations
    RELATIVE_KEYWORDS = {
        "today": 0,
        "tomorrow": 1,
        "next week": 7,
        "next month": 30,
        "in a week": 7,
        "in a month": 30,
        "in 2 weeks": 14,
        "in 3 weeks": 21,
        "in 2 months": 60,
        "in 3 months": 90,
        "in 6 months": 180,
        "in a year": 365,
        "next year": 365,
        "end of the week": 7,
        "end of the month": 30,
        "end of next month": 60,
        "middle of next week": 10,
        "middle of the month": 15,
        "beginning of next month": 30,
        "start of next month": 30,
    }
    
    @classmethod
    def parse(cls, date_string: str) -> ValidationResult:
        """
        Parse a date string into a datetime object.
        
        Tries multiple formats and handles natural language dates.
        Enhanced to support more conversational date expressions.
        
        Args:
            date_string: The date string to parse
            
        Returns:
            ValidationResult with parsed datetime or error
            
        Validates: Requirements 3.1
        """
        if not date_string or not date_string.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Please provide a date for your project deadline."
            )
        
        original_string = date_string.strip()
        date_string = original_string.lower()
        
        # Handle numeric relative dates FIRST (before extraction) like "in 5 days", "in 3 weeks", "in 2 months"
        # This must come before date_indicators extraction to avoid breaking the pattern
        numeric_relative_patterns = [
            (r'(?:in|within)\s+(\d+)\s+days?', 1),
            (r'(?:in|within)\s+(\d+)\s+weeks?', 7),
            (r'(?:in|within)\s+(\d+)\s+months?', 30),
        ]
        
        for pattern, multiplier in numeric_relative_patterns:
            match = re.search(pattern, date_string, re.IGNORECASE)
            if match:
                count = int(match.group(1))
                days_offset = count * multiplier
                result_date = datetime.now() + timedelta(days=days_offset)
                result_date = result_date.replace(hour=23, minute=59, second=59, microsecond=0)
                logger.info(f"Parsed numeric relative date '{original_string}' to {result_date}")
                return ValidationResult(is_valid=True, value=result_date)
        
        # Extract conversational context that might indicate a date
        # Handle phrases like "I need it by Friday" or "deadline is next month"
        date_indicators = [
            r'(?:by|until|before|on|around|about)\s+(.+)',
            r'(?:deadline|due|finish|complete)(?:\s+(?:is|by|on))?\s+(.+)',
        ]
        
        for pattern in date_indicators:
            match = re.search(pattern, date_string, re.IGNORECASE)
            if match:
                extracted_date = match.group(1).strip()
                logger.info(f"Extracted date phrase '{extracted_date}' from '{date_string}'")
                date_string = extracted_date
                break
        
        # Try relative keywords (with longest matches first to avoid partial matches)
        sorted_keywords = sorted(cls.RELATIVE_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True)
        for keyword, days_offset in sorted_keywords:
            if keyword in date_string:
                result_date = datetime.now() + timedelta(days=days_offset)
                # Set to end of day
                result_date = result_date.replace(hour=23, minute=59, second=59, microsecond=0)
                logger.info(f"Parsed relative date '{original_string}' to {result_date}")
                return ValidationResult(is_valid=True, value=result_date)
        
        # Try dateutil parser (handles many natural language formats)
        try:
            # First check if the string contains at least some date-like components
            # This prevents parsing of completely invalid strings like 'xyz123'
            has_date_component = any(char.isdigit() for char in date_string)
            if not has_date_component:
                raise ValueError("No numeric date components found")
            
            parsed_date = date_parser.parse(date_string, fuzzy=True)
            
            # Additional validation: check if the parsed date is reasonable
            # Reject if year is too far in past or future
            if parsed_date.year < 2000 or parsed_date.year > 2100:
                raise ValueError(f"Year {parsed_date.year} is out of reasonable range")
            
            # If only date provided (no time), set to end of day
            if parsed_date.hour == 0 and parsed_date.minute == 0:
                parsed_date = parsed_date.replace(hour=23, minute=59, second=59, microsecond=0)
            logger.info(f"Parsed date '{original_string}' to {parsed_date}")
            return ValidationResult(is_valid=True, value=parsed_date)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date '{original_string}': {e}")
        
        # If all parsing attempts fail
        return ValidationResult(
            is_valid=False,
            error_message=(
                "I couldn't understand that date format. Please try one of these formats:\n"
                "- YYYY-MM-DD (e.g., 2024-12-31)\n"
                "- MM/DD/YYYY (e.g., 12/31/2024)\n"
                "- Natural language (e.g., 'next Friday', 'in 2 weeks', 'tomorrow')\n"
                "- Conversational (e.g., 'by the end of the month', 'in 5 days')"
            )
        )
    
    @classmethod
    def detect_ambiguity(cls, date_string: str) -> bool:
        """
        Detect if a date string is ambiguous.
        
        For example, "01/02/2024" could be Jan 2 or Feb 1.
        
        Args:
            date_string: The date string to check
            
        Returns:
            True if ambiguous, False otherwise
        """
        # Check for ambiguous numeric formats like 01/02/2024
        ambiguous_pattern = r'^\d{1,2}[/-]\d{1,2}[/-]\d{4}$'
        if re.match(ambiguous_pattern, date_string.strip()):
            parts = re.split(r'[/-]', date_string.strip())
            if len(parts) == 3:
                first, second = int(parts[0]), int(parts[1])
                # Ambiguous if both parts could be valid months
                if 1 <= first <= 12 and 1 <= second <= 12 and first != second:
                    return True
        return False


class DeadlineValidator:
    """
    Validator for project deadlines.
    
    Ensures deadlines are not in the past and are reasonable.
    """
    
    @classmethod
    def validate(cls, deadline: datetime) -> ValidationResult:
        """
        Validate a deadline datetime.
        
        Checks that the deadline is not in the past.
        
        Args:
            deadline: The deadline to validate
            
        Returns:
            ValidationResult indicating if deadline is valid
            
        Validates: Requirements 3.2
        """
        now = datetime.now()
        
        # Check if deadline is in the past
        if deadline < now:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"The deadline you provided ({deadline.strftime('%B %d, %Y')}) is in the past. "
                    "Please provide a future date for your project deadline."
                ),
                is_ambiguous=False
            )
        
        # Check if deadline is too far in the future (more than 5 years)
        max_future = now + timedelta(days=365 * 5)
        if deadline > max_future:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"The deadline you provided ({deadline.strftime('%B %d, %Y')}) is more than 5 years away. "
                    "Please provide a more reasonable deadline."
                ),
                is_ambiguous=False
            )
        
        # Check if deadline is very soon (within 24 hours) - ask for confirmation
        if deadline < now + timedelta(hours=24):
            return ValidationResult(
                is_valid=True,
                value=deadline,
                is_ambiguous=True,
                clarification_needed=(
                    f"Your deadline is set for {deadline.strftime('%B %d, %Y at %I:%M %p')}, "
                    "which is less than 24 hours away. Is this correct?"
                )
            )
        
        return ValidationResult(is_valid=True, value=deadline)


class ToneValidator:
    """
    Validator for communication tone preferences.
    
    Validates that the user's tone preference is one of the supported options.
    Enhanced to extract tone from conversational responses.
    """
    
    VALID_TONES = {"supportive", "direct", "casual"}
    
    # Synonyms for tone preferences with more conversational variations
    TONE_SYNONYMS = {
        "supportive": [
            "supportive", "encouraging", "friendly", "warm", "kind", "gentle",
            "nice", "positive", "motivating", "uplifting", "cheerful", "caring"
        ],
        "direct": [
            "direct", "straightforward", "blunt", "honest", "no-nonsense", 
            "professional", "business-like", "formal", "serious", "strict",
            "to the point", "concise", "brief"
        ],
        "casual": [
            "casual", "relaxed", "chill", "laid-back", "informal", "easygoing",
            "conversational", "friendly", "light", "fun", "playful", "cool"
        ],
    }
    
    # Conversational patterns that indicate tone preferences
    TONE_PATTERNS = {
        "supportive": [
            r'\b(?:be|sound|talk)\s+(?:more\s+)?(?:supportive|encouraging|friendly|warm|kind|nice)\b',
            r'\b(?:want|like|prefer)\s+(?:something\s+)?(?:supportive|encouraging|friendly|warm|positive)\b',
            r'\b(?:motivate|encourage|support)\s+me\b',
            r'\bhelp\s+me\s+stay\s+motivated\b',
        ],
        "direct": [
            r'\b(?:be|sound|talk)\s+(?:more\s+)?(?:direct|straightforward|blunt|honest|professional)\b',
            r'\b(?:want|like|prefer)\s+(?:something\s+)?(?:direct|straightforward|professional|formal)\b',
            r'\b(?:just|keep\s+it)\s+(?:straight|simple|brief|short)\b',
            r'\bget\s+to\s+the\s+point\b',
            r'\bno\s+(?:fluff|nonsense)\b',
        ],
        "casual": [
            r'\b(?:be|sound|talk)\s+(?:more\s+)?(?:casual|relaxed|chill|laid-back|informal)\b',
            r'\b(?:want|like|prefer)\s+(?:something\s+)?(?:casual|relaxed|informal|conversational)\b',
            r'\bkeep\s+it\s+(?:casual|light|fun|relaxed)\b',
            r'\bdon\'?t\s+be\s+too\s+(?:formal|serious)\b',
        ],
    }
    
    @classmethod
    def validate(cls, tone_input: str) -> ValidationResult:
        """
        Validate and normalize a tone preference.
        Enhanced to extract tone from conversational responses.
        
        Args:
            tone_input: The user's tone preference input
            
        Returns:
            ValidationResult with normalized tone or error
            
        Validates: Requirements 3.3
        """
        if not tone_input or not tone_input.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Please choose a communication tone: supportive, direct, or casual."
            )
        
        tone_input = tone_input.strip().lower()
        
        # Check if input matches a valid tone directly
        if tone_input in cls.VALID_TONES:
            return ValidationResult(is_valid=True, value=tone_input)
        
        # Check conversational patterns first (more specific)
        for tone, patterns in cls.TONE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, tone_input, re.IGNORECASE):
                    logger.info(f"Extracted tone '{tone}' from conversational input '{tone_input}'")
                    return ValidationResult(is_valid=True, value=tone)
        
        # Check synonyms
        for tone, synonyms in cls.TONE_SYNONYMS.items():
            if tone_input in synonyms:
                logger.info(f"Mapped tone input '{tone_input}' to '{tone}'")
                return ValidationResult(is_valid=True, value=tone)
        
        # Check if input contains a valid tone word or synonym
        for tone, synonyms in cls.TONE_SYNONYMS.items():
            for synonym in synonyms:
                if synonym in tone_input:
                    logger.info(f"Found tone '{tone}' from synonym '{synonym}' in '{tone_input}'")
                    return ValidationResult(is_valid=True, value=tone)
        
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"I didn't recognize '{tone_input}' as a tone preference. "
                "Please choose one of: supportive, direct, or casual.\n"
                "You can also describe what you want, like 'be encouraging' or 'keep it professional'."
            )
        )


class CheckinFrequencyParser:
    """
    Parser for check-in frequency preferences.
    
    Parses user input about how often they want check-ins.
    Enhanced to handle more natural language expressions.
    """
    
    # Valid frequency patterns with more conversational variations
    FREQUENCY_PATTERNS = {
        r'\b(daily|every\s*day|each\s*day)\b': 'daily',
        r'\b(twice\s*a?\s*week|2\s*times?\s*a?\s*week|two\s*times?\s*a?\s*week)\b': 'twice_weekly',
        r'\b(weekly|once\s*a?\s*week|every\s*week|each\s*week)\b': 'weekly',
        r'\b(bi-?weekly|every\s*2\s*weeks|every\s*two\s*weeks|twice\s*a?\s*month)\b': 'biweekly',
        r'\b(monthly|once\s*a?\s*month|every\s*month|each\s*month)\b': 'monthly',
    }
    
    # Conversational patterns that indicate frequency
    CONVERSATIONAL_PATTERNS = [
        (r'(?:check\s+in\s+with\s+me|message\s+me|contact\s+me)\s+(?:about\s+)?(\d+)\s*times?\s*(?:a|per)\s*(day|week|month)', 'numeric'),
        (r'(?:i\s+want|i\'d\s+like|prefer)\s+(?:to\s+)?(?:hear\s+from\s+you|get\s+messages)\s+(\d+)\s*times?\s*(?:a|per)\s*(day|week|month)', 'numeric'),
        (r'(?:every|each)\s+(?:other|2nd|second)\s+(day|week)', 'every_other'),
        (r'(?:a\s+)?(?:couple|few)\s+times?\s*(?:a|per)\s*(week|month)', 'few'),
    ]
    
    @classmethod
    def parse(cls, frequency_input: str) -> ValidationResult:
        """
        Parse check-in frequency from user input.
        Enhanced to handle more natural language expressions.
        
        Args:
            frequency_input: The user's frequency input
            
        Returns:
            ValidationResult with parsed frequency or error
            
        Validates: Requirements 3.4
        """
        if not frequency_input or not frequency_input.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Please tell me how often you'd like check-ins (e.g., daily, weekly, twice a week)."
            )
        
        original_input = frequency_input.strip()
        frequency_input = original_input.lower()
        
        # Try conversational patterns first (more specific)
        for pattern, pattern_type in cls.CONVERSATIONAL_PATTERNS:
            match = re.search(pattern, frequency_input, re.IGNORECASE)
            if match:
                if pattern_type == 'numeric':
                    count = int(match.group(1))
                    period = match.group(2)
                    frequency = f"{count}_per_{period}"
                    logger.info(f"Parsed conversational frequency '{original_input}' to '{frequency}'")
                    return ValidationResult(is_valid=True, value=frequency)
                elif pattern_type == 'every_other':
                    period = match.group(1)
                    if period == 'day':
                        frequency = 'every_other_day'
                    elif period == 'week':
                        frequency = 'biweekly'
                    logger.info(f"Parsed 'every other' frequency '{original_input}' to '{frequency}'")
                    return ValidationResult(is_valid=True, value=frequency)
                elif pattern_type == 'few':
                    period = match.group(1)
                    # "A few times" typically means 2-3 times
                    frequency = f"2_per_{period}"
                    logger.info(f"Parsed 'few times' frequency '{original_input}' to '{frequency}'")
                    return ValidationResult(is_valid=True, value=frequency)
        
        # Try to match against known patterns
        for pattern, frequency in cls.FREQUENCY_PATTERNS.items():
            if re.search(pattern, frequency_input, re.IGNORECASE):
                logger.info(f"Parsed frequency '{original_input}' to '{frequency}'")
                return ValidationResult(is_valid=True, value=frequency)
        
        # Check for numeric patterns like "3 times a week"
        numeric_pattern = r'(\d+)\s*times?\s*(?:a|per)\s*(week|month|day)'
        match = re.search(numeric_pattern, frequency_input, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            period = match.group(2)
            frequency = f"{count}_per_{period}"
            logger.info(f"Parsed numeric frequency '{original_input}' to '{frequency}'")
            return ValidationResult(is_valid=True, value=frequency)
        
        # Handle word numbers (one, two, three, etc.)
        word_numbers = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        word_numeric_pattern = r'(' + '|'.join(word_numbers.keys()) + r')\s*times?\s*(?:a|per)\s*(week|month|day)'
        match = re.search(word_numeric_pattern, frequency_input, re.IGNORECASE)
        if match:
            word = match.group(1).lower()
            count = word_numbers[word]
            period = match.group(2)
            frequency = f"{count}_per_{period}"
            logger.info(f"Parsed word-number frequency '{original_input}' to '{frequency}'")
            return ValidationResult(is_valid=True, value=frequency)
        
        return ValidationResult(
            is_valid=False,
            error_message=(
                f"I didn't understand '{original_input}' as a check-in frequency. "
                "Please use phrases like:\n"
                "- 'daily' or 'every day'\n"
                "- 'weekly' or 'once a week'\n"
                "- 'twice a week' or '2 times a week'\n"
                "- 'every other day'\n"
                "You can also say things like 'check in with me 3 times a week'."
            )
        )


class AmbiguityDetector:
    """
    Detector for ambiguous user inputs.
    
    Identifies when user input is unclear and needs clarification.
    Enhanced to detect more types of ambiguity and provide context-aware clarifications.
    """
    
    # Patterns that indicate ambiguous or unclear responses
    AMBIGUOUS_PATTERNS = [
        r'^\s*maybe\s*$',
        r'^\s*idk\s*$',
        r'^\s*i\s*don\'?t\s*know\s*$',
        r'^\s*not\s*sure\s*$',
        r'^\s*dunno\s*$',
        r'^\s*\?\s*$',
        r'^\s*(?:um|uh|hmm|err)\s*$',
        r'^\s*whatever\s*$',
        r'^\s*anything\s*$',
        r'^\s*doesn\'?t\s*matter\s*$',
    ]
    
    # Patterns that indicate uncertainty within a longer response
    UNCERTAINTY_INDICATORS = [
        r'\b(?:maybe|perhaps|possibly|probably|i\s+think|i\s+guess|not\s+sure)\b',
        r'\b(?:kind\s+of|sort\s+of|kinda|sorta)\b',
        r'\b(?:or\s+something|or\s+whatever)\b',
    ]
    
    # Very short responses that might be unclear
    MIN_MEANINGFUL_LENGTH = 2
    
    @classmethod
    def is_ambiguous(cls, user_input: str, context: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Detect if user input is ambiguous or unclear.
        Enhanced with context-aware clarification messages.
        
        Args:
            user_input: The user's input to check
            context: Optional context about what information is being collected
            
        Returns:
            Tuple of (is_ambiguous, clarification_message)
            
        Validates: Requirements 3.3
        """
        if not user_input or not user_input.strip():
            clarification = "I didn't receive a response. Could you please provide an answer?"
            if context:
                clarification = f"I didn't receive a response. Could you please tell me {context}?"
            return True, clarification
        
        user_input_lower = user_input.strip().lower()
        
        # Check for ambiguous patterns (exact matches)
        for pattern in cls.AMBIGUOUS_PATTERNS:
            if re.match(pattern, user_input_lower, re.IGNORECASE):
                clarification = "I see you're not sure. Would you like some examples or suggestions?"
                if context:
                    clarification = f"I see you're not sure about {context}. Would you like some examples or suggestions?"
                return True, clarification
        
        # Check for very short responses (might be typos or unclear)
        if len(user_input.strip()) < cls.MIN_MEANINGFUL_LENGTH:
            return True, "That response seems very short. Could you provide a bit more detail?"
        
        # Check for uncertainty indicators in longer responses
        # Count total matches, not just patterns
        uncertainty_count = 0
        for pattern in cls.UNCERTAINTY_INDICATORS:
            matches = re.findall(pattern, user_input_lower, re.IGNORECASE)
            uncertainty_count += len(matches)
        
        # If multiple uncertainty indicators, ask for clarification
        if uncertainty_count >= 2:
            clarification = "It sounds like you're uncertain. Would you like to think about it and come back to this?"
            if context:
                clarification = f"It sounds like you're uncertain about {context}. Would you like some help deciding?"
            return True, clarification
        
        return False, None
    
    @classmethod
    def detect_date_ambiguity(cls, date_string: str, parsed_date: datetime) -> Tuple[bool, Optional[str]]:
        """
        Detect if a parsed date might be ambiguous.
        
        Args:
            date_string: The original date string
            parsed_date: The parsed datetime
            
        Returns:
            Tuple of (is_ambiguous, clarification_message)
        """
        if DateParser.detect_ambiguity(date_string):
            return True, (
                f"I parsed your date as {parsed_date.strftime('%B %d, %Y')}. "
                "Is this correct? (If not, please use YYYY-MM-DD format to avoid ambiguity)"
            )
        return False, None
    
    @classmethod
    def detect_multiple_intents(cls, user_input: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if user input contains multiple pieces of information or intents.
        
        This helps identify when a user is trying to provide multiple answers at once,
        which might need to be broken down.
        
        Args:
            user_input: The user's input to check
            
        Returns:
            Tuple of (has_multiple_intents, clarification_message)
        """
        if not user_input or not user_input.strip():
            return False, None
        
        # Check for common separators that indicate multiple pieces of info
        # Count total occurrences of all separators
        separators = [' and ', ' & ', ', and ', '; ', ' also ', ' plus ']
        separator_count = sum(user_input.lower().count(sep) for sep in separators)
        
        if separator_count >= 2:
            return True, (
                "It looks like you're providing multiple pieces of information. "
                "Let's take them one at a time. Could you focus on just the first part?"
            )
        
        return False, None


def validate_project_name(name: str) -> ValidationResult:
    """
    Validate a project name.
    
    Args:
        name: The project name to validate
        
    Returns:
        ValidationResult indicating if name is valid
    """
    if not name or not name.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Please provide a name for your project."
        )
    
    # Strip whitespace and check length of stripped version
    stripped_name = name.strip()
    
    # Check minimum length on stripped name
    if len(stripped_name) < 2:
        return ValidationResult(
            is_valid=False,
            error_message="Project name should be at least 2 characters long."
        )
    
    # Check maximum length on stripped name
    if len(stripped_name) > 200:
        return ValidationResult(
            is_valid=False,
            error_message="Project name should be less than 200 characters."
        )
    
    return ValidationResult(is_valid=True, value=stripped_name)


def validate_project_goal(goal: str) -> ValidationResult:
    """
    Validate a project goal/description.
    
    Args:
        goal: The project goal to validate
        
    Returns:
        ValidationResult indicating if goal is valid
    """
    if not goal or not goal.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Please provide a goal or description for your project."
        )
    
    goal = goal.strip()
    
    # Check minimum length
    if len(goal) < 5:
        return ValidationResult(
            is_valid=False,
            error_message="Project goal should be at least 5 characters long. Please provide more detail."
        )
    
    # Check maximum length
    if len(goal) > 2000:
        return ValidationResult(
            is_valid=False,
            error_message="Project goal should be less than 2000 characters."
        )
    
    return ValidationResult(is_valid=True, value=goal)
