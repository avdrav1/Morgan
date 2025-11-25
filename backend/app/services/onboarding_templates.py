"""
Onboarding message templates for Discord DM onboarding flow.

This module provides comprehensive message templates for each onboarding step
with variations for different communication tones (supportive, direct, casual, drill_sergeant).

Requirements: 1.2, 2.1, 4.2
"""

from typing import Dict, Optional
from app.models.onboarding_session import OnboardingState


class OnboardingTemplates:
    """
    Message templates for the Discord DM onboarding flow.
    
    Provides templates for:
    - Welcome messages
    - Question templates for each step
    - Confirmation messages
    - Error and retry messages
    - Tone variations (supportive, direct, casual, drill_sergeant)
    """
    
    # Welcome messages by tone
    WELCOME_MESSAGES = {
        "supportive": (
            "Welcome! 🎉 I'm so glad you're here. I'm your accountability assistant, "
            "and I'm here to help you achieve your goals.\n\n"
            "Let's get started by creating your first project together. "
            "What would you like to work on?"
        ),
        "direct": (
            "Welcome. I'm your accountability assistant.\n\n"
            "Let's set up your first project. What are you working on?"
        ),
        "casual": (
            "Hey there! 👋 Welcome aboard! I'm your accountability buddy, "
            "here to help you crush your goals.\n\n"
            "Let's kick things off - what project do you want to tackle?"
        ),
        "drill_sergeant": (
            "Listen up! I'm your accountability assistant, and we're here to get things done.\n\n"
            "First project. What is it? Let's move!"
        ),
    }
    
    # Project name collection by tone
    COLLECT_PROJECT_NAME = {
        "supportive": (
            "That sounds great! What would you like to call this project? "
            "Choose a name that resonates with you."
        ),
        "direct": (
            "What's the project name?"
        ),
        "casual": (
            "Nice! What are we calling this project?"
        ),
        "drill_sergeant": (
            "Project name. Now."
        ),
    }
    
    # Project goal collection by tone
    COLLECT_GOAL = {
        "supportive": (
            "Perfect! '{project_name}' is a wonderful name. "
            "Now, what's the main goal you want to achieve with this project? "
            "What does success look like for you?"
        ),
        "direct": (
            "Got it: '{project_name}'. What's the goal?"
        ),
        "casual": (
            "Love it! So what's the big goal for '{project_name}'? "
            "What are you trying to accomplish?"
        ),
        "drill_sergeant": (
            "'{project_name}'. Noted. Main objective?"
        ),
    }
    
    # Deadline collection by tone
    COLLECT_DEADLINE = {
        "supportive": (
            "Excellent! That's a meaningful goal. "
            "When would you like to complete this project? "
            "You can tell me a specific date like 'December 31' or use natural language like 'in 2 weeks'."
        ),
        "direct": (
            "When's the deadline? Use a date like 'December 31' or 'in 2 weeks'."
        ),
        "casual": (
            "Awesome! When do you want to wrap this up? "
            "Give me a date like 'December 31' or something like 'in 2 weeks'."
        ),
        "drill_sergeant": (
            "Deadline. Give me a date. 'December 31' or 'in 2 weeks'. Go."
        ),
    }
    
    # Deadline confirmation by tone
    CONFIRM_DEADLINE = {
        "supportive": (
            "Just to make sure I have this right - you want to complete this by {deadline}. "
            "Does that sound good? (yes/no)"
        ),
        "direct": (
            "Confirm: deadline is {deadline}. Correct? (yes/no)"
        ),
        "casual": (
            "So we're shooting for {deadline}, right? (yes/no)"
        ),
        "drill_sergeant": (
            "Deadline: {deadline}. Confirm. (yes/no)"
        ),
    }
    
    # Check-in frequency collection by tone
    COLLECT_CHECKIN_FREQUENCY = {
        "supportive": (
            "Great! Now, how often would you like me to check in with you? "
            "I can reach out daily, every few days, weekly - whatever works best for you. "
            "What feels right?"
        ),
        "direct": (
            "Check-in frequency? Options: daily, every 2 days, weekly, etc."
        ),
        "casual": (
            "Cool! How often should I ping you? "
            "Daily? Every couple days? Weekly? You tell me!"
        ),
        "drill_sergeant": (
            "Check-in schedule. Daily? Every 2 days? Weekly? Decide."
        ),
    }
    
    # Tone preference collection by tone (meta!)
    COLLECT_TONE = {
        "supportive": (
            "Last question! What communication style works best for you?\n\n"
            "• **supportive** - Encouraging and empathetic\n"
            "• **direct** - Straightforward and efficient\n"
            "• **casual** - Friendly and relaxed\n"
            "• **drill_sergeant** - No-nonsense and intense\n\n"
            "Which one feels right for you?"
        ),
        "direct": (
            "Communication style preference:\n\n"
            "• supportive - Encouraging\n"
            "• direct - Straightforward\n"
            "• casual - Friendly\n"
            "• drill_sergeant - Intense\n\n"
            "Choose one."
        ),
        "casual": (
            "Last thing! How do you want me to talk to you?\n\n"
            "• **supportive** - Warm and encouraging\n"
            "• **direct** - Straight to the point\n"
            "• **casual** - Chill and friendly (like this!)\n"
            "• **drill_sergeant** - Tough love, no fluff\n\n"
            "What's your vibe?"
        ),
        "drill_sergeant": (
            "Final question. Communication style:\n\n"
            "• supportive - Soft\n"
            "• direct - Efficient\n"
            "• casual - Relaxed\n"
            "• drill_sergeant - Hardcore\n\n"
            "Pick one."
        ),
    }
    
    # Confirmation summary by tone
    CONFIRM_DETAILS = {
        "supportive": (
            "Wonderful! Let me make sure I have everything right:\n\n"
            "**Project:** {project_name}\n"
            "**Goal:** {project_goal}\n"
            "**Deadline:** {deadline}\n"
            "**Check-ins:** {checkin_frequency}\n"
            "**Tone:** {preferred_tone}\n\n"
            "Does this all look good to you? (yes/no)"
        ),
        "direct": (
            "Confirm details:\n\n"
            "Project: {project_name}\n"
            "Goal: {project_goal}\n"
            "Deadline: {deadline}\n"
            "Check-ins: {checkin_frequency}\n"
            "Tone: {preferred_tone}\n\n"
            "Correct? (yes/no)"
        ),
        "casual": (
            "Alright, let's double-check everything:\n\n"
            "**Project:** {project_name}\n"
            "**Goal:** {project_goal}\n"
            "**Deadline:** {deadline}\n"
            "**Check-ins:** {checkin_frequency}\n"
            "**Tone:** {preferred_tone}\n\n"
            "Look good? (yes/no)"
        ),
        "drill_sergeant": (
            "Final check:\n\n"
            "Project: {project_name}\n"
            "Goal: {project_goal}\n"
            "Deadline: {deadline}\n"
            "Check-ins: {checkin_frequency}\n"
            "Tone: {preferred_tone}\n\n"
            "Confirmed? (yes/no)"
        ),
    }
    
    # Completion messages by tone
    COMPLETION_MESSAGES = {
        "supportive": (
            "🎉 Congratulations! Your project '{project_name}' is all set up!\n\n"
            "I'll check in with you {checkin_frequency} to see how you're doing. "
            "Remember, I'm here to support you every step of the way.\n\n"
            "You've got this! Let's make great things happen together. 💪"
        ),
        "direct": (
            "Done. '{project_name}' is created.\n\n"
            "I'll check in {checkin_frequency}. Let's get to work."
        ),
        "casual": (
            "Boom! 🚀 '{project_name}' is ready to go!\n\n"
            "I'll hit you up {checkin_frequency} to see how things are going. "
            "Let's do this!"
        ),
        "drill_sergeant": (
            "'{project_name}' is locked in.\n\n"
            "Check-ins: {checkin_frequency}. No excuses. Move out!"
        ),
    }
    
    # Error messages by tone
    ERROR_MESSAGES = {
        "invalid_date": {
            "supportive": (
                "I'm having trouble understanding that date. "
                "Could you try again? You can use formats like:\n"
                "• December 31\n"
                "• 12/31/2024\n"
                "• in 2 weeks\n"
                "• next Friday"
            ),
            "direct": (
                "Invalid date format. Try:\n"
                "• December 31\n"
                "• 12/31/2024\n"
                "• in 2 weeks"
            ),
            "casual": (
                "Hmm, I didn't quite catch that date. Try something like:\n"
                "• December 31\n"
                "• 12/31/2024\n"
                "• in 2 weeks\n"
                "• next Friday"
            ),
            "drill_sergeant": (
                "Invalid date. Format:\n"
                "• December 31\n"
                "• 12/31/2024\n"
                "• in 2 weeks\n"
                "Try again."
            ),
        },
        "past_deadline": {
            "supportive": (
                "I noticed that date is in the past. "
                "Would you like to choose a future date instead? "
                "It's okay - we all make mistakes!"
            ),
            "direct": (
                "That date is in the past. Choose a future date."
            ),
            "casual": (
                "Oops! That date already passed. "
                "Let's pick something in the future, yeah?"
            ),
            "drill_sergeant": (
                "Past date. Unacceptable. Future date. Now."
            ),
        },
        "empty_input": {
            "supportive": (
                "I didn't catch that. Could you please try again? "
                "Take your time - I'm here when you're ready."
            ),
            "direct": (
                "Empty response. Please provide an answer."
            ),
            "casual": (
                "Didn't get anything there. Mind trying again?"
            ),
            "drill_sergeant": (
                "No input detected. Respond."
            ),
        },
        "ambiguous_input": {
            "supportive": (
                "I want to make sure I understand you correctly. "
                "Could you clarify what you meant?"
            ),
            "direct": (
                "Unclear. Please clarify."
            ),
            "casual": (
                "Not quite sure what you mean. Can you rephrase that?"
            ),
            "drill_sergeant": (
                "Ambiguous. Clarify."
            ),
        },
    }
    
    # Retry messages by tone (after multiple failed attempts)
    RETRY_MESSAGES = {
        "supportive": (
            "I can see we're having some trouble with this. "
            "Would you like some help? You can:\n"
            "• Type 'help' for more guidance\n"
            "• Type 'skip' to come back to this later\n"
            "• Type 'cancel' to pause onboarding"
        ),
        "direct": (
            "Multiple attempts failed. Options:\n"
            "• 'help' - Get guidance\n"
            "• 'skip' - Skip for now\n"
            "• 'cancel' - Pause onboarding"
        ),
        "casual": (
            "Looks like we're stuck. No worries! You can:\n"
            "• Type 'help' for some tips\n"
            "• Type 'skip' to move on\n"
            "• Type 'cancel' to take a break"
        ),
        "drill_sergeant": (
            "Three strikes. Options:\n"
            "• 'help' - Instructions\n"
            "• 'skip' - Move on\n"
            "• 'cancel' - Abort"
        ),
    }
    
    # Help messages by state and tone
    HELP_MESSAGES = {
        "collect_project_name": {
            "supportive": (
                "I'm asking for a name for your project. "
                "This can be anything that helps you identify it - "
                "like 'Website Redesign' or 'Learn Python'. "
                "What would you like to call it?"
            ),
            "direct": (
                "Need: Project name. Example: 'Website Redesign' or 'Learn Python'."
            ),
            "casual": (
                "Just need a name for your project! "
                "Something like 'Website Redesign' or 'Learn Python'. "
                "Whatever works for you!"
            ),
            "drill_sergeant": (
                "Project name required. Example: 'Website Redesign'. Simple."
            ),
        },
        "collect_goal": {
            "supportive": (
                "I'm asking what you want to achieve with this project. "
                "What's your main objective? What does success look like? "
                "For example: 'Launch a new website' or 'Complete 10 Python tutorials'."
            ),
            "direct": (
                "Need: Project goal. Example: 'Launch new website' or 'Complete 10 tutorials'."
            ),
            "casual": (
                "What's the endgame here? What are you trying to accomplish? "
                "Like 'Launch a new website' or 'Finish 10 Python tutorials'."
            ),
            "drill_sergeant": (
                "Objective required. Example: 'Launch website'. Be specific."
            ),
        },
        "collect_deadline": {
            "supportive": (
                "I'm asking when you'd like to complete this project. "
                "You can use natural language like:\n"
                "• 'December 31'\n"
                "• 'in 2 weeks'\n"
                "• 'next Friday'\n"
                "• '12/31/2024'"
            ),
            "direct": (
                "Need: Deadline. Formats:\n"
                "• December 31\n"
                "• in 2 weeks\n"
                "• 12/31/2024"
            ),
            "casual": (
                "When do you want to finish this? You can say:\n"
                "• 'December 31'\n"
                "• 'in 2 weeks'\n"
                "• 'next Friday'\n"
                "Whatever feels natural!"
            ),
            "drill_sergeant": (
                "Deadline required. Formats:\n"
                "• December 31\n"
                "• in 2 weeks\n"
                "• 12/31/2024\n"
                "Choose one."
            ),
        },
    }
    
    # Cancel/pause messages by tone
    CANCEL_MESSAGES = {
        "supportive": (
            "No problem! I've paused your onboarding. "
            "Your progress is saved, so you can pick up right where you left off.\n\n"
            "When you're ready to continue, just send me a message and we'll resume. "
            "Take care! 💙"
        ),
        "direct": (
            "Onboarding paused. Progress saved. "
            "Message me to resume."
        ),
        "casual": (
            "All good! I've hit pause on the onboarding. "
            "Everything's saved, so just holler when you want to continue. "
            "Catch you later! ✌️"
        ),
        "drill_sergeant": (
            "Paused. Progress saved. Resume when ready. Dismissed."
        ),
    }
    
    # Restart confirmation messages by tone
    RESTART_MESSAGES = {
        "supportive": (
            "Are you sure you want to start over? "
            "This will clear all the information we've collected so far. "
            "Type 'yes' to restart or 'no' to keep your current progress."
        ),
        "direct": (
            "Confirm restart? This clears all data. (yes/no)"
        ),
        "casual": (
            "You want to start fresh? That'll wipe everything we've done. "
            "Type 'yes' to restart or 'no' to keep going."
        ),
        "drill_sergeant": (
            "Restart confirmation. All data will be cleared. (yes/no)"
        ),
    }
    
    @classmethod
    def get_message(
        cls,
        state: OnboardingState,
        tone: str = "supportive",
        **kwargs
    ) -> str:
        """
        Get a message template for the given state and tone.
        
        Args:
            state: The current onboarding state
            tone: The communication tone (supportive, direct, casual, drill_sergeant)
            **kwargs: Variables to format into the template
            
        Returns:
            str: The formatted message
        """
        # Normalize tone
        tone = tone.lower() if tone else "supportive"
        if tone not in ["supportive", "direct", "casual", "drill_sergeant"]:
            tone = "supportive"
        
        # Map state to template dictionary
        template_map = {
            OnboardingState.WELCOME: cls.WELCOME_MESSAGES,
            OnboardingState.COLLECT_PROJECT_NAME: cls.COLLECT_PROJECT_NAME,
            OnboardingState.COLLECT_GOAL: cls.COLLECT_GOAL,
            OnboardingState.COLLECT_DEADLINE: cls.COLLECT_DEADLINE,
            OnboardingState.CONFIRM_DEADLINE: cls.CONFIRM_DEADLINE,
            OnboardingState.COLLECT_CHECKIN_FREQUENCY: cls.COLLECT_CHECKIN_FREQUENCY,
            OnboardingState.COLLECT_TONE: cls.COLLECT_TONE,
            OnboardingState.CONFIRM_DETAILS: cls.CONFIRM_DETAILS,
            OnboardingState.COMPLETED: cls.COMPLETION_MESSAGES,
        }
        
        templates = template_map.get(state)
        if not templates:
            return "Let's continue with your onboarding."
        
        template = templates.get(tone, templates.get("supportive", ""))
        
        # Format template with provided kwargs
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Missing required variable - return unformatted template
            return template
    
    @classmethod
    def get_error_message(
        cls,
        error_type: str,
        tone: str = "supportive"
    ) -> str:
        """
        Get an error message for the given error type and tone.
        
        Args:
            error_type: Type of error (invalid_date, past_deadline, empty_input, ambiguous_input)
            tone: The communication tone
            
        Returns:
            str: The error message
        """
        tone = tone.lower() if tone else "supportive"
        if tone not in ["supportive", "direct", "casual", "drill_sergeant"]:
            tone = "supportive"
        
        error_templates = cls.ERROR_MESSAGES.get(error_type, {})
        return error_templates.get(tone, "I didn't quite understand that. Could you try again?")
    
    @classmethod
    def get_retry_message(cls, tone: str = "supportive") -> str:
        """
        Get a retry message after multiple failed attempts.
        
        Args:
            tone: The communication tone
            
        Returns:
            str: The retry message
        """
        tone = tone.lower() if tone else "supportive"
        if tone not in ["supportive", "direct", "casual", "drill_sergeant"]:
            tone = "supportive"
        
        return cls.RETRY_MESSAGES.get(tone, cls.RETRY_MESSAGES["supportive"])
    
    @classmethod
    def get_help_message(
        cls,
        state: OnboardingState,
        tone: str = "supportive"
    ) -> str:
        """
        Get a help message for the given state and tone.
        
        Args:
            state: The current onboarding state
            tone: The communication tone
            
        Returns:
            str: The help message
        """
        tone = tone.lower() if tone else "supportive"
        if tone not in ["supportive", "direct", "casual", "drill_sergeant"]:
            tone = "supportive"
        
        state_key = state.value if isinstance(state, OnboardingState) else state
        help_templates = cls.HELP_MESSAGES.get(state_key, {})
        
        return help_templates.get(
            tone,
            "I'm here to help you set up your first project. What would you like to know?"
        )
    
    @classmethod
    def get_cancel_message(cls, tone: str = "supportive") -> str:
        """
        Get a cancellation/pause message.
        
        Args:
            tone: The communication tone
            
        Returns:
            str: The cancel message
        """
        tone = tone.lower() if tone else "supportive"
        if tone not in ["supportive", "direct", "casual", "drill_sergeant"]:
            tone = "supportive"
        
        return cls.CANCEL_MESSAGES.get(tone, cls.CANCEL_MESSAGES["supportive"])
    
    @classmethod
    def get_restart_message(cls, tone: str = "supportive") -> str:
        """
        Get a restart confirmation message.
        
        Args:
            tone: The communication tone
            
        Returns:
            str: The restart message
        """
        tone = tone.lower() if tone else "supportive"
        if tone not in ["supportive", "direct", "casual", "drill_sergeant"]:
            tone = "supportive"
        
        return cls.RESTART_MESSAGES.get(tone, cls.RESTART_MESSAGES["supportive"])
