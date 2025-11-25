# Requirements Document

## Introduction

The Proactive Accountability Assistant is an LLM-powered digital companion that functions as a personal project manager. The system transforms vague goals into structured action plans, proactively checks in on progress, diagnoses obstacles, and coaches users through friction points. Unlike passive reminder systems, this assistant is intentional, assertive, and adaptive—pushing users forward while respecting their boundaries and adapting to their communication style.

## Glossary

- **Assistant**: The LLM-powered conversational agent that manages user accountability
- **Project**: A user-defined goal with associated tasks and timeline
- **Task**: A discrete, actionable step within a project
- **Check-In**: A proactive message initiated by the Assistant to verify progress
- **Blocker**: An obstacle preventing task completion
- **Quiet Hours**: User-defined time periods when the Assistant SHALL NOT send messages
- **Tone**: The communication style and personality of the Assistant
- **System Prompt**: The configurable instructions that define the Assistant's personality
- **Timeline**: The schedule of tasks with deadlines for a project
- **Rescheduling**: The conversational process of adjusting task deadlines

## Requirements

### Requirement 1: Project Intake and Goal Understanding

**User Story:** As a user, I want to describe my goal in my own words and have the Assistant understand what I'm trying to accomplish without requiring rigid formatting.

#### Acceptance Criteria

1. WHEN a user provides a free-form project description THEN the Assistant SHALL accept the input and initiate clarification
2. WHEN the project description is ambiguous THEN the Assistant SHALL ask targeted questions about scope, deadlines, and constraints
3. WHEN clarification is complete THEN the Assistant SHALL confirm understanding with the user before proceeding to task decomposition
4. WHEN a user has multiple projects THEN the Assistant SHALL store all projects while focusing on one active project at a time

### Requirement 2: Task Decomposition and Timeline Generation

**User Story:** As a user, I want the Assistant to break my big goal into small steps so I know exactly what to do next.

#### Acceptance Criteria

1. WHEN the Assistant decomposes a project THEN the Assistant SHALL generate between 5 and 20 tasks based on project complexity
2. WHEN tasks are generated THEN the Assistant SHALL assign realistic time estimates for each task
3. WHEN tasks have dependencies THEN the Assistant SHALL sequence tasks in logical order
4. WHEN the timeline is generated THEN the Assistant SHALL present the proposed timeline to the user for approval
5. WHEN the user reviews the timeline THEN the Assistant SHALL allow modifications before confirmation
6. WHEN generating timelines THEN the Assistant SHALL account for user-specified availability and constraints

### Requirement 3: Proactive Scheduling and Check-Ins

**User Story:** As a user, I want the Assistant to reach out when I should be working on something, but only during times I've said I'm available.

#### Acceptance Criteria

1. WHEN a task deadline approaches THEN the Assistant SHALL initiate a check-in message aligned with the deadline
2. WHEN the user has defined quiet hours THEN the Assistant SHALL NOT send messages during those time periods
3. WHEN a task is approaching its due date THEN the Assistant SHALL send reminders before the task is late
4. WHEN the user demonstrates low responsiveness THEN the Assistant SHALL adapt check-in frequency accordingly
5. WHEN the user demonstrates high responsiveness THEN the Assistant SHALL maintain or increase check-in frequency
6. WHEN scheduling check-ins THEN the Assistant SHALL respect user-defined availability windows

### Requirement 4: Blocker Diagnosis and Coaching

**User Story:** As a user, when I'm stuck, I want the Assistant to help me figure out why and suggest ways to get unstuck.

#### Acceptance Criteria

1. WHEN a user reports difficulty completing a task THEN the Assistant SHALL ask targeted questions to understand the obstacle
2. WHEN a user misses a deadline THEN the Assistant SHALL initiate a coaching conversation to diagnose the root cause
3. WHEN the Assistant identifies a blocker pattern THEN the Assistant SHALL recognize the blocker type from time constraints, clarity issues, emotional resistance, external dependencies, or scope creep
4. WHEN a blocker is diagnosed THEN the Assistant SHALL offer specific strategies based on the blocker type
5. WHEN providing coaching THEN the Assistant SHALL provide options rather than prescriptions
6. WHEN timeline adjustment is necessary THEN the Assistant SHALL adjust the timeline through conversation with the user

### Requirement 5: Conversational Rescheduling

**User Story:** As a user, when I can't finish something on time, I want to explain why and work with the Assistant to set a new deadline that makes sense.

#### Acceptance Criteria

1. WHEN a user reports inability to complete a task THEN the Assistant SHALL engage in conversation to understand the reason
2. WHEN rescheduling is needed THEN the Assistant SHALL ask about new constraints or changed circumstances
3. WHEN new information is gathered THEN the Assistant SHALL propose a revised timeline based on the conversation
4. WHEN a revised timeline is proposed THEN the Assistant SHALL require explicit user confirmation before updating the schedule
5. WHEN rescheduling occurs THEN the Assistant SHALL track the rescheduling pattern to inform future planning

