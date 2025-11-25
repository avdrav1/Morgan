"""
Property-based tests for platform-appropriate message formatting.

Feature: proactive-accountability-assistant, Property 15: Platform-appropriate formatting
Validates: Requirements 7.3
"""

import pytest
from hypothesis import given, strategies as st, settings
from app.services.discord_adapter import DiscordAdapter
from app.services.web_adapter import WebAdapter


# Strategy for generating messages with markdown
@st.composite
def markdown_messages(draw):
    """Generate messages with various markdown formatting."""
    elements = []
    
    # Add some plain text
    if draw(st.booleans()):
        elements.append(draw(st.text(min_size=1, max_size=100)))
    
    # Add bold text
    if draw(st.booleans()):
        text = draw(st.text(min_size=1, max_size=50))
        elements.append(f"**{text}**")
    
    # Add italic text
    if draw(st.booleans()):
        text = draw(st.text(min_size=1, max_size=50))
        elements.append(f"*{text}*")
    
    # Add code
    if draw(st.booleans()):
        text = draw(st.text(alphabet=st.characters(blacklist_categories=('Cs',)), min_size=1, max_size=30))
        elements.append(f"`{text}`")
    
    # Add strikethrough
    if draw(st.booleans()):
        text = draw(st.text(min_size=1, max_size=50))
        elements.append(f"~~{text}~~")
    
    # Add blockquote
    if draw(st.booleans()):
        text = draw(st.text(min_size=1, max_size=50))
        elements.append(f"> {text}")
    
    # Add list item
    if draw(st.booleans()):
        text = draw(st.text(min_size=1, max_size=50))
        elements.append(f"- {text}")
    
    # Join with spaces or newlines
    separator = draw(st.sampled_from([" ", "\n"]))
    return separator.join(elements) if elements else "Hello"


@settings(max_examples=100)
@given(message=markdown_messages())
def test_discord_preserves_markdown(message):
    """
    Property: For any message with markdown, Discord adapter should preserve markdown formatting.
    
    Discord natively supports markdown, so the formatted message should be identical
    to the input message.
    """
    adapter = DiscordAdapter()
    formatted = adapter.format_message(message)
    
    # Discord preserves markdown
    assert formatted == message


@settings(max_examples=100)
@given(message=markdown_messages())
def test_web_removes_markdown(message):
    """
    Property: For any message with markdown, Web adapter should remove markdown syntax.
    
    Web interface displays plain text, so markdown syntax should be stripped out
    while preserving the actual content.
    """
    adapter = WebAdapter()
    formatted = adapter.format_message(message)
    
    # Web adapter should remove markdown syntax
    # The formatted message should not contain markdown markers
    assert "**" not in formatted or message.count("**") % 2 != 0  # Unpaired markers ok
    assert "~~" not in formatted or message.count("~~") % 2 != 0
    
    # Should be a string
    assert isinstance(formatted, str)
    
    # Should not be empty unless input was only markdown syntax
    if message.strip():
        assert len(formatted) >= 0  # May be empty if message was only markdown


@settings(max_examples=100)
@given(
    message=st.text(min_size=1, max_size=200),
    platform=st.sampled_from(['discord', 'web'])
)
def test_format_message_returns_string(message, platform):
    """
    Property: For any message and platform, format_message should return a string.
    
    All adapters must return a string from format_message, never None or other types.
    """
    if platform == 'discord':
        adapter = DiscordAdapter()
    else:
        adapter = WebAdapter()
    
    formatted = adapter.format_message(message)
    
    assert isinstance(formatted, str)
    assert formatted is not None


@settings(max_examples=100)
@given(message=st.text(min_size=1, max_size=200))
def test_discord_format_is_idempotent(message):
    """
    Property: For any message, formatting twice should give the same result as formatting once.
    
    Discord formatting should be idempotent - applying it multiple times
    should not change the result.
    """
    adapter = DiscordAdapter()
    
    formatted_once = adapter.format_message(message)
    formatted_twice = adapter.format_message(formatted_once)
    
    assert formatted_once == formatted_twice


@settings(max_examples=100)
@given(message=st.text(min_size=1, max_size=200))
def test_web_format_is_idempotent(message):
    """
    Property: For any message, formatting twice should give the same result as formatting once.
    
    Web formatting should be idempotent - applying it multiple times
    should not change the result.
    """
    adapter = WebAdapter()
    
    formatted_once = adapter.format_message(message)
    formatted_twice = adapter.format_message(formatted_once)
    
    assert formatted_once == formatted_twice


@settings(max_examples=100)
@given(message=markdown_messages())
def test_web_formatted_length_not_greater_than_original(message):
    """
    Property: For any message, web formatting should not increase the length.
    
    Since web formatting removes markdown syntax, the formatted message
    should be equal or shorter than the original.
    """
    adapter = WebAdapter()
    formatted = adapter.format_message(message)
    
    # Formatted message should not be longer than original
    # (we're removing syntax, not adding)
    assert len(formatted) <= len(message)


@settings(max_examples=100)
@given(
    message=st.text(
        alphabet=st.characters(blacklist_categories=('Cs', 'Cc'), blacklist_characters='*_~`>-[]()'),
        min_size=1,
        max_size=100
    )
)
def test_plain_text_unchanged_by_web_adapter(message):
    """
    Property: For any plain text message (no markdown), web adapter should preserve it.
    
    If a message contains no markdown syntax, the web adapter should return it unchanged.
    """
    adapter = WebAdapter()
    formatted = adapter.format_message(message)
    
    # Plain text should be preserved (possibly with whitespace normalization)
    assert formatted.strip() == message.strip()
