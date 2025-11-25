# Discord Onboarding Enhancement

## Overview
This document describes the enhancements made to the Discord DM onboarding flow to make it more conversational and complete.

## Goals
1. Keep the project-focused onboarding flow (project name, goal, deadline, preferences)
2. Make the conversation more natural using LLM-generated responses
3. Show a comprehensive summary at the end including:
   - User preferences (tone, check-in frequency)
   - Project plan with milestones/tasks

## Current State
- Onboarding state machine exists with proper states
- LLM service has `generate_onboarding_message` method
- Webhook endpoint `/webhooks/onboarding/message` exists but needs enhancement
- Project decomposition exists via `decompose_project` method

## Required Changes

### 1. Enhanced Message Processing in Webhook
**File:** `backend/app/api/webhooks.py`

The `process_onboarding_message` endpoint needs to:
- Parse user input based on current state
- Extract relevant data (project name, goal, deadline, etc.)
- Validate input and handle errors
- Transition to next state
- Generate LLM response for next question
- Handle final state by creating project and showing summary

### 2. Add Project Plan Generation
**File:** `backend/app/services/onboarding_service.py`

Add method to generate final summary with project plan:
- `async def generate_completion_summary(user_id: UUID) -> str`
- Calls `llm_service.decompose_project()` to get tasks
- Formats summary with preferences + project breakdown

### 3. Update State Machine
**File:** `backend/app/services/onboarding_state_machine.py`

Add new state for showing summary:
- `SHOW_SUMMARY` - Display preferences + project plan before completion

### 4. Input Parsing and Validation
**File:** `backend/app/services/input_validators.py`

Enhance validators to handle:
- Natural language date parsing
- Tone preference extraction
- Check-in frequency parsing

## Implementation Status

### Phase 1: Core Infrastructure (COMPLETED ✅)
- [x] Database models and migrations
- [x] State machine implementation
- [x] OnboardingService core functionality
- [x] Input validation and parsing
- [x] LLM service integration
- [x] Webhook endpoints
- [x] Discord bot DM handler
- [x] Project creation with retry logic
- [x] Logging and monitoring
- [x] Session cleanup and abandonment handling

### Phase 2: Enhanced Conversational Flow (NEW TASKS)
- [ ] Task 21: Enhanced webhook message processing with state-based logic
- [ ] Task 22: Add state machine support for summary display
- [ ] Task 23: Implement project plan generation service
- [ ] Task 24: Integrate summary generation into completion flow
- [ ] Task 25: Enhance input parsing for natural language
- [ ] Task 26: Add state-specific response generation
- [ ] Task 27: Test enhanced conversational flow
- [ ] Task 28: Final checkpoint - Verify enhanced flow

## Key Implementation Details

### Task 21: Enhanced Webhook Message Processing
**Location:** `backend/app/api/webhooks.py` - `process_onboarding_message()`

**Current State:** Basic message routing exists but doesn't parse input or transition states

**Needed Changes:**
```python
async def process_onboarding_message(...):
    # 1. Get current session and state
    # 2. Parse user input based on state:
    #    - COLLECT_PROJECT_NAME: Extract project name
    #    - COLLECT_GOAL: Extract project goal
    #    - COLLECT_DEADLINE: Parse date using input_validators
    #    - COLLECT_CHECKIN_FREQUENCY: Extract frequency
    #    - COLLECT_TONE: Extract tone preference
    # 3. Validate extracted data
    # 4. Update session with data
    # 5. Determine next state
    # 6. Transition to next state via process_message()
    # 7. Generate LLM response via generate_response()
    # 8. Return response to Discord bot
```

### Task 22: State Machine Enhancement
**Location:** `backend/app/services/onboarding_state_machine.py`

**Add New State:**
```python
class OnboardingState(Enum):
    # ... existing states ...
    SHOW_SUMMARY = "show_summary"  # NEW: Display preferences + project plan
```

**Update Transitions:**
```python
CONFIRM_DETAILS -> SHOW_SUMMARY -> CREATING_PROJECT -> COMPLETED
```

### Task 23: Project Plan Generation
**Location:** `backend/app/services/onboarding_service.py`

**New Method:**
```python
async def generate_completion_summary(self, user_id: UUID) -> str:
    """
    Generate comprehensive summary with preferences and project plan.
    
    Returns formatted message with:
    1. User preferences (tone, check-in frequency)
    2. Project details (name, goal, deadline)
    3. Project plan with tasks/milestones from LLM
    """
    # 1. Get session data
    # 2. Get user data
    # 3. Create temporary project object
    # 4. Call llm_service.decompose_project()
    # 5. Format summary with preferences
    # 6. Format project plan with tasks
    # 7. Combine into comprehensive message
    # 8. Return formatted summary
```

### Task 24: Integration into Completion Flow
**Location:** `backend/app/api/webhooks.py` and `backend/app/services/onboarding_service.py`

**Flow:**
1. When user confirms details (CONFIRM_DETAILS state)
2. Transition to SHOW_SUMMARY state
3. Generate and send summary with project plan
4. Wait for user confirmation
5. On confirmation, transition to CREATING_PROJECT
6. Create project and complete onboarding

### Task 25: Enhanced Input Parsing
**Location:** `backend/app/services/input_validators.py`

**Enhancements Needed:**
- More flexible date parsing (e.g., "next Friday", "in 2 weeks", "end of month")
- Tone extraction from natural language (e.g., "I prefer supportive" -> "supportive")
- Frequency extraction (e.g., "check in daily" -> "daily")
- Better error messages for invalid inputs

### Task 26: State-Specific Response Generation
**Location:** `backend/app/services/onboarding_service.py` - `generate_response()`

**Current:** Uses generic prompts
**Needed:** State-specific prompts with collected data context

**Example:**
```python
# For COLLECT_GOAL state:
prompt = f"The user named their project '{session.project_name}'. 
          Generate a warm response acknowledging this and ask about 
          their main goal for this project."
```

## Testing Plan
1. **Unit Tests:** Test each new method individually
2. **Integration Tests:** Test complete flow from start to summary
3. **Manual Testing:** Test via Discord DMs with various inputs
4. **LLM Response Quality:** Verify responses are natural and contextual
5. **Summary Verification:** Ensure summary includes both preferences and project plan

## Success Criteria
- [ ] User can complete onboarding conversationally via Discord DMs
- [ ] LLM generates natural, contextual responses at each step
- [ ] System correctly parses natural language inputs
- [ ] Final summary shows user preferences clearly
- [ ] Final summary shows project plan with tasks/milestones
- [ ] User can confirm or edit plan before project creation
- [ ] All existing tests continue to pass
- [ ] New integration tests pass
