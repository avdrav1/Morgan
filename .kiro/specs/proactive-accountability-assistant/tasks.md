# Implementation Plan

- [x] 1. Enhance data models and create migrations
- [x] 1.1 Add new fields to User model for engagement tracking
  - Add total_check_ins_sent, total_check_ins_responded, consecutive_missed_check_ins, last_active_at fields
  - _Requirements: 3.4, 3.5, 9.1, 9.2, 9.3_

- [x] 1.2 Add new fields to Project model for ghosting and project-specific settings
  - Add ghosting_stage field to track missed check-in patterns
  - Ensure project_tone and project_context fields exist
  - _Requirements: 6.8, 6.9, 9.1, 9.2, 9.3_

- [x] 1.3 Add new fields to Task model for blocker tracking
  - Add blocker_diagnosed_at field
  - Ensure blocker_type and blocker_description fields exist
  - _Requirements: 4.3, 4.6_

- [x] 1.4 Add new fields to CheckIn model for conversation and response tracking
  - Add blocker_detected, reschedule_initiated, response_time_minutes, sentiment fields
  - Ensure conversation_context JSONB field exists
  - _Requirements: 4.2, 5.1, 5.3_

- [x] 1.5 Create ReschedulingHistory model
  - Create model with task_id, old_due_date, new_due_date, reason, blocker_type, initiated_by, created_at fields
  - _Requirements: 5.5_

- [x] 1.6 Create Alembic migration for all model changes
  - Generate migration script for all new fields and tables
  - Test migration on development database
  - _Requirements: All above_

- [x] 1.7 Write property test for multi-project storage
  - **Property 2: Multi-project storage with single focus**
  - **Validates: Requirements 1.4**

- [x] 2. Implement Scheduler Service
- [x] 2.1 Create SchedulerService class with availability-aware scheduling
  - Implement calculate_check_in_time method that respects availability windows
  - Implement find_next_available_slot method
  - _Requirements: 2.6, 3.6, 8.4_

- [x] 2.2 Implement quiet hours enforcement logic
  - Implement is_within_quiet_hours method with proper timezone handling
  - Handle quiet hours that span midnight (e.g., 22:00 to 08:00)
  - _Requirements: 3.2, 8.3_

- [x] 2.3 Write property test for quiet hours enforcement
  - **Property 7: Quiet hours enforcement**
  - **Validates: Requirements 3.2, 8.3**

- [x] 2.4 Implement adaptive frequency logic
  - Implement should_adapt_frequency method that analyzes response patterns
  - Calculate response rate from recent check-ins
  - Adjust frequency based on responsiveness thresholds
  - _Requirements: 3.4, 3.5_

- [x] 2.5 Write property tests for adaptive frequency
  - **Property 8: Adaptive frequency for low responsiveness**
  - **Property 9: Adaptive frequency for high responsiveness**
  - **Validates: Requirements 3.4, 3.5**

- [x] 2.6 Implement ghosting detection and response
  - Implement calculate_ghosting_response method
  - Handle 2, 4, and 7 missed check-in thresholds
  - Update project ghosting_stage appropriately
  - _Requirements: 9.1, 9.2, 9.3_

- [x] 2.7 Implement timezone-aware scheduling
  - Ensure all time calculations use user's timezone
  - Handle timezone conversion correctly
  - _Requirements: 8.5_

- [x] 2.8 Write property test for timezone-aware scheduling
  - **Property 17: Timezone-aware scheduling**
  - **Validates: Requirements 8.5**

- [x] 2.9 Write property test for availability-aware scheduling
  - **Property 5: Availability-aware scheduling**
  - **Validates: Requirements 2.6, 3.6, 8.4**

- [x] 2.10 Write property test for pre-deadline check-ins
  - **Property 6: Pre-deadline check-ins**
  - **Validates: Requirements 3.1, 3.3**

- [x] 3. Implement Conversation Manager
- [x] 3.1 Create ConversationManager class
  - Implement get_conversation_context method to retrieve conversation history
  - Implement store_conversation_turn method to save conversation turns
  - _Requirements: 4.1, 4.2, 5.1_

- [x] 3.2 Implement blocker pattern detection
  - Implement detect_blocker_pattern method
  - Recognize patterns indicating time, clarity, emotional, external, or scope blockers
  - _Requirements: 4.3_

- [x] 3.3 Write property test for blocker type validity
  - **Property 10: Blocker type validity**
  - **Validates: Requirements 4.3**

- [x] 3.4 Implement reschedule intent extraction
  - Implement extract_reschedule_intent method
  - Detect when user is requesting to reschedule
  - _Requirements: 5.1, 5.2_
      nce LLM Service
- [x]   4.1 Implement blocker diagnosis method
  - Add  diagnose_blocker method to LLMService
  - Return blocker_type and suggested_strategies
  - _Requirements: 4.2, 4.3_

- [x] 4.2 Implement reschedule proposal method
  - Add propose_reschedule method to LLMService
  - Generate proposed new deadline with reasoning
  - _Requirements: 5.2, 5.3_

