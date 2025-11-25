"""
Integration tests for onboarding templates with the onboarding service.

Validates that templates integrate properly with the onboarding flow.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from app.services.onboarding_templates import OnboardingTemplates
from app.models.onboarding_session import OnboardingState


class TestOnboardingTemplatesIntegration:
    """Integration tests for onboarding templates."""
    
    def test_welcome_flow_all_tones(self):
        """Test that welcome messages work for all tones in a flow."""
        tones = ["supportive", "direct", "casual", "drill_sergeant"]
        
        for tone in tones:
            # Welcome
            welcome = OnboardingTemplates.get_message(
                state=OnboardingState.WELCOME,
                tone=tone
            )
            assert welcome
            
            # Collect project name
            collect_name = OnboardingTemplates.get_message(
                state=OnboardingState.COLLECT_PROJECT_NAME,
                tone=tone
            )
            assert collect_name
            
            # Collect goal with project name
            collect_goal = OnboardingTemplates.get_message(
                state=OnboardingState.COLLECT_GOAL,
                tone=tone,
                project_name="Test Project"
            )
            assert collect_goal
            assert "Test Project" in collect_goal
    
    def test_complete_onboarding_flow_supportive(self):
        """Test a complete onboarding flow with supportive tone."""
        tone = "supportive"
        
        # Step 1: Welcome
        msg1 = OnboardingTemplates.get_message(
            state=OnboardingState.WELCOME,
            tone=tone
        )
        assert "Welcome" in msg1 or "welcome" in msg1
        
        # Step 2: Collect project name
        msg2 = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_PROJECT_NAME,
            tone=tone
        )
        assert len(msg2) > 0
        
        # Step 3: Collect goal
        msg3 = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_GOAL,
            tone=tone,
            project_name="Website Redesign"
        )
        assert "Website Redesign" in msg3
        
        # Step 4: Collect deadline
        msg4 = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_DEADLINE,
            tone=tone
        )
        assert len(msg4) > 0
        
        # Step 5: Confirm deadline
        msg5 = OnboardingTemplates.get_message(
            state=OnboardingState.CONFIRM_DEADLINE,
            tone=tone,
            deadline="December 31, 2024"
        )
        assert "December 31, 2024" in msg5
        
        # Step 6: Collect check-in frequency
        msg6 = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_CHECKIN_FREQUENCY,
            tone=tone
        )
        assert len(msg6) > 0
        
        # Step 7: Collect tone preference
        msg7 = OnboardingTemplates.get_message(
            state=OnboardingState.COLLECT_TONE,
            tone=tone
        )
        assert "supportive" in msg7
        assert "direct" in msg7
        assert "casual" in msg7
        
        # Step 8: Confirm details
        msg8 = OnboardingTemplates.get_message(
            state=OnboardingState.CONFIRM_DETAILS,
            tone=tone,
            project_name="Website Redesign",
            project_goal="Launch new site",
            deadline="December 31, 2024",
            checkin_frequency="daily",
            preferred_tone="supportive"
        )
        assert "Website Redesign" in msg8
        assert "Launch new site" in msg8
        
        # Step 9: Completion
        msg9 = OnboardingTemplates.get_message(
            state=OnboardingState.COMPLETED,
            tone=tone,
            project_name="Website Redesign",
            checkin_frequency="daily"
        )
        assert "Website Redesign" in msg9
    
    def test_error_handling_flow(self):
        """Test error handling messages in a flow."""
        tone = "supportive"
        
        # Invalid date error
        error1 = OnboardingTemplates.get_error_message(
            error_type="invalid_date",
            tone=tone
        )
        assert len(error1) > 0
        
        # Past deadline error
        error2 = OnboardingTemplates.get_error_message(
            error_type="past_deadline",
            tone=tone
        )
        assert len(error2) > 0
        
        # Empty input error
        error3 = OnboardingTemplates.get_error_message(
            error_type="empty_input",
            tone=tone
        )
        assert len(error3) > 0
        
        # Retry message after multiple failures
        retry = OnboardingTemplates.get_retry_message(tone=tone)
        assert "help" in retry.lower() or "skip" in retry.lower()
    
    def test_help_flow(self):
        """Test help messages for different states."""
        tone = "casual"
        
        # Help for project name
        help1 = OnboardingTemplates.get_help_message(
            state=OnboardingState.COLLECT_PROJECT_NAME,
            tone=tone
        )
        assert len(help1) > 0
        
        # Help for goal
        help2 = OnboardingTemplates.get_help_message(
            state=OnboardingState.COLLECT_GOAL,
            tone=tone
        )
        assert len(help2) > 0
        
        # Help for deadline
        help3 = OnboardingTemplates.get_help_message(
            state=OnboardingState.COLLECT_DEADLINE,
            tone=tone
        )
        assert len(help3) > 0
    
    def test_cancel_and_restart_flow(self):
        """Test cancel and restart messages."""
        tone = "direct"
        
        # Cancel message
        cancel = OnboardingTemplates.get_cancel_message(tone=tone)
        assert len(cancel) > 0
        
        # Restart message
        restart = OnboardingTemplates.get_restart_message(tone=tone)
        assert len(restart) > 0
    
    def test_tone_consistency_across_flow(self):
        """Test that tone is consistent across the entire flow."""
        tone = "drill_sergeant"
        
        messages = [
            OnboardingTemplates.get_message(OnboardingState.WELCOME, tone=tone),
            OnboardingTemplates.get_message(OnboardingState.COLLECT_PROJECT_NAME, tone=tone),
            OnboardingTemplates.get_message(OnboardingState.COLLECT_GOAL, tone=tone, project_name="Test"),
            OnboardingTemplates.get_message(OnboardingState.COLLECT_DEADLINE, tone=tone),
        ]
        
        # All messages should be relatively short and direct for drill_sergeant tone
        for msg in messages:
            assert len(msg) > 0
            # Drill sergeant messages should generally be shorter
            assert len(msg) < 500
