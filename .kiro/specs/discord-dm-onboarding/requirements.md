# Requirements Document

## Introduction

This document specifies the requirements for a Discord Direct Message (DM) based onboarding flow for new users of the accountability assistant. When a user signs up via Discord OAuth, they will complete the entire onboarding process through a conversational interface in Discord DMs, eliminating the need for web-based onboarding forms.

## Glossary

- **Discord Bot**: The automated Discord application that sends and receives direct messages with users
- **Onboarding Flow**: The sequence of questions and interactions that collect user information and create their first project
- **Onboarding State**: The current step in the onboarding process for a given user
- **Discord DM**: Discord Direct Message, a private one-on-one conversation between the bot and a user
- **Backend API**: The FastAPI backend service that stores user and project data
- **LLM Service**: The language model service used to generate conversational responses
- **New User**: A user who has just completed Discord OAuth and has `is_new=true`
- **Onboarding Session**: A stateful conversation tracking a user's progress through onboarding

## Requirements

### Requirement 1

**User Story:** As a new user who just signed up via Discord OAuth, I want to receive a welcome message in Discord DMs, so that I can start using the accountability assistant immediately without leaving Discord.

#### Acceptance Criteria

1. WHEN a new user completes Discord OAuth THEN the Discord Bot SHALL send a welcome DM within 5 seconds
2. WHEN the welcome DM is sent THEN the Discord Bot SHALL include a friendly greeting and explanation of the onboarding process
3. WHEN the user has not enabled DMs from server members THEN the system SHALL handle the DM failure gracefully and redirect to web onboarding
4. WHEN the welcome DM is successfully sent THEN the system SHALL create an onboarding session for the user
5. WHEN the welcome DM fails to send THEN the system SHALL log the failure and mark the user for web-based onboarding

### Requirement 2

**User Story:** As a new user in the onboarding flow, I want to provide my project information conversationally through Discord DMs, so that I can set up my accountability assistant naturally without filling out forms.

#### Acceptance Criteria

1. WHEN the user responds to any onboarding question THEN the Discord Bot SHALL acknowledge the response and ask the next question
2. WHEN the user provides a project name THEN the Discord Bot SHALL store the project name and ask for the project goal
3. WHEN the user provides a project goal THEN the Discord Bot SHALL store the goal and ask for the deadline
4. WHEN the user provides a deadline THEN the Discord Bot SHALL parse the date and ask for confirmation if ambiguous
5. WHEN the user provides check-in preferences THEN the Discord Bot SHALL store the preferences and ask for communication tone preference

### Requirement 3

**User Story:** As a new user completing onboarding, I want the system to validate my inputs and ask for clarification when needed, so that my project is set up correctly.

#### Acceptance Criteria

1. WHEN the user provides an invalid date format THEN the Discord Bot SHALL ask for clarification with examples of valid formats
2. WHEN the user provides a past deadline THEN the Discord Bot SHALL warn the user and ask for confirmation
3. WHEN the user provides an ambiguous response THEN the Discord Bot SHALL ask a clarifying question
4. WHEN the user provides a valid response THEN the Discord Bot SHALL confirm understanding before proceeding
5. WHEN the user requests to go back to a previous question THEN the Discord Bot SHALL allow editing of previous responses

### Requirement 4

**User Story:** As a new user, I want to choose my preferred communication tone during onboarding, so that the assistant's messages match my preferences from the start.

#### Acceptance Criteria

1. WHEN the Discord Bot asks about tone preference THEN the system SHALL present options: supportive, direct, and casual
2. WHEN the user selects a tone THEN the Discord Bot SHALL confirm the selection with an example message in that tone
3. WHEN the user wants to change the tone THEN the Discord Bot SHALL allow re-selection
4. WHEN the tone is confirmed THEN the system SHALL store the preference in the user profile
5. WHEN no tone is selected within 5 minutes THEN the system SHALL default to supportive tone

