# Implementation Plan

- [x] 1. Create database models and migrations for onboarding sessions
  - Create `OnboardingSession` model with all required fields
  - Create Alembic migration for onboarding_sessions table
  - Add indexes for user_id and discord_id lookups
  - _Requirements: 6.1, 6.2_

- [x] 2. Implement onboarding state machine
  - Define `OnboardingState` enum with all states
  - Create state transition validation logic
  - Implement state machine rules and valid transitions
  - _Requirements: 2.1_

- [x] 2.1 Write property test for state transition validity
  - **Property 2: State transition validity**
  - **Validates: Requirements 2.1**

- [x] 3. Build OnboardingService core functionality
  - Implement `start_onboarding()` method
  - Implement `process_message()` method with state handling
  - Implement `get_session()` and session retrieval
  - Implement `cancel_onboarding()` and `restart_onboarding()`
  - Implement `complete_onboarding()` with project creation
  - _Requirements: 1.4, 2.1, 5.1, 6.1, 9.1_

- [x] 3.1 Write property test for session creation
  - **Property 1: Onboarding session creation**
  - **Validates: Requirements 1.4**

- [x] 3.2 Write property test for data persistence
  - **Property 3: Data persistence**
  - **Validates: Requirements 6.2**

- [x] 3.3 Write property test for completion idempotency
  - **Property 5: Completion idempotency**
  - **Validates: Requirements 5.1**

- [x] 3.4 Write property test for cancellation cleanup
  - **Property 8: Cancellation cleanup**
  - **Validates: Requirements 9.1, 9.2**

- [x] 4. Implement input validation and parsing
  - Create date parser with multiple format support
  - Implement deadline validation (no past dates)
  - Create tone preference validator
  - Implement check-in frequency parser
  - Add ambiguous input detection
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4.1 Write property test for input validation
  - **Property 7: Input validation**
  - **Validates: Requirements 3.1, 3.2**

- [x] 5. Integrate LLM service for conversational responses
  - Create prompt templates for each onboarding step
  - Implement LLM call with conversation history context
  - Add fallback to templated responses on LLM failure
  - Implement tone-aware response generation
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 5.1 Write property test for conversation history preservation
  - **Property 9: Conversation history preservation**
  - **Validates: Requirements 8.3**

- [x] 6. Create webhook endpoint for onboarding trigger
  - Implement `POST /webhooks/onboarding/start` endpoint
  - Add authentication/authorization for webhook
  - Validate webhook payload
  - Trigger onboarding service on new user
  - _Requirements: 1.1_

- [x] 7. Update OAuth callback to trigger onboarding webhook
  - Modify Discord OAuth callback to call webhook for new users
  - Pass user_id, discord_id, and email to webhook
  - Handle webhook call failures gracefully
  - _Requirements: 1.1_

- [x] 8. Implement Discord bot DM handler for onboarding
  - Create `OnboardingBotHandler` class
  - Implement `on_message()` to route DMs to onboarding service
  - Implement `send_onboarding_message()` with Discord formatting
  - Add message queuing to respect rate limits
  - _Requirements: 1.2, 2.1_

- [x] 9. Add DM failure detection and handling
  - Catch `discord.Forbidden` exceptions
  - Log DM delivery failures with context
  - Implement fallback to web onboarding on DM failure
  - Update OAuth callback redirect logic for DM failures
  - _Requirements: 1.3, 1.5, 7.1, 7.2, 7.3_

- [x] 9.1 Write property test for DM failure handling
  - **Property 6: DM failure handling**
  - **Validates: Requirements 7.1, 7.2**

- [x] 10. Implement session resumption logic
  - Add logic to detect returning users with incomplete onboarding
  - Resume from last completed state
  - Restore conversation history
  - Send reminder DMs after 24 hours of inactivity
  - _Requirements: 6.3, 6.4_

- [x] 10.1 Write property test for session resumption
  - **Property 4: Session resumption**
  - **Validates: Requirements 6.4**

- [x] 11. Build project creation integration
  - Implement API call to `POST /api/projects`
  - Map onboarding data to project creation payload
  - Handle API errors and retry logic
  - Mark user as onboarded (`is_new=false`) after success
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 11.1 Write property test for onboarding completion marking
  - **Property 10: Onboarding completion marking**
  - **Validates: Requirements 5.4**

