"""
Property-based tests for input validation during onboarding.

Feature: discord-dm-onboarding, Property 7: Input validation
Validates: Requirements 3.1, 3.2
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime, timedelta

from app.services.input_validators import (
    DateParser,
    DeadlineValidator,
    ToneValidator,
    CheckinFrequencyParser,
    AmbiguityDetector,
    validate_project_name,
    validate_project_goal,
    ValidationResult,
)


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def past_dates(draw):
    """Generate dates in the past."""
    days_ago = draw(st.integers(min_value=1, max_value=365 * 5))
    past_date = datetime.now() - timedelta(days=days_ago)
    return past_date


@st.composite
def future_dates(draw):
    """Generate dates in the future (but not too far)."""
    days_ahead = draw(st.integers(min_value=1, max_value=365 * 4))
    future_date = datetime.now() + timedelta(days=days_ahead)
    return future_date


@st.composite
def very_far_future_dates(draw):
    """Generate dates more than 5 years in the future."""
    days_ahead = draw(st.integers(min_value=365 * 5 + 1, max_value=365 * 10))
    far_future_date = datetime.now() + timedelta(days=days_ahead)
    return far_future_date


@st.composite
def valid_date_strings(draw):
    """Generate valid date strings in various formats."""
    formats = [
        "2024-12-31",
        "12/31/2024",
        "December 31, 2024",
        "Dec 31, 2024",
        "tomorrow",
        "next week",
        "in 2 weeks",
        "next month",
    ]
    return draw(st.sampled_from(formats))


@st.composite
def invalid_date_strings(draw):
    """Generate invalid date strings."""
    invalid_dates = [
        "not a date",
        "xyz123",
        "13/45/2024",  # Invalid month/day
        "2024-13-01",  # Invalid month
        "abc def ghi",
        "!!!",
        "00/00/0000",
    ]
    return draw(st.sampled_from(invalid_dates))


@st.composite
def valid_tone_inputs(draw):
    """Generate valid tone preference inputs."""
    valid_tones = [
        "supportive", "encouraging", "friendly", "warm",
        "direct", "straightforward", "professional",
        "casual", "relaxed", "chill", "laid-back",
    ]
    return draw(st.sampled_from(valid_tones))


@st.composite
def invalid_tone_inputs(draw):
    """Generate invalid tone preference inputs."""
    invalid_tones = [
        "angry", "mean", "rude", "sarcastic",
        "xyz", "123", "!!!",
        "not a tone", "whatever",
    ]
    return draw(st.sampled_from(invalid_tones))


@st.composite
def valid_frequency_inputs(draw):
    """Generate valid check-in frequency inputs."""
    valid_frequencies = [
        "daily", "every day",
        "weekly", "once a week", "every week",
        "twice a week", "2 times a week",
        "biweekly", "every 2 weeks",
        "monthly", "once a month",
    ]
    return draw(st.sampled_from(valid_frequencies))


@st.composite
def invalid_frequency_inputs(draw):
    """Generate invalid check-in frequency inputs."""
    invalid_frequencies = [
        "never", "sometimes", "whenever",
        "xyz", "123", "!!!",
        "not a frequency",
    ]
    return draw(st.sampled_from(invalid_frequencies))


# ============================================================================
# Property Tests for Date Parsing
# ============================================================================

@settings(max_examples=100)
@given(date_string=invalid_date_strings())
def test_invalid_date_strings_are_rejected(date_string):
    """
    Property 7: Input validation
    
    For any invalid date string, the DateParser should return a ValidationResult
    with is_valid=False and provide an error message with format examples.
    
    This ensures that malformed dates trigger clarification requests.
    
    Validates: Requirements 3.1
    """
    result = DateParser.parse(date_string)
    
    # Invalid dates should be rejected
    assert not result.is_valid, \
        f"Invalid date string '{date_string}' should be rejected"
    
    # Should provide an error message
    assert result.error_message is not None, \
        "Error message should be provided for invalid dates"
    
    # Error message should contain format examples
    assert any(keyword in result.error_message.lower() for keyword in ["format", "example", "try"]), \
        "Error message should provide format examples or suggestions"


@settings(max_examples=100)
@given(date_string=valid_date_strings())
def test_valid_date_strings_are_parsed(date_string):
    """
    Property 7: Input validation
    
    For any valid date string, the DateParser should return a ValidationResult
    with is_valid=True and a parsed datetime value.
    
    Validates: Requirements 3.1
    """
    result = DateParser.parse(date_string)
    
    # Valid dates should be accepted
    assert result.is_valid, \
        f"Valid date string '{date_string}' should be accepted"
    
    # Should provide a parsed datetime value
    assert result.value is not None, \
        "Parsed datetime value should be provided"
    
    assert isinstance(result.value, datetime), \
        "Parsed value should be a datetime object"


def test_empty_date_string_is_rejected():
    """
    Property 7: Input validation
    
    Empty or whitespace-only date strings should be rejected.
    
    Validates: Requirements 3.1
    """
    for empty_input in ["", "   ", "\t", "\n"]:
        result = DateParser.parse(empty_input)
        assert not result.is_valid, \
            f"Empty input '{repr(empty_input)}' should be rejected"
        assert result.error_message is not None


# ============================================================================
# Property Tests for Deadline Validation
# ============================================================================

@settings(max_examples=100)
@given(past_date=past_dates())
def test_past_deadlines_are_rejected(past_date):
    """
    Property 7: Input validation
    
    For any deadline in the past, the DeadlineValidator should return
    a ValidationResult with is_valid=False and an error message explaining
    that past dates are not allowed.
    
    This ensures that past deadlines trigger clarification requests without
    advancing the onboarding state.
    
    Validates: Requirements 3.2
    """
    result = DeadlineValidator.validate(past_date)
    
    # Past deadlines should be rejected
    assert not result.is_valid, \
        f"Past deadline {past_date} should be rejected"
    
    # Should provide an error message
    assert result.error_message is not None, \
        "Error message should be provided for past deadlines"
    
    # Error message should mention that the date is in the past
    assert any(keyword in result.error_message.lower() for keyword in ["past", "future"]), \
        "Error message should explain that past dates are not allowed"


@settings(max_examples=100)
@given(future_date=future_dates())
def test_future_deadlines_are_accepted(future_date):
    """
    Property 7: Input validation
    
    For any reasonable future deadline (within 5 years), the DeadlineValidator
    should return a ValidationResult with is_valid=True.
    
    Validates: Requirements 3.2
    """
    # Skip dates that are too close (within 24 hours) as they trigger confirmation
    assume((future_date - datetime.now()).total_seconds() > 24 * 3600)
    
    result = DeadlineValidator.validate(future_date)
    
    # Future deadlines should be accepted
    assert result.is_valid, \
        f"Future deadline {future_date} should be accepted"
    
    # Should provide the validated value
    assert result.value is not None, \
        "Validated deadline value should be provided"


@settings(max_examples=100)
@given(far_future_date=very_far_future_dates())
def test_very_far_future_deadlines_are_rejected(far_future_date):
    """
    Property 7: Input validation
    
    For any deadline more than 5 years in the future, the DeadlineValidator
    should return a ValidationResult with is_valid=False.
    
    Validates: Requirements 3.2
    """
    result = DeadlineValidator.validate(far_future_date)
    
    # Very far future deadlines should be rejected
    assert not result.is_valid, \
        f"Deadline {far_future_date} (more than 5 years away) should be rejected"
    
    # Should provide an error message
    assert result.error_message is not None, \
        "Error message should be provided for very far future deadlines"


def test_imminent_deadlines_trigger_confirmation():
    """
    Property 7: Input validation
    
    Deadlines within 24 hours should be marked as ambiguous and require confirmation.
    
    Validates: Requirements 3.2
    """
    imminent_deadline = datetime.now() + timedelta(hours=12)
    result = DeadlineValidator.validate(imminent_deadline)
    
    # Should be valid but ambiguous
    assert result.is_valid, \
        "Imminent deadline should be valid"
    
    assert result.is_ambiguous, \
        "Imminent deadline should be marked as ambiguous"
    
    assert result.clarification_needed is not None, \
        "Clarification message should be provided for imminent deadlines"


# ============================================================================
# Property Tests for Tone Validation
# ============================================================================

@settings(max_examples=100)
@given(tone_input=valid_tone_inputs())
def test_valid_tone_inputs_are_accepted(tone_input):
    """
    Property 7: Input validation
    
    For any valid tone preference input (including synonyms), the ToneValidator
    should return a ValidationResult with is_valid=True and a normalized tone value.
    
    Validates: Requirements 3.3
    """
    result = ToneValidator.validate(tone_input)
    
    # Valid tones should be accepted
    assert result.is_valid, \
        f"Valid tone input '{tone_input}' should be accepted"
    
    # Should provide a normalized tone value
    assert result.value is not None, \
        "Normalized tone value should be provided"
    
    # Normalized value should be one of the valid tones
    assert result.value in ToneValidator.VALID_TONES, \
        f"Normalized tone '{result.value}' should be in VALID_TONES"


@settings(max_examples=100)
@given(tone_input=invalid_tone_inputs())
def test_invalid_tone_inputs_are_rejected(tone_input):
    """
    Property 7: Input validation
    
    For any invalid tone preference input, the ToneValidator should return
    a ValidationResult with is_valid=False and an error message listing
    the valid options.
    
    Validates: Requirements 3.3
    """
    result = ToneValidator.validate(tone_input)
    
    # Invalid tones should be rejected
    assert not result.is_valid, \
        f"Invalid tone input '{tone_input}' should be rejected"
    
    # Should provide an error message
    assert result.error_message is not None, \
        "Error message should be provided for invalid tones"
    
    # Error message should list valid options
    assert any(tone in result.error_message.lower() for tone in ["supportive", "direct", "casual"]), \
        "Error message should list valid tone options"


def test_empty_tone_input_is_rejected():
    """
    Property 7: Input validation
    
    Empty or whitespace-only tone inputs should be rejected.
    
    Validates: Requirements 3.3
    """
    for empty_input in ["", "   ", "\t", "\n"]:
        result = ToneValidator.validate(empty_input)
        assert not result.is_valid, \
            f"Empty tone input '{repr(empty_input)}' should be rejected"
        assert result.error_message is not None


# ============================================================================
# Property Tests for Check-in Frequency Parsing
# ============================================================================

@settings(max_examples=100)
@given(frequency_input=valid_frequency_inputs())
def test_valid_frequency_inputs_are_parsed(frequency_input):
    """
    Property 7: Input validation
    
    For any valid check-in frequency input, the CheckinFrequencyParser should
    return a ValidationResult with is_valid=True and a parsed frequency value.
    
    Validates: Requirements 3.4
    """
    result = CheckinFrequencyParser.parse(frequency_input)
    
    # Valid frequencies should be accepted
    assert result.is_valid, \
        f"Valid frequency input '{frequency_input}' should be accepted"
    
    # Should provide a parsed frequency value
    assert result.value is not None, \
        "Parsed frequency value should be provided"
    
    assert isinstance(result.value, str), \
        "Parsed frequency should be a string"


@settings(max_examples=100)
@given(frequency_input=invalid_frequency_inputs())
def test_invalid_frequency_inputs_are_rejected(frequency_input):
    """
    Property 7: Input validation
    
    For any invalid check-in frequency input, the CheckinFrequencyParser should
    return a ValidationResult with is_valid=False and an error message with examples.
    
    Validates: Requirements 3.4
    """
    result = CheckinFrequencyParser.parse(frequency_input)
    
    # Invalid frequencies should be rejected
    assert not result.is_valid, \
        f"Invalid frequency input '{frequency_input}' should be rejected"
    
    # Should provide an error message
    assert result.error_message is not None, \
        "Error message should be provided for invalid frequencies"
    
    # Error message should provide examples
    assert any(keyword in result.error_message.lower() for keyword in ["daily", "weekly", "example"]), \
        "Error message should provide frequency examples"


def test_empty_frequency_input_is_rejected():
    """
    Property 7: Input validation
    
    Empty or whitespace-only frequency inputs should be rejected.
    
    Validates: Requirements 3.4
    """
    for empty_input in ["", "   ", "\t", "\n"]:
        result = CheckinFrequencyParser.parse(empty_input)
        assert not result.is_valid, \
            f"Empty frequency input '{repr(empty_input)}' should be rejected"
        assert result.error_message is not None


# ============================================================================
# Property Tests for Ambiguity Detection
# ============================================================================

@settings(max_examples=100)
@given(user_input=st.text(min_size=10, max_size=200))
def test_meaningful_inputs_are_not_ambiguous(user_input):
    """
    Property 7: Input validation
    
    For any meaningful user input (not matching ambiguous patterns),
    the AmbiguityDetector should not flag it as ambiguous.
    
    Validates: Requirements 3.3
    """
    # Skip inputs that match known ambiguous patterns
    ambiguous_keywords = ["maybe", "idk", "don't know", "not sure", "dunno"]
    assume(not any(keyword in user_input.lower() for keyword in ambiguous_keywords))
    assume(len(user_input.strip()) >= 2)
    
    is_ambiguous, clarification = AmbiguityDetector.is_ambiguous(user_input)
    
    # Meaningful inputs should not be flagged as ambiguous
    assert not is_ambiguous, \
        f"Meaningful input '{user_input}' should not be flagged as ambiguous"


def test_ambiguous_patterns_are_detected():
    """
    Property 7: Input validation
    
    Known ambiguous patterns should be detected by the AmbiguityDetector.
    
    Validates: Requirements 3.3
    """
    ambiguous_inputs = [
        "maybe", "idk", "i don't know", "not sure", "dunno", "?",
        "", "   ", "a", "x"
    ]
    
    for ambiguous_input in ambiguous_inputs:
        is_ambiguous, clarification = AmbiguityDetector.is_ambiguous(ambiguous_input)
        
        assert is_ambiguous, \
            f"Ambiguous input '{ambiguous_input}' should be detected"
        
        assert clarification is not None, \
            f"Clarification message should be provided for '{ambiguous_input}'"


# ============================================================================
# Property Tests for Project Name Validation
# ============================================================================

@settings(max_examples=100)
@given(name=st.text(min_size=2, max_size=200))
def test_valid_project_names_are_accepted(name):
    """
    Property 7: Input validation
    
    For any project name between 2 and 200 characters, validation should succeed.
    
    Validates: Requirements 3.1
    """
    # Skip names that are only whitespace or too short after stripping
    assume(name.strip())
    assume(len(name.strip()) >= 2)
    
    result = validate_project_name(name)
    
    assert result.is_valid, \
        f"Valid project name '{name}' should be accepted"
    
    assert result.value is not None, \
        "Validated project name should be provided"


@settings(max_examples=100)
@given(name=st.text(min_size=201, max_size=500))
def test_too_long_project_names_are_rejected(name):
    """
    Property 7: Input validation
    
    For any project name longer than 200 characters, validation should fail.
    
    Validates: Requirements 3.1
    """
    result = validate_project_name(name)
    
    assert not result.is_valid, \
        f"Project name with {len(name)} characters should be rejected"
    
    assert result.error_message is not None, \
        "Error message should be provided for too-long names"


def test_empty_project_names_are_rejected():
    """
    Property 7: Input validation
    
    Empty or whitespace-only project names should be rejected.
    
    Validates: Requirements 3.1
    """
    for empty_input in ["", "   ", "\t", "\n", " "]:
        result = validate_project_name(empty_input)
        assert not result.is_valid, \
            f"Empty project name '{repr(empty_input)}' should be rejected"
        assert result.error_message is not None


def test_very_short_project_names_are_rejected():
    """
    Property 7: Input validation
    
    Project names shorter than 2 characters should be rejected.
    
    Validates: Requirements 3.1
    """
    for short_name in ["a", "x", "1"]:
        result = validate_project_name(short_name)
        assert not result.is_valid, \
            f"Short project name '{short_name}' should be rejected"
        assert result.error_message is not None


# ============================================================================
# Property Tests for Project Goal Validation
# ============================================================================

@settings(max_examples=100)
@given(goal=st.text(min_size=5, max_size=2000))
def test_valid_project_goals_are_accepted(goal):
    """
    Property 7: Input validation
    
    For any project goal between 5 and 2000 characters (after stripping), validation should succeed.
    
    Validates: Requirements 3.1
    """
    # Skip goals that are only whitespace or become too short after stripping
    assume(goal.strip() and len(goal.strip()) >= 5)
    
    result = validate_project_goal(goal)
    
    assert result.is_valid, \
        f"Valid project goal should be accepted"
    
    assert result.value is not None, \
        "Validated project goal should be provided"


@settings(max_examples=50, suppress_health_check=[HealthCheck.large_base_example])
@given(goal=st.text(min_size=2001, max_size=3000).filter(lambda g: len(g.strip()) > 2000))
def test_too_long_project_goals_are_rejected(goal):
    """
    Property 7: Input validation
    
    For any project goal longer than 2000 characters (after stripping), validation should fail.
    
    Validates: Requirements 3.1
    """
    result = validate_project_goal(goal)
    
    assert not result.is_valid, \
        f"Project goal with {len(goal.strip())} characters (stripped) should be rejected"
    
    assert result.error_message is not None, \
        "Error message should be provided for too-long goals"


def test_empty_project_goals_are_rejected():
    """
    Property 7: Input validation
    
    Empty or whitespace-only project goals should be rejected.
    
    Validates: Requirements 3.1
    """
    for empty_input in ["", "   ", "\t", "\n"]:
        result = validate_project_goal(empty_input)
        assert not result.is_valid, \
            f"Empty project goal '{repr(empty_input)}' should be rejected"
        assert result.error_message is not None


def test_very_short_project_goals_are_rejected():
    """
    Property 7: Input validation
    
    Project goals shorter than 5 characters should be rejected.
    
    Validates: Requirements 3.1
    """
    for short_goal in ["a", "ab", "abc", "abcd"]:
        result = validate_project_goal(short_goal)
        assert not result.is_valid, \
            f"Short project goal '{short_goal}' should be rejected"
        assert result.error_message is not None


# ============================================================================
# Tests for Enhanced Natural Language Parsing (Task 25)
# ============================================================================

def test_conversational_date_extraction():
    """
    Test that dates can be extracted from conversational phrases.
    
    Enhanced natural language parsing should handle phrases like:
    - "I need it by Friday"
    - "deadline is next month"
    - "finish by the end of the week"
    
    Validates: Requirements 3.1
    """
    conversational_dates = [
        "I need it by tomorrow",
        "deadline is next week",
        "finish by next month",
        "complete it by the end of the month",
        "I want to finish in 2 weeks",
    ]
    
    for date_phrase in conversational_dates:
        result = DateParser.parse(date_phrase)
        assert result.is_valid, \
            f"Conversational date phrase '{date_phrase}' should be parsed successfully"
        assert result.value is not None, \
            f"Should extract date from '{date_phrase}'"
        assert isinstance(result.value, datetime), \
            "Extracted value should be a datetime"


def test_numeric_relative_dates():
    """
    Test that numeric relative dates are parsed correctly.
    
    Enhanced parsing should handle:
    - "in 5 days"
    - "in 3 weeks"
    - "in 2 months"
    
    Validates: Requirements 3.1
    """
    test_cases = [
        ("in 5 days", 5),
        ("in 3 weeks", 21),
        ("in 2 months", 60),
        ("within 10 days", 10),
    ]
    
    for date_string, expected_days in test_cases:
        result = DateParser.parse(date_string)
        assert result.is_valid, \
            f"Numeric relative date '{date_string}' should be parsed"
        
        # Check that the parsed date is approximately correct
        days_diff = (result.value - datetime.now()).days
        assert abs(days_diff - expected_days) <= 1, \
            f"'{date_string}' should be approximately {expected_days} days from now"


def test_extended_relative_keywords():
    """
    Test that extended relative keywords are recognized.
    
    Enhanced parsing includes:
    - "end of the week"
    - "middle of next week"
    - "beginning of next month"
    
    Validates: Requirements 3.1
    """
    extended_keywords = [
        "end of the week",
        "end of the month",
        "middle of next week",
        "beginning of next month",
        "start of next month",
    ]
    
    for keyword in extended_keywords:
        result = DateParser.parse(keyword)
        assert result.is_valid, \
            f"Extended relative keyword '{keyword}' should be parsed"
        assert result.value > datetime.now(), \
            f"'{keyword}' should result in a future date"


def test_conversational_tone_extraction():
    """
    Test that tone preferences can be extracted from conversational responses.
    
    Enhanced tone validation should handle:
    - "I want something supportive"
    - "Be direct with me"
    - "Keep it casual"
    - "Help me stay motivated"
    
    Validates: Requirements 3.3
    """
    conversational_tones = [
        ("I want something supportive", "supportive"),
        ("Be direct with me", "direct"),
        ("Keep it casual", "casual"),
        ("Help me stay motivated", "supportive"),
        ("Just be straightforward", "direct"),
        ("I prefer something encouraging", "supportive"),
        ("Keep it professional", "direct"),
        ("Be relaxed and chill", "casual"),
    ]
    
    for tone_phrase, expected_tone in conversational_tones:
        result = ToneValidator.validate(tone_phrase)
        assert result.is_valid, \
            f"Conversational tone phrase '{tone_phrase}' should be recognized"
        assert result.value == expected_tone, \
            f"'{tone_phrase}' should map to '{expected_tone}', got '{result.value}'"


def test_expanded_tone_synonyms():
    """
    Test that expanded tone synonyms are recognized.
    
    Enhanced tone validation includes more synonyms:
    - "nice", "positive", "motivating" -> supportive
    - "business-like", "formal", "to the point" -> direct
    - "fun", "playful", "cool" -> casual
    
    Validates: Requirements 3.3
    """
    expanded_synonyms = [
        ("nice", "supportive"),
        ("positive", "supportive"),
        ("motivating", "supportive"),
        ("business-like", "direct"),
        ("formal", "direct"),
        ("fun", "casual"),
        ("playful", "casual"),
        ("cool", "casual"),
    ]
    
    for synonym, expected_tone in expanded_synonyms:
        result = ToneValidator.validate(synonym)
        assert result.is_valid, \
            f"Tone synonym '{synonym}' should be recognized"
        assert result.value == expected_tone, \
            f"'{synonym}' should map to '{expected_tone}'"


def test_conversational_frequency_extraction():
    """
    Test that check-in frequencies can be extracted from conversational responses.
    
    Enhanced frequency parsing should handle:
    - "Check in with me 3 times a week"
    - "I want to hear from you every other day"
    - "Message me a couple times a week"
    
    Validates: Requirements 3.4
    """
    conversational_frequencies = [
        ("Check in with me 3 times a week", "3_per_week"),
        ("I want to hear from you daily", "daily"),
        ("Message me every other day", "every_other_day"),
        ("Contact me a couple times a week", "2_per_week"),
        ("I'd like to get messages twice a week", "twice_weekly"),
    ]
    
    for freq_phrase, expected_freq in conversational_frequencies:
        result = CheckinFrequencyParser.parse(freq_phrase)
        assert result.is_valid, \
            f"Conversational frequency phrase '{freq_phrase}' should be parsed"
        assert result.value == expected_freq, \
            f"'{freq_phrase}' should map to '{expected_freq}', got '{result.value}'"


def test_word_number_frequencies():
    """
    Test that word numbers are recognized in frequency expressions.
    
    Enhanced parsing should handle:
    - "three times a week"
    - "five times a month"
    
    Note: "two times a week" matches the existing "twice a week" pattern,
    which is acceptable behavior.
    
    Validates: Requirements 3.4
    """
    word_number_frequencies = [
        ("three times a week", "3_per_week"),
        ("four times a week", "4_per_week"),
        ("five times a month", "5_per_month"),
    ]
    
    for freq_phrase, expected_freq in word_number_frequencies:
        result = CheckinFrequencyParser.parse(freq_phrase)
        assert result.is_valid, \
            f"Word number frequency '{freq_phrase}' should be parsed"
        assert result.value == expected_freq, \
            f"'{freq_phrase}' should map to '{expected_freq}'"


def test_enhanced_ambiguity_detection():
    """
    Test that enhanced ambiguity detection catches more patterns.
    
    Enhanced detection should recognize:
    - "um", "uh", "hmm"
    - "whatever", "anything", "doesn't matter"
    - Multiple uncertainty indicators
    
    Validates: Requirements 3.3
    """
    ambiguous_inputs = [
        "um",
        "uh",
        "hmm",
        "whatever",
        "anything",
        "doesn't matter",
        "maybe I think probably",  # Multiple uncertainty indicators
    ]
    
    for ambiguous_input in ambiguous_inputs:
        is_ambiguous, clarification = AmbiguityDetector.is_ambiguous(ambiguous_input)
        assert is_ambiguous, \
            f"Enhanced ambiguity detection should catch '{ambiguous_input}'"
        assert clarification is not None, \
            f"Clarification should be provided for '{ambiguous_input}'"


def test_context_aware_clarification():
    """
    Test that ambiguity detection provides context-aware clarifications.
    
    When context is provided, clarification messages should reference it.
    
    Validates: Requirements 3.3
    """
    is_ambiguous, clarification = AmbiguityDetector.is_ambiguous(
        "idk", 
        context="your project deadline"
    )
    
    assert is_ambiguous, "Should detect ambiguity"
    assert "deadline" in clarification.lower(), \
        "Clarification should reference the context"


def test_multiple_intent_detection():
    """
    Test that multiple intents in a single response are detected.
    
    Enhanced detection should identify when users provide multiple pieces
    of information at once.
    
    Validates: Requirements 3.3
    """
    multiple_intent_inputs = [
        "I want daily check-ins and also a supportive tone and my deadline is next week",
        "My project is called X and the goal is Y and I need it by Friday",
    ]
    
    for multi_input in multiple_intent_inputs:
        has_multiple, clarification = AmbiguityDetector.detect_multiple_intents(multi_input)
        assert has_multiple, \
            f"Should detect multiple intents in '{multi_input}'"
        assert clarification is not None, \
            "Should provide clarification for multiple intents"
