# Design Document: Proactive Accountability Assistant

## Overview

The Proactive Accountability Assistant is an LLM-powered system that provides personalized accountability for users working on projects. The system operates through a conversational interface, breaking down ambiguous goals into structured tasks, proactively checking in on progress, diagnosing blockers, and providing adaptive coaching.

The architecture builds on an existing FastAPI backend with PostgreSQL database, Celery task queue, and Anthropic Claude integration. The system extends this foundation with enhanced scheduling logic, conversational state management, and multi-platform messaging support.

### Key Design Principles

1. **Proactive, Not Reactive**: The system initiates conversations based on schedules and progress expectations
2. **Conversational Rescheduling**: No "snooze" buttons—all timeline adjustments happen through dialogue
3. **Boundary Respect**: Strict adherence to quiet hours and user availability
4. **Adaptive Personality**: User-configurable tone and system prompts for different contexts
5. **Pattern Recognition**: Learn from user behavior to improve scheduling and coaching

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Messaging Layer                          │
│  (Discord Bot, Web Interface, Future: SMS, Slack)           │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                   FastAPI Backend                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   API        │  │  LLM Service │  │  Scheduler   │     │
│  │   Routes     │  │  (Claude)    │  │  Service     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│              Data Layer (PostgreSQL)                         │
│  Users, Projects, Tasks, CheckIns, AvailabilityWindows     │
└─────────────────────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│           Task Queue (Celery + Redis)                        │
│  Scheduled check-ins, message delivery, pattern analysis    │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**API Layer**
- Handle HTTP requests for project/task CRUD operations
- Manage user authentication and authorization
- Process incoming messages from messaging platforms
- Coordinate between LLM service and data layer

**LLM Service**
- Generate check-in messages based on context and tone
- Provide coaching responses to user updates
- Decompose projects into actionable tasks
- Diagnose blockers from conversation patterns
- Maintain conversation context across interactions

**Scheduler Service**
- Calculate optimal check-in times based on task deadlines and user availability
- Respect quiet hours and time zones
- Adapt check-in frequency based on user responsiveness
- Handle rescheduling through conversational flow
- Track ghosting patterns and trigger appropriate responses

**Messaging Layer**
- Abstract platform-specific message delivery (Discord, web, SMS, Slack)
- Handle message formatting for different platforms
- Manage delivery status and retry logic with exponential backoff
- Route incoming messages to appropriate handlers

**Data Layer**
- Persist user profiles, projects, tasks, and check-ins
- Store conversation history and context
- Track rescheduling patterns and blocker types
- Maintain availability windows and quiet hours

## Components and Interfaces

### 1. Enhanced LLM Service

The existing `LLMService` will be extended with additional capabilities:

```python
class LLMService:
    async def generate_check_in_message(
        user: User,
        project: Project,
        task: Task,
        check_in_type: str
    ) -> str
    
    async def generate_coaching_response(
        user: User,
        project: Project,
        task: Task,
        user_response: str,
        conversation_history: List[Dict]
    ) -> str
    
    async def decompose_project(
        user: User,
        project: Project
    ) -> List[Dict[str, Any]]
    
    async def diagnose_blocker(
        user: User,
        task: Task,
        conversation_history: List[Dict]
    ) -> Dict[str, str]  # Returns blocker_type and suggested_strategies
    
    async def propose_reschedule(
        user: User,
        task: Task,
        blocker_info: Dict,
        conversation_history: List[Dict]
    ) -> Dict[str, Any]  # Returns proposed new deadline and reasoning
```

### 2. Scheduler Service

New service for intelligent check-in scheduling:

```python
class SchedulerService:
    def calculate_check_in_time(
        task: Task,
        user: User,
        availability_windows: List[AvailabilityWindow]
    ) -> datetime
    
    def is_within_quiet_hours(
        user: User,
        check_time: datetime
    ) -> bool
    
    def should_adapt_frequency(
        user: User,
        project: Project,
        recent_check_ins: List[CheckIn]
    ) -> Tuple[bool, str]  # Returns (should_adapt, reason)
    
    def calculate_ghosting_response(
        user: User,
        project: Project,
        missed_count: int
    ) -> Dict[str, Any]  # Returns response_type and message_template
    
    def find_next_available_slot(
        user: User,
        preferred_time: datetime,
        availability_windows: List[AvailabilityWindow]
    ) -> datetime
```

### 3. Conversation Manager

New component for managing conversational state:

