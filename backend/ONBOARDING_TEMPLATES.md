# Onboarding Message Templates

This document describes the message template system for Discord DM onboarding.

## Overview

The `OnboardingTemplates` class provides comprehensive message templates for the entire onboarding flow with support for multiple communication tones. This ensures consistent, high-quality messaging throughout the user experience.

## Features

- **Tone Variations**: Four distinct communication styles
  - `supportive`: Encouraging and empathetic
  - `direct`: Straightforward and efficient
  - `casual`: Friendly and relaxed
  - `drill_sergeant`: No-nonsense and intense

- **Complete Coverage**: Templates for all onboarding states
  - Welcome messages
  - Question prompts for each data collection step
  - Confirmation messages
  - Error messages
  - Help messages
  - Cancel/restart messages

- **Fallback Support**: Used when LLM service is unavailable

## Usage

### Basic Message Retrieval

```python
from app.services.onboarding_templates import OnboardingTemplates
from app.models.onboarding_session import OnboardingState

# Get a welcome message
message = OnboardingTemplates.get_message(
    state=OnboardingState.WELCOME,
    tone="supportive"
)

# Get a message with variables
message = OnboardingTemplates.get_message(
    state=OnboardingState.COLLECT_GOAL,
    tone="casual",
    project_name="My Project"
)
```

### Error Messages

```python
# Get an error message
error_msg = OnboardingTemplates.get_error_message(
    error_type="invalid_date",
    tone="supportive"
)

# Available error types:
# - invalid_date
# - past_deadline
# - empty_input
# - ambiguous_input
```

### Help Messages

```python
# Get contextual help
help_msg = OnboardingTemplates.get_help_message(
    state=OnboardingState.COLLECT_DEADLINE,
    tone="direct"
)
```

### Retry Messages

```python
# After multiple failed attempts
retry_msg = OnboardingTemplates.get_retry_message(tone="casual")
```

### Control Messages

```python
# Cancel/pause message
cancel_msg = OnboardingTemplates.get_cancel_message(tone="supportive")

# Restart confirmation
restart_msg = OnboardingTemplates.get_restart_message(tone="direct")
```

## Template Variables

Different states support different template variables:

### COLLECT_GOAL
- `project_name`: The name of the project

### CONFIRM_DEADLINE
- `deadline`: The formatted deadline date

### CONFIRM_DETAILS
- `project_name`: Project name
- `project_goal`: Project goal/description
- `deadline`: Formatted deadline
- `checkin_frequency`: Check-in frequency
- `preferred_tone`: User's preferred tone

### COMPLETED
- `project_name`: Project name
- `checkin_frequency`: Check-in frequency

## Tone Guidelines

### Supportive
- Warm and encouraging
- Uses emojis sparingly
- Acknowledges user effort
- Provides reassurance

Example: "Welcome! 🎉 I'm so glad you're here. I'm your accountability assistant, and I'm here to help you achieve your goals."

### Direct
- Concise and to-the-point
- No unnecessary words
- Clear instructions
- Professional tone

Example: "Welcome. I'm your accountability assistant. Let's set up your first project. What are you working on?"

### Casual
- Friendly and conversational
- Uses casual language
- Includes emojis
- Relaxed tone

Example: "Hey there! 👋 Welcome aboard! I'm your accountability buddy, here to help you crush your goals."

### Drill Sergeant
- Commanding and intense
- Very brief
- Action-oriented
- No fluff

Example: "Listen up! I'm your accountability assistant, and we're here to get things done. First project. What is it? Let's move!"

## Integration with LLM Service

The templates serve as fallbacks when the LLM service is unavailable:

1. **Primary**: LLM generates contextual, natural responses
2. **Fallback**: Templates provide consistent messaging if LLM fails
3. **Timeout**: 5-second timeout triggers fallback

```python
# In llm_service.py
try:
    response = await llm_service.generate_onboarding_message(...)
except Exception:
    # Falls back to templates
    response = OnboardingTemplates.get_message(...)
```

## Adding New Templates

To add templates for a new state:

1. Add the state to `OnboardingState` enum
2. Create template dictionary with all four tones
3. Add to `template_map` in `get_message()` method
4. Add tests in `test_onboarding_templates.py`

Example:

```python
NEW_STATE_TEMPLATES = {
    "supportive": "Your supportive message here",
    "direct": "Your direct message here",
    "casual": "Your casual message here",
    "drill_sergeant": "Your drill sergeant message here",
}
```

## Testing

Run template tests:

```bash
docker exec accountability-backend python -m pytest tests/test_onboarding_templates.py -v
```

Run integration tests:

```bash
docker exec accountability-backend python -m pytest tests/test_onboarding_templates_integration.py -v
```

## Requirements Validation

This implementation satisfies:
- **Requirement 1.2**: Welcome message templates
- **Requirement 2.1**: Question templates for each step
- **Requirement 4.2**: Tone preference templates

## Best Practices

1. **Consistency**: Keep tone consistent within each variation
2. **Brevity**: Keep messages concise, especially for drill_sergeant
3. **Clarity**: Ensure instructions are clear in all tones
4. **Variables**: Use template variables for dynamic content
5. **Testing**: Test all tones for each new template
6. **Fallback**: Always provide a sensible default message

## Future Enhancements

Potential improvements:
- Localization support for multiple languages
- A/B testing different message variations
- User feedback on message effectiveness
- Dynamic tone adjustment based on user engagement
- Custom tone creation for individual users