- [x] 12. Add comprehensive logging and monitoring
  - Log all onboarding events with correlation IDs
  - Log state transitions
  - Log errors with full context
  - Implement PII redaction in logs
  - Add metrics for completion rates and drop-offs
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 13. Create web onboarding fallback page
  - Update frontend to show "Check Discord DMs" message for new users
  - Add fallback to web onboarding form if DMs failed
  - Display appropriate messaging based on onboarding method
  - _Requirements: 7.3, 7.4_

- [x] 14. Implement help and control commands
  - Add "help" command handler during onboarding
  - Add "cancel" and "stop" command handlers
  - Add "restart" command handler
  - Provide contextual help based on current step
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 15. Add session cleanup and abandonment handling
  - Implement background job to detect abandoned sessions
  - Send reminder after 24 hours of inactivity
  - Mark sessions as abandoned after 7 days
  - Archive old sessions after 30 days
  - _Requirements: 6.3, 6.5_

- [x] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Create onboarding message templates
  - Write welcome message template
  - Write question templates for each step
  - Write confirmation message template
  - Write error and retry message templates
  - Add tone variations (supportive, direct, casual)
  - _Requirements: 1.2, 2.1, 4.2_

- [x] 18. Add rate limiting and queuing
  - Implement message queue for Discord DMs
  - Add rate limiting (1 message/second per user)
  - Implement exponential backoff for Discord API
  - _Requirements: Implementation Notes_

- [x] 19. Write integration tests for end-to-end flow
  - Test complete onboarding flow from OAuth to project creation
  - Test resumption after interruption
  - Test cancellation and restart
  - Test DM failure fallback to web

- [x] 20. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: Enhanced Conversational Flow

- [x] 21. Enhance webhook message processing with state-based logic
  - Parse user input based on current onboarding state
  - Extract relevant data (project name, goal, deadline, tone, frequency)
  - Validate extracted data using input validators
  - Update session with extracted data
  - Determine next state based on current state and input
  - Transition to next state
  - Generate LLM response for next question
  - Handle validation errors with clarifying questions
  - _Requirements: 2.1, 3.1, 3.2, 8.1, 8.2_

- [x] 22. Add state machine support for summary display
  - Add `SHOW_SUMMARY` state to OnboardingState enum
  - Update state machine to allow transition from CONFIRM_DETAILS to SHOW_SUMMARY
  - Update state machine to allow transition from SHOW_SUMMARY to CREATING_PROJECT
  - _Requirements: 5.1, 5.2_

- [x] 23. Implement project plan generation service
  - Add `generate_completion_summary()` method to OnboardingService
  - Call `llm_service.decompose_project()` to get project tasks/milestones
  - Format summary with user preferences (tone, check-in frequency)
  - Format project plan with tasks and estimated timeline
  - Combine preferences and plan into comprehensive summary
  - _Requirements: 5.1, 5.2_

- [x] 24. Integrate summary generation into completion flow
  - Modify `complete_onboarding()` to generate summary before creating project
  - Send summary message to user via Discord DM
  - Wait for user confirmation before creating project
  - Handle user edits or changes to plan
  - _Requirements: 5.1, 5.2_

- [x] 25. Enhance input parsing for natural language
  - Improve date parser to handle more natural language formats
  - Add tone preference extraction from conversational responses
  - Add check-in frequency extraction from natural language
  - Handle ambiguous inputs with clarifying questions
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 26. Add state-specific response generation
  - Enhance `generate_response()` to use state-specific prompts
  - Include collected data in context for each response
  - Generate acknowledgments for user responses
  - Generate clarifying questions for ambiguous inputs
  - Maintain conversational tone throughout
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 27. Test enhanced conversational flow
  - Test complete flow with natural language inputs
  - Test state transitions with various user responses
  - Test summary generation with project plan
  - Test error handling and clarifying questions
  - Verify LLM responses are contextual and natural

- [x] 28. Final checkpoint - Verify enhanced flow
  - Ensure all tests pass
  - Manually test complete onboarding flow via Discord
  - Verify summary includes preferences and project plan
  - Verify conversational responses are natural and helpful