### Requirement 6: Personality and Tone Customization

**User Story:** As a user, I want to choose how the Assistant talks to me—sometimes I need a push, sometimes I need support.

#### Acceptance Criteria

1. WHEN a user configures the Assistant THEN the Assistant SHALL provide direct access to the system prompt used for conversation
2. WHEN selecting a tone THEN the Assistant SHALL offer preset templates including Coach, Manager, Accountability Buddy, and Drill Sergeant modes
3. WHEN a user selects Coach mode THEN the Assistant SHALL use supportive, encouraging, growth-focused language
4. WHEN a user selects Manager mode THEN the Assistant SHALL use professional, organized, results-oriented language
5. WHEN a user selects Accountability Buddy mode THEN the Assistant SHALL use friendly, peer-like, motivational language
6. WHEN a user selects Drill Sergeant mode THEN the Assistant SHALL use direct, demanding language with strategic pressure including measured guilt-tripping when appropriate
7. WHEN a user wants customization THEN the Assistant SHALL allow editing of system prompts with custom instructions
8. WHEN a user has multiple projects THEN the Assistant SHALL enable tone switching between projects
9. WHEN a user adds project context THEN the Assistant SHALL support project-specific context additions to the system prompt

### Requirement 7: Messaging Platform Support

**User Story:** As a user, I want the Assistant to reach me where I already check messages, not force me to use another app.

#### Acceptance Criteria

1. WHEN the system is deployed THEN the Assistant SHALL support Discord as the primary messaging channel
2. WHEN the system is deployed THEN the Assistant SHALL provide a web interface for onboarding and timeline review
3. WHEN a message is sent THEN the Assistant SHALL format messages appropriately for the target platform
4. WHEN message delivery fails THEN the Assistant SHALL handle delivery status and retry with exponential backoff

### Requirement 8: User Availability Management

**User Story:** As a user, I want to define when I'm available so the Assistant never interrupts me during protected time.

#### Acceptance Criteria

1. WHEN a user configures availability THEN the Assistant SHALL allow specification of quiet hours
2. WHEN a user configures availability THEN the Assistant SHALL allow specification of general availability patterns
3. WHEN quiet hours are active THEN the Assistant SHALL NOT send any messages during those periods
4. WHEN scheduling check-ins THEN the Assistant SHALL calculate check-in times based on user availability and task deadlines
5. WHEN the user changes time zones THEN the Assistant SHALL respect the user's current time zone settings

### Requirement 9: User Ghosting Handling

**User Story:** As a user who sometimes gets overwhelmed, I want the Assistant to give me space when I'm not responding, but also check if I want to continue.

#### Acceptance Criteria

1. WHEN a user misses 2 consecutive check-ins THEN the Assistant SHALL send an empathetic message acknowledging difficulty
2. WHEN a user misses 4 consecutive check-ins THEN the Assistant SHALL ask if the user wants to pause the project or adjust the approach
3. WHEN a user misses 7 consecutive check-ins THEN the Assistant SHALL offer to archive the project and check in again later
4. WHEN a user resumes engagement THEN the Assistant SHALL welcome the user back and assess current project status

### Requirement 10: Data Privacy and User Control

**User Story:** As a user, I want full control over my data and the ability to delete or export it at any time.

#### Acceptance Criteria

1. WHEN a user requests data deletion THEN the Assistant SHALL delete all user data within 30 days
2. WHEN a user requests data export THEN the Assistant SHALL provide all project data in a portable format
3. WHEN a user wants to pause messaging THEN the Assistant SHALL allow disabling of proactive messages
4. WHEN collecting data THEN the Assistant SHALL collect only project goals, tasks, timelines, preferences, and conversation history
5. WHEN a user expresses severe distress THEN the Assistant SHALL suggest professional resources and clarify that it is not a therapy tool

### Requirement 11: Progress Tracking and Completion

**User Story:** As a user, I want the Assistant to acknowledge my progress and help me reflect when I complete a project.

#### Acceptance Criteria

1. WHEN a user completes a task THEN the Assistant SHALL acknowledge completion and introduce the next task
2. WHEN a user completes a project milestone THEN the Assistant SHALL celebrate the completed phase
3. WHEN a user completes a project THEN the Assistant SHALL confirm project completion and initiate a reflection conversation
4. WHEN a project is complete THEN the Assistant SHALL ask about the user's experience and learnings
5. WHEN a project is complete THEN the Assistant SHALL offer to start a new project or refine existing ones

### Requirement 12: Minimal Response Handling

**User Story:** As a user who sometimes gives brief responses, I want the Assistant to accept short updates without over-questioning me.

#### Acceptance Criteria

1. WHEN a user replies with minimal text such as "done" or "ok" THEN the Assistant SHALL acknowledge the completion
2. WHEN minimal responses occur occasionally THEN the Assistant SHALL NOT over-question the user
3. WHEN minimal responses form a pattern suggesting issues THEN the Assistant SHALL ask for brief reflection on what worked
