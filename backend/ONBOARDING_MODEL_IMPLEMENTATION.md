# Onboarding Session Model Implementation

## Overview
This document describes the implementation of the OnboardingSession database model and migration for the Discord DM onboarding feature.

## Files Created

### 1. Model Definition
**File:** `backend/app/models/onboarding_session.py`

**Contents:**
- `OnboardingState` enum with 12 states (WELCOME, COLLECT_PROJECT_NAME, COLLECT_GOAL, COLLECT_DEADLINE, CONFIRM_DEADLINE, COLLECT_CHECKIN_FREQUENCY, COLLECT_TONE, CONFIRM_DETAILS, CREATING_PROJECT, COMPLETED, PAUSED, FAILED)
- `OnboardingSession` model class with all required fields:
  - Primary key: `id` (UUID)
  - Foreign key: `user_id` (references users.id)
  - Indexed fields: `user_id`, `discord_id`
  - State tracking: `current_state`, `started_at`, `last_activity_at`, `completed_at`
  - Collected data: `project_name`, `project_goal`, `deadline`, `checkin_frequency`, `preferred_tone`
  - Conversation history: `conversation_history` (JSON)
  - Metadata: `retry_count`, `error_message`, `created_at`, `updated_at`

### 2. Migration File
**File:** `backend/alembic/versions/j9a0b1c2d3e4_add_onboarding_sessions_table.py`

**Contents:**
- Revision ID: `j9a0b1c2d3e4`
- Revises: `i8a9b0c1d2e3` (Discord OAuth fields migration)
- Creates `onboarding_sessions` table with all columns
- Creates indexes on `user_id` and `discord_id` for efficient lookups
- Idempotent upgrade/downgrade functions that check for existing tables/indexes

### 3. Model Export
**File:** `backend/app/models/__init__.py`

**Changes:**
- Added import for `OnboardingSession` and `OnboardingState`
- Added both to `__all__` export list

## Requirements Validation

### Requirement 6.1
✓ **WHEN a user starts onboarding THEN the system SHALL create an onboarding session in the database**
- Model includes all fields needed to track onboarding state
- Primary key and foreign key relationships established

### Requirement 6.2
✓ **WHEN the user provides information THEN the system SHALL update the onboarding session after each response**
- Model includes fields for all collected data (project_name, project_goal, deadline, etc.)
- `last_activity_at` field tracks when session was last updated
- `conversation_history` JSON field stores all message exchanges

## Design Document Compliance

The implementation matches the design document specification exactly:

1. **Table name:** `onboarding_sessions` ✓
2. **All required fields present:** ✓
   - id, user_id, discord_id
   - current_state, started_at, last_activity_at, completed_at
   - project_name, project_goal, deadline, checkin_frequency, preferred_tone
   - conversation_history
   - retry_count, error_message
   - created_at, updated_at

3. **State enum:** All 12 states defined ✓
4. **Indexes:** user_id and discord_id indexed ✓
5. **Foreign key:** References users.id ✓
6. **JSON field:** conversation_history for storing message history ✓

## Database Schema

```sql
CREATE TABLE onboarding_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    discord_id VARCHAR NOT NULL,
    current_state onboardingstate NOT NULL,
    started_at TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    project_name VARCHAR,
    project_goal TEXT,
    deadline TIMESTAMP,
    checkin_frequency VARCHAR,
    preferred_tone VARCHAR,
    conversation_history JSON NOT NULL,
    retry_count INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_onboarding_sessions_user_id ON onboarding_sessions(user_id);
CREATE INDEX ix_onboarding_sessions_discord_id ON onboarding_sessions(discord_id);
```

## Testing

A verification script has been created at `backend/verify_onboarding_model.py` that:
- Verifies the model can be imported
- Checks all 12 states are defined
- Validates all required fields are present
- Confirms indexes are defined

## Next Steps

To apply this migration:

1. **Using Docker:**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

2. **Locally (if dependencies installed):**
   ```bash
   cd backend
   alembic upgrade head
   ```

The migration is idempotent and safe to run multiple times.

## Notes

- The migration follows the same defensive pattern as existing migrations (checks for existing tables/indexes)
- The model uses SQLAlchemy's declarative base pattern consistent with other models
- The relationship to User model is established via backref
- Default values are set for fields that should have them (retry_count=0, conversation_history=[])
- The OnboardingState enum uses string values for better database readability
