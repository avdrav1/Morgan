# Implementation Plan

- [x] 1. Set up database schema and models
  - Create milestones table with proper indexes
  - Create project_plan_conversations table for conversation state
  - Add database migration scripts
  - _Requirements: 1.1, 5.2, 6.1_

- [x] 1.1 Write property test for milestone data persistence
  - **Property 5: Milestone completion state persistence**
  - **Validates: Requirements 5.2**

- [x] 2. Implement core data models and services
  - [x] 2.1 Create Milestone SQLAlchemy model
    - Define Milestone model with all fields
    - Add relationships to Project model
    - Implement status enum (PENDING, IN_PROGRESS, COMPLETED)
    - _Requirements: 1.3, 5.2_

  - [x] 2.2 Create ProjectPlanConversation model
    - Define conversation tracking model
    - Add JSON fields for pending confirmations and history
    - _Requirements: 2.2, 6.1_

  - [x] 2.3 Implement ProjectPlanService base operations
    - Write get_project_plan method
    - Write add_milestone method
    - Write update_milestone method
    - Write mark_milestone_complete method
    - _Requirements: 1.1, 3.3, 3.4, 5.1, 5.2_

  - [x] 2.4 Write property test for project plan retrieval
    - **Property 1: Project plan retrieval completeness**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 2.5 Write property test for multi-project isolation
    - **Property 6: Multi-project context isolation**
    - **Validates: Requirements 7.1, 7.2, 7.3**

- [x] 3. Implement milestone generation and timeline management
  - [x] 3.1 Create MilestoneGenerator service
    - Implement algorithm to calculate milestone count based on project duration
    - Implement even distribution of milestones across timeline
    - Use LLM to generate milestone titles from project goal
    - _Requirements: 1.4_

  - [x] 3.2 Create TimelineAdjuster service
    - Implement proportional date adjustment algorithm
    - Add minimum spacing validation (3 days between milestones)
    - Implement update_deadline method with milestone adjustment
    - _Requirements: 4.1, 4.2, 4.5_

  - [x] 3.3 Write property test for deadline update propagation
    - **Property 4: Deadline update propagation**
    - **Validates: Requirements 4.1, 4.2, 4.5**

  - [x] 3.4 Write unit tests for milestone generation
    - Test milestone count calculation for various project durations
    - Test milestone distribution algorithm
    - Test LLM integration for milestone title generation
    - _Requirements: 1.4_

- [x] 4. Implement intent classification system
  - [x] 4.1 Create Intent and IntentType models
    - Define Intent dataclass with type, parameters, and confidence
    - Define IntentType enum (VIEW_PLAN, EDIT_DEADLINE, ADD_MILESTONE, etc.)
    - _Requirements: 6.1, 6.2_

  - [x] 4.2 Implement IntentClassifier service
    - Create LLM prompt template for intent classification
    - Implement classify_intent method
    - Add parameter extraction logic (dates, milestone names, etc.)
    - Implement confidence scoring
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 4.3 Write property test for intent classification consistency
    - **Property 3: Intent classification consistency**
    - **Validates: Requirements 6.1, 6.2**

  - [x] 4.4 Write unit tests for intent classification
    - Test various phrasings for each intent type
    - Test parameter extraction accuracy
    - Test ambiguous input handling
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 5. Implement Discord response formatting
  - [x] 5.1 Create DiscordProjectPlanFormatter service
    - Implement format_project_plan method
    - Implement format_milestone method with status emojis
    - Implement format_timeline_summary method
    - Add message splitting logic for long content
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 5.2 Write property test for Discord message length compliance
    - **Property 7: Discord message length compliance**
    - **Validates: Requirements 8.2, 8.5**

  - [x] 5.3 Write property test for relative date accuracy
    - **Property 8: Relative date accuracy**
    - **Validates: Requirements 8.3**

  - [x] 5.4 Write property test for milestone chronological ordering
    - **Property 2: Milestone chronological ordering**
    - **Validates: Requirements 1.3**

  - [x] 5.5 Write unit tests for formatting
    - Test Discord markdown formatting
    - Test emoji status indicators
    - Test message splitting at natural boundaries
    - _Requirements: 8.1, 8.2, 8.4_