### Requirement 5

**User Story:** As a new user completing onboarding, I want the system to create my project and confirm everything is set up, so that I know the accountability assistant is ready to use.

#### Acceptance Criteria

1. WHEN all onboarding information is collected THEN the Discord Bot SHALL create the project via the Backend API
2. WHEN the project is created successfully THEN the Discord Bot SHALL send a confirmation message with project details
3. WHEN the project creation fails THEN the Discord Bot SHALL inform the user and offer to retry or contact support
4. WHEN onboarding is complete THEN the system SHALL mark the user as no longer new (`is_new=false`)
5. WHEN onboarding is complete THEN the Discord Bot SHALL explain how to interact with the assistant going forward

### Requirement 6

**User Story:** As a system administrator, I want the onboarding state to be persisted, so that users can resume onboarding if they get interrupted.

#### Acceptance Criteria

1. WHEN a user starts onboarding THEN the system SHALL create an onboarding session in the database
2. WHEN the user provides information THEN the system SHALL update the onboarding session after each response
3. WHEN the user stops responding for 24 hours THEN the system SHALL send a gentle reminder
4. WHEN the user returns after interruption THEN the Discord Bot SHALL resume from the last completed step
5. WHEN onboarding is completed or abandoned THEN the system SHALL archive the onboarding session

### Requirement 7

**User Story:** As a user who cannot receive Discord DMs, I want to be redirected to web-based onboarding, so that I can still complete the setup process.

#### Acceptance Criteria

1. WHEN the Discord Bot cannot send a DM to the user THEN the system SHALL detect the failure
2. WHEN DM delivery fails THEN the system SHALL log the failure reason
3. WHEN DM delivery fails THEN the OAuth callback SHALL redirect to web onboarding instead of the dashboard
4. WHEN the user completes web onboarding THEN the system SHALL mark them as onboarded
5. WHEN the user later enables DMs THEN the system SHALL notify them that Discord DM features are now available

### Requirement 8

**User Story:** As a developer, I want the onboarding conversation to use the existing LLM service, so that responses are natural and contextual.

#### Acceptance Criteria

1. WHEN generating onboarding messages THEN the Discord Bot SHALL use the LLM Service for natural language generation
2. WHEN the user provides unexpected input THEN the LLM Service SHALL generate an appropriate clarifying response
3. WHEN the conversation context is needed THEN the system SHALL provide the full onboarding history to the LLM
4. WHEN generating responses THEN the system SHALL include the user's chosen tone preference
5. WHEN the LLM Service is unavailable THEN the system SHALL fall back to templated responses

### Requirement 9

**User Story:** As a new user, I want to be able to cancel or restart the onboarding process, so that I have control over my setup experience.

#### Acceptance Criteria

1. WHEN the user sends "cancel" or "stop" during onboarding THEN the Discord Bot SHALL pause the onboarding flow
2. WHEN onboarding is paused THEN the Discord Bot SHALL ask if the user wants to resume later or start over
3. WHEN the user chooses to start over THEN the system SHALL clear the current onboarding session and begin again
4. WHEN the user chooses to resume later THEN the system SHALL preserve the onboarding state
5. WHEN the user sends "help" during onboarding THEN the Discord Bot SHALL explain the current step and available commands

### Requirement 10

**User Story:** As a system operator, I want comprehensive logging of the onboarding flow, so that I can debug issues and improve the user experience.

#### Acceptance Criteria

1. WHEN any onboarding event occurs THEN the system SHALL log the event with correlation ID
2. WHEN the user progresses through onboarding THEN the system SHALL log each state transition
3. WHEN errors occur during onboarding THEN the system SHALL log the error with full context
4. WHEN onboarding is completed THEN the system SHALL log the completion time and collected data (PII-redacted)
5. WHEN analyzing onboarding metrics THEN the system SHALL provide aggregated statistics on completion rates and drop-off points
