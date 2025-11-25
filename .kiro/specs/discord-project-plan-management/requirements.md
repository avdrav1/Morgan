# Requirements Document

## Introduction

This document specifies the requirements for managing project plans through Discord Direct Messages after onboarding is complete. Users should be able to view their project plan with milestones, ask questions about their plan, and make edits through natural conversation with Morgan (the accountability assistant bot).

## Glossary

- **Morgan**: The accountability assistant Discord bot that interacts with users
- **Project Plan**: A structured breakdown of the user's project including milestones, tasks, and timeline
- **Milestone**: A significant checkpoint or deliverable in the project timeline
- **Timeline**: The schedule of milestones and tasks from the current date to the project deadline
- **Discord DM**: Discord Direct Message, a private conversation between Morgan and the user
- **LLM Service**: The language model service used to generate conversational responses and understand user intent
- **Project Context**: The full project information including name, goal, deadline, current progress, and user preferences

## Requirements

### Requirement 1

**User Story:** As a user who just completed onboarding, I want to view my project plan with milestones, so that I understand what I need to accomplish and when.

#### Acceptance Criteria

1. WHEN a user asks to see their project plan THEN Morgan SHALL retrieve the project details from the database
2. WHEN displaying the project plan THEN Morgan SHALL show the project name, goal, deadline, and timeline starting from today
3. WHEN displaying milestones THEN Morgan SHALL present them in chronological order with dates
4. WHEN the project has no milestones yet THEN Morgan SHALL generate initial milestones based on the project goal and deadline
5. WHEN displaying the plan THEN Morgan SHALL format the information clearly for Discord's message format

### Requirement 2

**User Story:** As a user viewing my project plan, I want to ask open-ended questions about my plan, so that I can better understand my timeline and commitments.

#### Acceptance Criteria

1. WHEN a user asks a question about their project THEN Morgan SHALL use the LLM Service to understand the intent
2. WHEN answering questions THEN Morgan SHALL reference the specific project context and timeline
3. WHEN a question is ambiguous THEN Morgan SHALL ask for clarification
4. WHEN a question cannot be answered with available data THEN Morgan SHALL explain what information is missing
5. WHEN answering THEN Morgan SHALL use the user's preferred communication tone

### Requirement 3

**User Story:** As a user managing my project, I want to edit my project plan through conversation, so that I can adjust my timeline and milestones as my situation changes.

#### Acceptance Criteria

1. WHEN a user requests to change their deadline THEN Morgan SHALL parse the new date and update the project
2. WHEN a user wants to modify a milestone THEN Morgan SHALL identify which milestone and what changes to make
3. WHEN a user wants to add a new milestone THEN Morgan SHALL collect the necessary details and add it to the plan
4. WHEN a user wants to remove a milestone THEN Morgan SHALL confirm the deletion before removing it
5. WHEN changes are made THEN Morgan SHALL confirm the updates and show the revised timeline

### Requirement 4

**User Story:** As a user, I want Morgan to automatically adjust milestone dates when I change my project deadline, so that my plan stays realistic and achievable.

#### Acceptance Criteria

1. WHEN the project deadline is extended THEN Morgan SHALL propose redistributing milestones across the new timeline
2. WHEN the project deadline is shortened THEN Morgan SHALL warn if milestones may be too compressed
3. WHEN milestone dates are adjusted THEN Morgan SHALL ask for user confirmation before saving changes
4. WHEN the user rejects proposed changes THEN Morgan SHALL keep the original milestone dates
5. WHEN timeline adjustments are confirmed THEN Morgan SHALL update all affected milestones in the database

### Requirement 5

**User Story:** As a user, I want to mark milestones as complete through conversation, so that I can track my progress naturally.

#### Acceptance Criteria

1. WHEN a user indicates they completed a milestone THEN Morgan SHALL identify which milestone was completed
2. WHEN marking a milestone complete THEN Morgan SHALL update the milestone status in the database
3. WHEN a milestone is completed THEN Morgan SHALL celebrate the achievement with an encouraging message
4. WHEN a milestone is completed THEN Morgan SHALL show the next upcoming milestone
5. WHEN all milestones are complete THEN Morgan SHALL congratulate the user on project completion

### Requirement 6

**User Story:** As a user, I want Morgan to understand natural language requests about my project, so that I don't need to learn specific commands.

#### Acceptance Criteria

1. WHEN a user makes a request in natural language THEN Morgan SHALL use the LLM Service to parse the intent
2. WHEN the intent is to view the plan THEN Morgan SHALL display the project plan
3. WHEN the intent is to modify the plan THEN Morgan SHALL collect necessary information and make the changes
4. WHEN the intent is unclear THEN Morgan SHALL ask clarifying questions
5. WHEN multiple interpretations are possible THEN Morgan SHALL present options for the user to choose from

### Requirement 7

**User Story:** As a user with multiple projects, I want to specify which project I'm asking about, so that Morgan provides information about the correct project.

#### Acceptance Criteria

1. WHEN a user has multiple projects THEN Morgan SHALL ask which project they're referring to if not specified
2. WHEN a user mentions a project by name THEN Morgan SHALL use that project's context
3. WHEN a user says "current project" or "active project" THEN Morgan SHALL use the most recently active project
4. WHEN displaying information THEN Morgan SHALL always include the project name for clarity
5. WHEN switching between projects THEN Morgan SHALL maintain context for the conversation

### Requirement 8

**User Story:** As a user, I want to see my project plan formatted appropriately for Discord, so that it's easy to read on mobile and desktop.

#### Acceptance Criteria

1. WHEN displaying the project plan THEN Morgan SHALL use Discord markdown formatting for readability
2. WHEN the plan is too long for one message THEN Morgan SHALL split it across multiple messages
3. WHEN showing dates THEN Morgan SHALL use relative dates (e.g., "in 3 days") alongside absolute dates
4. WHEN showing milestones THEN Morgan SHALL use emojis or symbols to indicate status (pending, in progress, complete)
5. WHEN the message exceeds Discord's character limit THEN Morgan SHALL summarize and offer to show details

### Requirement 9

**User Story:** As a user, I want Morgan to proactively suggest improvements to my project plan, so that I can optimize my timeline and approach.

#### Acceptance Criteria

1. WHEN milestones are unevenly distributed THEN Morgan SHALL suggest a more balanced timeline
2. WHEN a milestone seems too large THEN Morgan SHALL suggest breaking it into smaller milestones
3. WHEN the deadline is approaching with many incomplete milestones THEN Morgan SHALL suggest prioritization
4. WHEN suggesting changes THEN Morgan SHALL explain the reasoning behind the suggestion
5. WHEN the user declines a suggestion THEN Morgan SHALL respect the decision and not repeat the suggestion

### Requirement 10

**User Story:** As a system operator, I want all project plan interactions logged, so that I can debug issues and improve the conversation quality.

#### Acceptance Criteria

1. WHEN a user requests to view their plan THEN the system SHALL log the request with user ID and project ID
2. WHEN changes are made to a project THEN the system SHALL log the before and after states
3. WHEN the LLM Service is used THEN the system SHALL log the prompt and response (PII-redacted)
4. WHEN errors occur THEN the system SHALL log the error with full context
5. WHEN analyzing usage THEN the system SHALL provide metrics on common requests and conversation patterns