- [x] 6. Implement conversation management
  - [x] 6.1 Create ProjectPlanConversationManager service
    - Implement conversation state tracking
    - Implement conversation history management (last 10 messages)
    - Add pending confirmation handling
    - _Requirements: 2.2, 3.4, 4.3_

  - [x] 6.2 Write property test for conversation history preservation
    - **Property 10: Conversation history preservation**
    - **Validates: Requirements 2.2, 6.1**

  - [x] 6.3 Write property test for change confirmation requirement
    - **Property 9: Change confirmation requirement**
    - **Validates: Requirements 3.4, 4.3**

- [x] 7. Implement Discord bot handler
  - [x] 7.1 Create ProjectPlanHandler class
    - Implement handle_message method
    - Add routing logic based on classified intent
    - Integrate with IntentClassifier
    - Integrate with ProjectPlanService
    - Integrate with DiscordProjectPlanFormatter
    - _Requirements: 1.1, 2.1, 3.1, 6.1_

  - [x] 7.2 Add project plan handler to Discord bot main
    - Update bot message routing to use ProjectPlanHandler for non-onboarding users
    - Add error handling and logging
    - _Requirements: 1.1, 2.1_

  - [x] 7.3 Write integration tests for Discord bot handler
    - Test end-to-end flow: view plan
    - Test end-to-end flow: edit deadline
    - Test end-to-end flow: add milestone
    - Test end-to-end flow: mark milestone complete
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_

- [x] 8. Implement specific intent handlers
  - [x] 8.1 Implement VIEW_PLAN intent handler
    - Retrieve project and milestones
    - Generate initial milestones if none exist
    - Format and send response
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 8.2 Implement EDIT_DEADLINE intent handler
    - Parse new deadline from parameters
    - Calculate timeline adjustments
    - Request user confirmation for milestone changes
    - Apply changes after confirmation
    - _Requirements: 3.1, 4.1, 4.2, 4.3, 4.5_

  - [x] 8.3 Implement ADD_MILESTONE intent handler
    - Extract milestone details from parameters
    - Validate milestone date is before project deadline
    - Add milestone to database
    - Confirm addition to user
    - _Requirements: 3.3_

  - [x] 8.4 Implement EDIT_MILESTONE intent handler
    - Identify which milestone to edit
    - Extract changes from parameters
    - Update milestone in database
    - Confirm changes to user
    - _Requirements: 3.2_

  - [x] 8.5 Implement DELETE_MILESTONE intent handler
    - Identify which milestone to delete
    - Request confirmation from user
    - Delete milestone after confirmation
    - Confirm deletion to user
    - _Requirements: 3.4_

  - [x] 8.6 Implement MARK_COMPLETE intent handler
    - Identify which milestone was completed
    - Mark milestone as complete with timestamp
    - Send celebration message
    - Show next upcoming milestone
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 8.7 Implement ASK_QUESTION intent handler
    - Use LLM with project context to answer question
    - Format response in user's preferred tone
    - Handle follow-up questions
    - _Requirements: 2.1, 2.2, 2.5_

  - [x] 8.8 Implement UNCLEAR intent handler
    - Ask clarifying questions
    - Provide examples of what user can do
    - _Requirements: 2.3, 6.4_

- [x] 9. Implement multi-project support
  - [x] 9.1 Add project selection logic
    - Detect when user has multiple projects
    - Ask user to specify which project if ambiguous
    - Handle "current project" references
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 9.2 Add project context to all responses
    - Include project name in formatted responses
    - Maintain project context across conversation
    - _Requirements: 7.4, 7.5_

- [x] 10. Implement proactive suggestions
  - [x] 10.1 Create SuggestionEngine service
    - Implement uneven milestone distribution detection
    - Implement large milestone detection
    - Implement deadline pressure detection
    - Generate suggestion messages with reasoning
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 10.2 Add suggestion tracking
    - Track which suggestions have been shown
    - Respect user's decision to decline suggestions
    - Don't repeat declined suggestions
    - _Requirements: 9.5_

  - [x] 10.3 Write unit tests for suggestion engine
    - Test uneven distribution detection
    - Test large milestone detection
    - Test deadline pressure detection
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 11. Add comprehensive logging and monitoring
  - [x] 11.1 Add logging to all services
    - Log project plan requests with user and project IDs
    - Log all modifications with before/after states
    - Log LLM prompts and responses (PII-redacted)
    - Log errors with full context
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 11.2 Add metrics collection
    - Track common request types
    - Track conversation patterns
    - Track error rates by intent type
    - _Requirements: 10.5_

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