```python
class ConversationManager:
    def get_conversation_context(
        check_in: CheckIn,
        max_history: int = 10
    ) -> List[Dict[str, str]]
    
    def store_conversation_turn(
        check_in: CheckIn,
        role: str,
        content: str
    ) -> None
    
    def detect_blocker_pattern(
        task: Task,
        conversation_history: List[Dict]
    ) -> Optional[str]  # Returns blocker_type if detected
    
    def extract_reschedule_intent(
        user_response: str
    ) -> bool
```

### 4. Messaging Adapter Interface

Abstract interface for platform-specific messaging:

```python
class MessagingAdapter(ABC):
    @abstractmethod
    async def send_message(
        user_identifier: str,
        message: str,
        metadata: Dict[str, Any]
    ) -> bool
    
    @abstractmethod
    async def handle_incoming_message(
        user_identifier: str,
        message: str,
        metadata: Dict[str, Any]
    ) -> None

class DiscordAdapter(MessagingAdapter):
    # Discord-specific implementation
    
class WebAdapter(MessagingAdapter):
    # Web interface implementation
```

### 5. API Endpoints

New and enhanced endpoints:

```
POST   /api/projects                    # Create project with initial description
POST   /api/projects/{id}/decompose     # Trigger LLM task decomposition
PUT    /api/projects/{id}/timeline      # Approve/modify proposed timeline
POST   /api/projects/{id}/pause         # Pause project
POST   /api/projects/{id}/archive       # Archive project

GET    /api/tasks/{id}/check-ins        # Get check-in history for task
POST   /api/check-ins/{id}/respond      # User responds to check-in
POST   /api/check-ins/{id}/reschedule   # Initiate rescheduling conversation

GET    /api/users/me/availability       # Get availability windows
PUT    /api/users/me/availability       # Update availability windows
PUT    /api/users/me/quiet-hours        # Update quiet hours
PUT    /api/users/me/tone               # Update preferred tone
PUT    /api/users/me/system-prompt      # Update custom system prompt

POST   /api/messages/incoming           # Webhook for incoming messages from platforms
```

## Data Models

### Enhanced User Model

```python
class User(Base):
    # Existing fields...
    
    # Enhanced preferences
    preferred_tone: str  # coach, manager, buddy, drill_sergeant
    custom_system_prompt: Optional[str]
    timezone: str
    quiet_hours_start: Optional[str]  # "HH:MM" format
    quiet_hours_end: Optional[str]
    
    # Engagement tracking
    total_check_ins_sent: int = 0
    total_check_ins_responded: int = 0
    consecutive_missed_check_ins: int = 0
    last_active_at: Optional[datetime]
    
    # Relationships
    projects: List[Project]
    availability_windows: List[AvailabilityWindow]
```

### Enhanced Project Model

```python
class Project(Base):
    # Existing fields...
    
    # Project-specific settings
    project_tone: Optional[str]  # Override user's default
    project_context: Optional[str]  # Additional context for LLM
    
    # Status tracking
    status: ProjectStatus  # active, paused, completed, archived
    ghosting_stage: int = 0  # 0=active, 1=2 missed, 2=4 missed, 3=7 missed
    
    # Relationships
    tasks: List[Task]
    check_ins: List[CheckIn]
```

### Enhanced Task Model

```python
class Task(Base):
    # Existing fields...
    
    # Timeline tracking
    due_date: Optional[datetime]
    original_due_date: Optional[datetime]  # Track first deadline
    reschedule_count: int = 0
    
    # Blocker tracking
    blocker_type: Optional[str]  # time, clarity, emotional, external, scope
    blocker_description: Optional[str]
    blocker_diagnosed_at: Optional[datetime]
    
    # Status
    status: TaskStatus  # not_started, in_progress, blocked, completed, cancelled
    
    # Relationships
    check_ins: List[CheckIn]
```

### Enhanced CheckIn Model

```python
class CheckIn(Base):
    # Existing fields...
    
    # Conversation tracking
    conversation_context: JSONB  # Stores conversation history
    blocker_detected: bool = False
    reschedule_initiated: bool = False
    
    # Response tracking
    response_time_minutes: Optional[int]  # Time to respond
    sentiment: Optional[str]  # positive, neutral, negative, blocked
```

### AvailabilityWindow Model

```python
class AvailabilityWindow(Base):
    user_id: UUID
    day_of_week: int  # 0=Monday, 6=Sunday
    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"
```

### New: ReschedulingHistory Model