- [x] 4.3 Enhance tone system with all presets
  - Ensure all four tone presets (coach, manager, buddy, drill_sergeant) are implemented
  - Verify custom system prompt support
  - _Requirements: 6.1, 6.2, 6.7_

- [x] 4.4 Implement project-specific context inclusion
  - Ensure project_context is included in LLM prompts when present
  - Ensure project_tone overrides user default tone
  - _Requirements: 6.8, 6.9_

- [x] 4.5 Write property test for project-specific tone persistence
  - **Property 13: Project-specific tone persistence**
  - **Validates: Requirements 6.8**

- [x] 4.6 Write property test for project context inclusion
  - **Property 14: Project context inclusion**
  - **Validates: Requirements 6.9**

- [x] 4.7 Enhance project decomposition with task count validation
  - Ensure decompose_project returns 5-20 tasks
  - Add validation logic
  - _Requirements: 2.1_

- [x] 4.8 Write property test for task count bounds
  - **Property 3: Task count bounds**
  - **Validates: Requirements 2.1**

- [x] 5. Implement Messaging Adapter Interface
- [x] 5.1 Create abstract MessagingAdapter base class
  - Define send_message and handle_incoming_message abstract methods
  - _Requirements: 7.1, 7.2_

- [x] 5.2 Implement DiscordAdapter
  - Implement Discord-specific message sending
  - Implement Discord-specific message receiving
  - Handle Discord markdown formatting
  - _Requirements: 7.1, 7.3_

- [x] 5.3 Implement WebAdapter
  - Implement web interface message delivery
  - Implement web interface message receiving
  - Handle plain text formatting
  - _Requirements: 7.2, 7.3_

- [x] 5.4 Write property test for platform-appropriate formatting
  - **Property 15: Platform-appropriate formatting**
  - **Validates: Requirements 7.3**

- [x] 5.5 Implement message delivery retry logic with exponential backoff
  - Add retry mechanism to messaging adapters
  - Implement exponential backoff (1s, 2s, 4s, 8s, 16s)
  - Track delivery status
  - _Requirements: 7.4_

- [x] 5.6 Write property test for exponential backoff on retry
  - **Property 16: Exponential backoff on retry**
  - **Validates: Requirements 7.4**

- [x] 6. Implement API endpoints for user preferences
- [x] 6.1 Create availability management endpoints
  - Implement GET /api/users/me/availability
  - Implement PUT /api/users/me/availability
  - _Requirements: 8.1, 8.2_

- [x] 6.2 Create quiet hours management endpoint
  - Implement PUT /api/users/me/quiet-hours
  - _Requirements: 8.1_

- [x] 6.3 Create tone and system prompt management endpoints
  - Implement PUT /api/users/me/tone
  - Implement PUT /api/users/me/system-prompt
  - _Requirements: 6.1, 6.7_

- [x] 6.4 Create messaging pause/resume endpoint
  - Implement POST /api/users/me/pause-messaging
  - Implement POST /api/users/me/resume-messaging
  - _Requirements: 10.3_

- [x] 6.5 Write property test for pause stops proactive messages
  - **Property 20: Pause stops proactive messages**
  - **Validates: Requirements 10.3**

- [x] 7. Implement API endpoints for project management
- [x] 7.1 Enhance project creation endpoint
  - Update POST /api/projects to accept free-form descriptions
  - Trigger LLM clarification flow
  - _Requirements: 1.1_

- [x] 7.2 Write property test for project input acceptance
  - **Property 1: Project input acceptance**
  - **Validates: Requirements 1.1**

- [x] 7.3 Create project decomposition endpoint
  - Implement POST /api/projects/{id}/decompose
  - Call LLM service to generate tasks
  - Return proposed timeline
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 7.4 Create timeline approval endpoint
  - Implement PUT /api/projects/{id}/timeline
  - Allow user to modify and confirm timeline
  - _Requirements: 2.4, 2.5_

- [x] 7.5 Write property test for timeline modification acceptance
  - **Property 4: Timeline modification acceptance**
  - **Validates: Requirements 2.5**

- [x] 7.6 Create project pause and archive endpoints
  - Implement POST /api/projects/{id}/pause
  - Implement POST /api/projects/{id}/archive
  - _Requirements: 9.2, 9.3_

- [x] 8. Implement check-in response and rescheduling endpoints
- [x] 8.1 Create check-in response endpoint
  - Implement POST /api/check-ins/{id}/respond
  - Process user response through ConversationManager
  - Generate coaching response via LLM
  - _Requirements: 4.1, 4.2_

- [x] 8.2 Create rescheduling endpoint
  - Implement POST /api/check-ins/{id}/reschedule
  - Initiate conversational rescheduling flow
  - Require explicit confirmation before updating timeline
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 8.3 Write property test for no automatic timeline adjustments
  - **Property 11: No automatic timeline adjustments**
  - **Validates: Requirements 5.4**

- [x] 8.4 Implement rescheduling history tracking
  - Create ReschedulingHistory record on each reschedule
  - Store old date, new date, reason, and blocker type
  - _Requirements: 5.5_

