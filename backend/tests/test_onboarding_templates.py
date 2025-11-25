"""
Tests for onboarding message templates.

Validates that templates are properly defined for all states and tones.
"""

import pytest
from app.services.onboarding_templates import OnboardingTemplates
from app.models.onboarding_session import OnboardingState


class TestOnboardingTemplates:
    """Test suite for onboarding message templates."""
    
    def test_welcome_messages_all_tones(self):
        """Test that welcome messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_message(
                state=OnboardingState.WELCOME,
                tone=tone
            )
            assert message
            assert len(message) > 0
            assert isinstance(message, str)
    
    def test_collect_project_name_all_tones(self):
        """Test that project name collection messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_message(
                state=OnboardingState.COLLECT_PROJECT_NAME,
                tone=tone
            )
            assert message
            assert len(message) > 0
    
    def test_collect_goal_with_project_name(self):
        """Test that goal collection messages can be formatted with project name."""
        message = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_GOAL,
            tone="supportive",
            project_name="My Awesome Project"
        )
        assert "My Awesome Project" in message
    
    def test_confirm_deadline_with_date(self):
        """Test that deadline confirmation messages can be formatted with date."""
        message = OnboardingTemplates.get_message(
            state=OnboardingState.CONFIRM_DEADLINE,
            tone="direct",
            deadline="December 31, 2024"
        )
        assert "December 31, 2024" in message
    
    def test_confirm_details_with_all_data(self):
        """Test that confirmation messages can be formatted with all collected data."""
        message = OnboardingTemplates.get_message(
            state=OnboardingState.CONFIRM_DETAILS,
            tone="casual",
            project_name="Test Project",
            project_goal="Complete testing",
            deadline="December 31",
            checkin_frequency="daily",
            preferred_tone="casual"
        )
        assert "Test Project" in message
        assert "Complete testing" in message
        assert "December 31" in message
        assert "daily" in message
        assert "casual" in message
    
    def test_completion_message_all_tones(self):
        """Test that completion messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_message(
                state=OnboardingState.COMPLETED,
                tone=tone,
                project_name="Test Project",
                checkin_frequency="daily"
            )
            assert message
            assert len(message) > 0
    
    def test_error_message_invalid_date(self):
        """Test that invalid date error messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_error_message(
                error_type="invalid_date",
                tone=tone
            )
            assert message
            assert len(message) > 0
    
    def test_error_message_past_deadline(self):
        """Test that past deadline error messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_error_message(
                error_type="past_deadline",
                tone=tone
            )
            assert message
            assert len(message) > 0
    
    def test_error_message_empty_input(self):
        """Test that empty input error messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_error_message(
                error_type="empty_input",
                tone=tone
            )
            assert message
            assert len(message) > 0
    
    def test_retry_message_all_tones(self):
        """Test that retry messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_retry_message(tone=tone)
            assert message
            assert len(message) > 0
            # Should mention help, skip, or cancel options
            assert any(word in message.lower() for word in ["help", "skip", "cancel"])
    
    def test_help_message_collect_project_name(self):
        """Test that help messages exist for project name collection."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_help_message(
                state=OnboardingState.COLLECT_PROJECT_NAME,
                tone=tone
            )
            assert message
            assert len(message) > 0
    
    def test_help_message_collect_deadline(self):
        """Test that help messages exist for deadline collection."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_help_message(
                state=OnboardingState.COLLECT_DEADLINE,
                tone=tone
            )
            assert message
            assert len(message) > 0
            # Should mention date formats
            assert "December" in message or "weeks" in message
    
    def test_cancel_message_all_tones(self):
        """Test that cancel messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_cancel_message(tone=tone)
            assert message
            assert len(message) > 0
            # Should mention paused or saved
            assert any(word in message.lower() for word in ["pause", "save"])
    
    def test_restart_message_all_tones(self):
        """Test that restart messages exist for all tones."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            message = OnboardingTemplates.get_restart_message(tone=tone)
            assert message
            assert len(message) > 0
            # Should mention clearing data or starting over
            assert any(word in message.lower() for word in ["clear", "restart", "start"])
    
    def test_invalid_tone_defaults_to_supportive(self):
        """Test that invalid tone defaults to supportive."""
        message = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone="invalid_tone"
        )
        # Should return supportive tone message
        supportive_message = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone="supportive"
        )
        assert message == supportive_message
    
    def test_tone_variations_are_different(self):
        """Test that different tones produce different messages."""
        supportive = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone="supportive"
        )
        direct = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone="direct"
        )
        casual = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone="casual"
        )
        drill_sergeant = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone="drill_sergeant"
        )
        
        # All messages should be different
        messages = [supportive, direct, casual, drill_sergeant]
        assert len(set(messages)) == 4
    
    def test_missing_template_variables_handled_gracefully(self):
        """Test that missing template variables don't cause crashes."""
        # Try to get a message that requires variables without providing them
        message = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_GOAL,
            tone="supportive"
            # Missing project_name
        )
        # Should still return a message (unformatted)
        assert message
        assert len(message) > 0