```python
class ReschedulingHistory(Base):
    id: UUID
    task_id: UUID
    old_due_date: datetime
    new_due_date: datetime
    reason: str  # From conversation
    blocker_type: Optional[str]
    initiated_by: str  # user or assistant
    created_at: datetime
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Project input acceptance

*For any* free-form text input describing a project, the system should accept the input and respond with a clarification request rather than an error.
**Validates: Requirements 1.1**

### Property 2: Multi-project storage with single focus

*For any* set of projects belonging to a user, all projects should be persisted in the database, and exactly one project should be marked as the active focus at any time.
**Validates: Requirements 1.4**

### Property 3: Task count bounds

*For any* project decomposition, the number of generated tasks should be between 5 and 20 inclusive.
**Validates: Requirements 2.1**

### Property 4: Timeline modification acceptance

*For any* proposed timeline, when a user requests modifications, the system should update the timeline to reflect the requested changes.
**Validates: Requirements 2.5**

### Property 5: Availability-aware scheduling

*For any* task with a deadline and user with defined availability windows, all scheduled check-ins should fall within the user's availability windows.
**Validates: Requirements 2.6, 3.6, 8.4**

### Property 6: Pre-deadline check-ins

*For any* task with a due date, check-ins scheduled for that task should be scheduled before the due date, not after.
**Validates: Requirements 3.1, 3.3**

### Property 7: Quiet hours enforcement

*For any* user with defined quiet hours, no messages should be sent during those time periods.
**Validates: Requirements 3.2, 8.3**

### Property 8: Adaptive frequency for low responsiveness

*For any* user with a response rate below 30% over the last 10 check-ins, the check-in frequency should be reduced compared to the baseline.
**Validates: Requirements 3.4**

### Property 9: Adaptive frequency for high responsiveness

*For any* user with a response rate above 70% over the last 10 check-ins, the check-in frequency should be maintained or increased compared to the baseline.
**Validates: Requirements 3.5**

### Property 10: Blocker type validity

*For any* diagnosed blocker, the blocker type should be one of: time, clarity, emotional, external, or scope.
**Validates: Requirements 4.3**

### Property 11: No automatic timeline adjustments

*For any* task with a due date, the due date should never change without explicit user confirmation through conversation.
**Validates: Requirements 5.4**

### Property 12: Rescheduling history tracking

*For any* task that is rescheduled, a rescheduling history record should be created with the old date, new date, and reason.
**Validates: Requirements 5.5**

### Property 13: Project-specific tone persistence

*For any* project with a project-specific tone setting, that tone should be used for all check-ins related to that project, regardless of the user's default tone.
**Validates: Requirements 6.8**

### Property 14: Project context inclusion

*For any* project with project-specific context, that context should be included in the LLM prompt for all interactions related to that project.
**Validates: Requirements 6.9**

### Property 15: Platform-appropriate formatting

*For any* message sent to a specific platform, the message format should conform to that platform's requirements (e.g., Discord markdown vs plain text).
**Validates: Requirements 7.3**

### Property 16: Exponential backoff on retry

*For any* failed message delivery, retry attempts should occur with exponentially increasing delays (e.g., 1s, 2s, 4s, 8s).
**Validates: Requirements 7.4**

### Property 17: Timezone-aware scheduling

*For any* user with a specified timezone, all scheduled check-in times should be calculated in that timezone.
**Validates: Requirements 8.5**

### Property 18: Data deletion completeness

*For any* user who requests data deletion, all associated records (projects, tasks, check-ins, availability windows) should be deleted within 30 days.
**Validates: Requirements 10.1**

### Property 19: Data export completeness

*For any* user who requests data export, the exported data should include all projects, tasks, timelines, and conversation history associated with that user.
**Validates: Requirements 10.2**

### Property 20: Pause stops proactive messages

*For any* user who pauses messaging, no proactive check-ins should be sent until messaging is resumed.
**Validates: Requirements 10.3**

### Property 21: Data collection scope

*For any* user interaction, the system should only store data in the categories: project goals, tasks, timelines, user preferences, and conversation history.
**Validates: Requirements 10.4**

### Property 22: Minimal response acceptance

*For any* check-in response consisting of 10 or fewer characters, the system should accept and process the response without error.
**Validates: Requirements 12.1**

## Error Handling

### Quiet Hours Violations

**Scenario**: A check-in is scheduled during quiet hours due to calculation error.

**Handling**:
1. Scheduler detects quiet hours conflict before sending
2. Reschedule to next available slot after quiet hours end
3. Log the conflict for debugging
4. Never send the message during quiet hours

### LLM Service Failures

**Scenario**: Anthropic API is unavailable or returns an error.

**Handling**:
1. Retry with exponential backoff (3 attempts)
2. If all retries fail, use fallback template messages
3. Log the failure for monitoring
4. Queue for retry when service recovers
5. Notify user of delay if check-in is time-critical

### Message Delivery Failures

**Scenario**: Discord bot cannot deliver message (user blocked bot, network error).

**Handling**:
1. Retry with exponential backoff (5 attempts over 24 hours)
2. Mark check-in as "delivery_failed" after final attempt
3. Fall back to web interface notification
4. Log failure reason for debugging
5. Don't count as "missed" check-in if delivery failed

### Timezone Conversion Errors

**Scenario**: User's timezone setting is invalid or ambiguous.

**Handling**:
1. Default to UTC if timezone is invalid
2. Prompt user to update timezone setting
3. Log the error for investigation
4. Continue scheduling with UTC until corrected

### Database Connection Failures

**Scenario**: PostgreSQL connection is lost during operation.

**Handling**:
1. Celery task automatically retries with backoff
2. Use connection pooling with health checks
3. Fail gracefully and log error
4. Alert monitoring system if failures persist

### User Ghosting Edge Cases

**Scenario**: User misses check-ins but then suddenly responds.

**Handling**:
1. Reset consecutive missed count to 0
2. Resume normal check-in frequency
3. Acknowledge their return positively
4. Don't reference the gap unless user brings it up

### Concurrent Rescheduling

**Scenario**: User tries to reschedule same task multiple times simultaneously.

**Handling**:
1. Use database-level locking on task updates
2. Process reschedule requests sequentially
3. Return current state after each update
4. Prevent race conditions with optimistic locking

## Testing Strategy

### Unit Testing

Unit tests will verify specific functionality and edge cases:

**Core Functionality Tests**:
- Project CRUD operations
- Task CRUD operations
- Check-in creation and status transitions
- Availability window management
- Quiet hours calculation
- Timezone conversion

**Edge Case Tests**:
- Quiet hours spanning midnight (e.g., 22:00 to 08:00)
- Availability windows with no valid slots
- Tasks with past due dates
- Empty or whitespace-only user inputs
- Invalid timezone strings
- Concurrent updates to same task

**Integration Tests**:
- End-to-end project creation flow
- Check-in scheduling and delivery pipeline
- Rescheduling conversation flow
- LLM service integration with mocked responses
- Message delivery across platforms

### Property-Based Testing

Property-based tests will verify universal properties across many inputs using the **Hypothesis** library for Python.

**Configuration**: Each property test should run a minimum of 100 iterations to ensure thorough coverage of the input space.

**Test Tagging**: Each property-based test must include a comment explicitly referencing the correctness property from this design document using the format:
```python
# Feature: proactive-accountability-assistant, Property 7: Quiet hours enforcement
```

**Property Test Coverage**:

1. **Property 1: Project input acceptance** - Generate random text strings and verify system accepts them
2. **Property 2: Multi-project storage** - Generate random project sets and verify storage and focus constraints
3. **Property 3: Task count bounds** - Generate random projects and verify task count is 5-20
4. **Property 5: Availability-aware scheduling** - Generate random availability windows and verify check-ins fall within them
5. **Property 6: Pre-deadline check-ins** - Generate random task deadlines and verify check-ins are before deadlines
6. **Property 7: Quiet hours enforcement** - Generate random quiet hours and verify no messages during those times
7. **Property 8-9: Adaptive frequency** - Generate random response patterns and verify frequency adjustments
8. **Property 10: Blocker type validity** - Generate random blocker scenarios and verify type is valid
9. **Property 11: No automatic adjustments** - Generate random timeline changes and verify confirmation required
10. **Property 12: Rescheduling history** - Generate random reschedules and verify history records created
11. **Property 13-14: Project-specific settings** - Generate random project settings and verify they're used correctly
12. **Property 15: Platform formatting** - Generate random messages and verify platform-specific formatting
13. **Property 16: Exponential backoff** - Generate random failures and verify retry delays increase exponentially
14. **Property 17: Timezone-aware scheduling** - Generate random timezones and verify correct time calculations
15. **Property 18-19: Data operations** - Generate random user data and verify deletion/export completeness
16. **Property 20: Pause behavior** - Generate random pause states and verify no messages sent when paused
17. **Property 21: Data collection scope** - Generate random interactions and verify only specified data stored
18. **Property 22: Minimal response acceptance** - Generate random short responses and verify acceptance

**Smart Generators**:
- Availability windows that may or may not overlap
- Quiet hours that may span midnight
- Timezones from the full IANA database
- Project descriptions with various lengths and formats
- Response patterns with different rates and timing
- Task deadlines in past, present, and future

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Goal**: Establish foundation for proactive scheduling and messaging.

**Deliverables**:
- Enhanced data models with migrations
- Scheduler service with availability-aware logic
- Conversation manager for context tracking
- Basic messaging adapter interface

### Phase 2: LLM Integration (Week 3-4)

**Goal**: Implement intelligent conversation and coaching.

**Deliverables**:
- Enhanced LLM service with all conversation types
- Blocker diagnosis logic
- Tone preset system with custom prompts
- Project decomposition with timeline generation

### Phase 3: Proactive Check-Ins (Week 5-6)

**Goal**: Implement automated check-in system.

**Deliverables**:
- Celery tasks for check-in scheduling
- Quiet hours enforcement
- Adaptive frequency logic
- Ghosting detection and response

### Phase 4: Conversational Rescheduling (Week 7-8)

**Goal**: Implement rescheduling through dialogue.

**Deliverables**:
- Rescheduling conversation flow
- History tracking
- Pattern analysis for future planning
- Timeline adjustment with confirmation

### Phase 5: Platform Integration (Week 9-10)

**Goal**: Complete Discord and web interfaces.

**Deliverables**:
- Discord bot with message handling
- Web interface for onboarding and timeline review
- Message delivery with retry logic
- Platform-specific formatting

### Phase 6: Testing & Refinement (Week 11-12)

**Goal**: Comprehensive testing and bug fixes.

**Deliverables**:
- Complete unit test suite
- Complete property-based test suite
- Performance optimization
- Documentation

## Security Considerations

### Authentication & Authorization

- JWT-based authentication for API access
- User can only access their own projects and data
- Discord user ID verification before linking accounts
- Rate limiting on API endpoints to prevent abuse

### Data Privacy

- Conversation history stored encrypted at rest
- PII (email, Discord ID) stored separately from conversation data
- Audit log for data access and modifications
- Compliance with GDPR data deletion requirements

### LLM Safety

- System prompts include safety guidelines
- User inputs sanitized before sending to LLM
- LLM responses filtered for inappropriate content
- Clear disclaimers that system is not therapy
- Escalation to human resources for distress signals

### Platform Security

- Discord bot token stored in environment variables
- Webhook signatures verified for incoming messages
- SQL injection prevention through ORM
- CORS configured for web interface

## Performance Considerations

### Database Optimization

- Indexes on frequently queried fields (user_id, project_id, due_date, scheduled_for)
- Connection pooling for concurrent requests
- Query optimization for check-in scheduling
- Archival strategy for old completed projects

### LLM API Optimization

- Caching for repeated similar queries
- Batch processing where possible
- Token usage monitoring and optimization
- Fallback to templates for simple messages

### Celery Task Optimization

- Task prioritization (urgent check-ins first)
- Batch processing of scheduled check-ins
- Efficient polling intervals
- Dead letter queue for failed tasks

### Scalability

- Horizontal scaling of API servers
- Redis for distributed caching
- Database read replicas for reporting
- Message queue for async processing

## Monitoring & Observability

### Key Metrics

- Check-in response rate by user and project
- Average response time to check-ins
- LLM API latency and error rate
- Message delivery success rate
- Task completion rate vs. original timeline
- Rescheduling frequency
- Ghosting recovery rate

### Logging

- Structured logging with correlation IDs
- LLM request/response logging (with PII redaction)
- Scheduler decision logging
- Error tracking with stack traces
- Audit trail for data modifications

### Alerts

- LLM API failures exceeding threshold
- Message delivery failures exceeding threshold
- Database connection issues
- Celery queue backlog
- Unusual user behavior patterns

## Future Enhancements

### Phase 2+ Features

1. **Multi-Project Management**: Support multiple active projects simultaneously
2. **Collaborative Projects**: Shared accountability with other users
3. **Advanced Analytics**: Insights dashboard for completion patterns
4. **SMS Support**: Text message delivery for check-ins
5. **Slack Integration**: Workspace-based accountability
6. **Voice Interface**: Voice-based check-ins and responses
7. **RAG for Long-Term Memory**: Better context for long-running projects
8. **Predictive Scheduling**: ML-based optimal check-in timing
9. **Habit Tracking**: Recurring tasks and habit formation
10. **Integration API**: Connect with external tools (Notion, Todoist, etc.)