- [x] 8.5 Write property test for rescheduling history tracking
  - **Property 12: Rescheduling history tracking**
  - **Validates: Requirements 5.5**

- [x] 8.6 Create check-in history endpoint
  - Implement GET /api/tasks/{id}/check-ins
  - Return all check-ins for a task with conversation history
  - _Requirements: 4.1, 5.1_

- [x] 9. Implement data privacy and user control endpoints
- [x] 9.1 Create data deletion endpoint
  - Implement DELETE /api/users/me/data
  - Schedule deletion within 30 days
  - Delete all associated records
  - _Requirements: 10.1_

- [x] 9.2 Write property test for data deletion completeness
  - **Property 18: Data deletion completeness**
  - **Validates: Requirements 10.1**

- [x] 9.3 Create data export endpoint
  - Implement GET /api/users/me/export
  - Export all projects, tasks, timelines, and conversation history
  - Return in portable JSON format
  - _Requirements: 10.2_

- [x] 9.4 Write property test for data export completeness
  - **Property 19: Data export completeness**
  - **Validates: Requirements 10.2**

- [x] 9.5 Write property test for data collection scope
  - **Property 21: Data collection scope**
  - **Validates: Requirements 10.4**

- [x] 10. Implement Celery tasks for proactive check-ins
- [x] 10.1 Enhance process_scheduled_check_ins task
  - Update to use new SchedulerService for quiet hours checking
  - Update to use enhanced LLM service for message generation
  - Update to use MessagingAdapter for platform-agnostic delivery
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 10.2 Enhance schedule_upcoming_check_ins task
  - Update to use SchedulerService for availability-aware scheduling
  - Implement adaptive frequency logic
  - _Requirements: 2.6, 3.4, 3.5, 3.6_

- [x] 10.3 Create ghosting detection task
  - Implement periodic task to check for users with missed check-ins
  - Trigger appropriate responses based on ghosting stage
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 10.4 Create blocker followup task
  - Implement task to schedule followup check-ins for blocked tasks
  - Use ConversationManager to maintain context
  - _Requirements: 4.2, 4.6_

- [x] 11. Implement minimal response handling
- [x] 11.1 Add minimal response detection to check-in response handler
  - Detect responses with 10 or fewer characters
  - Accept and process without over-questioning
  - _Requirements: 12.1, 12.2_

- [x] 11.2 Write property test for minimal response acceptance
  - **Property 22: Minimal response acceptance**
  - **Validates: Requirements 12.1**

- [x] 12. Implement Discord bot enhancements
- [x] 12.1 Create Discord bot message sending endpoint
  - Implement HTTP endpoint for backend to trigger Discord messages
  - Handle Discord user ID to channel mapping
  - _Requirements: 7.1_

- [x] 12.2 Create Discord bot message receiving handler
  - Implement Discord event handler for incoming messages
  - Route messages to backend API
  - _Requirements: 7.1_

- [x] 12.3 Implement Discord-specific error handling
  - Handle user blocking bot
  - Handle missing permissions
  - Handle rate limiting
  - _Requirements: 7.4_

- [x] 13. Implement web interface for onboarding
- [x] 13.1 Create onboarding flow UI
  - Build welcome screen
  - Build tone selection interface
  - Build availability setup interface
  - _Requirements: 6.2, 8.1, 8.2_

- [x] 13.2 Create project creation UI
  - Build project description input
  - Build clarification conversation interface
  - Build task breakdown review interface
  - Build timeline approval interface
  - _Requirements: 1.1, 1.2, 1.3, 2.4, 2.5_

- [x] 13.3 Create timeline review and management UI
  - Build timeline visualization
  - Build task status tracking
  - Build check-in history view
  - _Requirements: 7.2_

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement error handling and fallbacks
- [x] 15.1 Implement LLM service fallback templates
  - Create template messages for common check-in types
  - Use templates when LLM API fails
  - _Requirements: 3.1_

- [x] 15.2 Implement timezone validation and error handling
  - Validate timezone strings against IANA database
  - Default to UTC for invalid timezones
  - Prompt user to update invalid timezone
  - _Requirements: 8.5_

- [x] 15.3 Implement database connection error handling
  - Add connection health checks
  - Implement retry logic for transient failures
  - _Requirements: All_

- [x] 15.4 Implement concurrent rescheduling protection
  - Add database-level locking for task updates
  - Implement optimistic locking
  - _Requirements: 5.4_

- [x] 16. Implement monitoring and logging
- [x] 16.1 Add structured logging throughout application
  - Add correlation IDs to all requests
  - Log LLM requests and responses (with PII redaction)
  - Log scheduler decisions
  - _Requirements: All_

- [x] 16.2 Implement key metrics tracking
  - Track check-in response rate
  - Track message delivery success rate
  - Track task completion rate
  - Track rescheduling frequency
  - _Requirements: 3.4, 3.5, 7.4_

- [x] 16.3 Configure alerts for critical failures
  - Alert on LLM API failures
  - Alert on message delivery failures
  - Alert on database connection issues
  - _Requirements: All_

- [x] 17. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
