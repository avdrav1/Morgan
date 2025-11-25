# Design Document

## Overview

This design document describes the architecture and implementation approach for managing project plans through Discord Direct Messages. The system enables users to view, query, and modify their project plans through natural conversation with Morgan, the accountability assistant bot. The design leverages the existing LLM service for natural language understanding and generation, while adding new conversation handlers and database operations for project plan management.

## Architecture

The project plan management system consists of several key components:

1. **Discord Bot Handler**: Receives messages from users and routes them to the appropriate handler
2. **Project Plan Conversation Manager**: Manages the conversational flow for project plan interactions
3. **Intent Classifier**: Uses the LLM service to understand user intent from natural language
4. **Project Plan Service**: Business logic for retrieving, displaying, and modifying project plans
5. **Milestone Generator**: Creates initial milestones based on project goals and deadlines
6. **Timeline Adjuster**: Recalculates milestone dates when deadlines change
7. **Response Formatter**: Formats project plan data for Discord display

## Components and Interfaces

### Discord Bot Handler

The existing Discord bot will be extended to handle post-onboarding conversations:

```python
class ProjectPlanHandler:
    """Handles Discord messages related to project plan management."""
    
    async def handle_message(
        self,
        user_id: str,
        discord_id: str,
        message: str
    ) -> str:
        """
        Process a message about project plans.
        
        Args:
            user_id: The user's UUID
            discord_id: The user's Discord ID
            message: The message content
            
        Returns:
            The response message to send back
        """
        pass
```

### Intent Classifier

Uses the LLM service to classify user intent:

```python
class IntentClassifier:
    """Classifies user intent from natural language messages."""
    
    async def classify_intent(
        self,
        message: str,
        conversation_history: List[Dict],
        project_context: Dict
    ) -> Intent:
        """
        Classify the user's intent from their message.
        
        Args:
            message: The user's message
            conversation_history: Recent conversation context
            project_context: Current project information
            
        Returns:
            Intent object with type and extracted parameters
        """
        pass

class Intent:
    """Represents a classified user intent."""
    type: IntentType  # VIEW_PLAN, EDIT_DEADLINE, ADD_MILESTONE, etc.
    parameters: Dict[str, Any]  # Extracted entities (dates, milestone names, etc.)
    confidence: float  # Confidence score 0-1
```

### Project Plan Service

Manages project plan data and operations:

```python
class ProjectPlanService:
    """Service for project plan operations."""
    
    async def get_project_plan(
        self,
        user_id: str,
        project_id: Optional[str] = None
    ) -> ProjectPlan:
        """Get the project plan for a user."""
        pass
    
    async def generate_initial_milestones(
        self,
        project: Project
    ) -> List[Milestone]:
        """Generate initial milestones for a project."""
        pass
    
    async def update_deadline(
        self,
        project_id: str,
        new_deadline: datetime,
        adjust_milestones: bool = True
    ) -> ProjectPlan:
        """Update project deadline and optionally adjust milestones."""
        pass
    
    async def add_milestone(
        self,
        project_id: str,
        milestone: MilestoneCreate
    ) -> Milestone:
        """Add a new milestone to the project."""
        pass
    
    async def update_milestone(
        self,
        milestone_id: str,
        updates: MilestoneUpdate
    ) -> Milestone:
        """Update an existing milestone."""
        pass
    
    async def mark_milestone_complete(
        self,
        milestone_id: str
    ) -> Milestone:
        """Mark a milestone as complete."""
        pass
```

### Response Formatter

Formats project plan data for Discord:

```python
class DiscordProjectPlanFormatter:
    """Formats project plan data for Discord display."""
    
    def format_project_plan(
        self,
        project: Project,
        milestones: List[Milestone],
        include_completed: bool = False
    ) -> List[str]:
        """
        Format a project plan for Discord display.
        
        Returns a list of message strings (may be multiple if content is long).
        """
        pass
    
    def format_milestone(
        self,
        milestone: Milestone,
        include_status_emoji: bool = True
    ) -> str:
        """Format a single milestone for display."""
        pass
    
    def format_timeline_summary(
        self,
        project: Project,
        milestones: List[Milestone]
    ) -> str:
        """Format a summary of the project timeline."""
        pass
```

## Data Models

### Milestone Model

Extends the existing database schema:

```python
class Milestone(Base):
    """Database model for project milestones."""
    __tablename__ = "milestones"
    
    id: UUID
    project_id: UUID  # Foreign key to projects table
    title: str
    description: Optional[str]
    target_date: datetime
    completed_at: Optional[datetime]
    status: MilestoneStatus  # PENDING, IN_PROGRESS, COMPLETED
    order: int  # Order in the project timeline
    created_at: datetime
    updated_at: datetime
```

### Conversation Context Model

Tracks conversation state for project plan discussions:

```python
class ProjectPlanConversation(Base):
    """Tracks conversation state for project plan management."""
    __tablename__ = "project_plan_conversations"
    
    id: UUID
    user_id: UUID
    project_id: UUID
    last_intent: str
    pending_confirmation: Optional[Dict]  # JSON field for pending changes
    conversation_history: List[Dict]  # Recent messages for context
    created_at: datetime
    updated_at: datetime
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Project plan retrieval completeness

*For any* user with at least one project, requesting to view their project plan should return a response containing the project name, goal, deadline, and all associated milestones.

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Milestone chronological ordering

*For any* project plan display, milestones should be ordered chronologically by target date, with earlier dates appearing before later dates.

**Validates: Requirements 1.3**

### Property 3: Intent classification consistency

*For any* user message expressing a clear intent (view, edit, add, etc.), the intent classifier should return the same intent type when given the same message and context.

**Validates: Requirements 6.1, 6.2**

### Property 4: Deadline update propagation

*For any* project deadline change, if the user confirms milestone adjustment, then all milestone dates should be recalculated to fit within the new timeline.

**Validates: Requirements 4.1, 4.2, 4.5**

### Property 5: Milestone completion state persistence

*For any* milestone marked as complete, subsequent retrievals of that milestone should show it as completed with a completion timestamp.

**Validates: Requirements 5.2**

### Property 6: Multi-project context isolation

*For any* user with multiple projects, operations on one project should not affect the data or state of other projects.

**Validates: Requirements 7.1, 7.2, 7.3**

### Property 7: Discord message length compliance

*For any* formatted project plan output, each individual message should not exceed Discord's 2000 character limit.

**Validates: Requirements 8.2, 8.5**

### Property 8: Relative date accuracy

*For any* milestone displayed with a relative date (e.g., "in 3 days"), the relative date should accurately reflect the difference between the current date and the milestone's target date.

**Validates: Requirements 8.3**

### Property 9: Change confirmation requirement

*For any* destructive operation (delete milestone, shorten deadline significantly), the system should require explicit user confirmation before applying the change.

**Validates: Requirements 3.4, 4.3**

### Property 10: Conversation history preservation

*For any* conversation about a project plan, the conversation history should be maintained and available for context in subsequent messages within the same session.

**Validates: Requirements 2.2, 6.1**

## Error Handling

### User Errors

- **No projects found**: Inform user they need to complete onboarding first
- **Ambiguous project reference**: Ask user to clarify which project they mean
- **Invalid date format**: Provide examples and ask user to try again
- **Milestone not found**: List available milestones and ask user to specify
- **Conflicting changes**: Explain the conflict and ask how to resolve

### System Errors

- **Database connection failure**: Apologize and ask user to try again in a moment
- **LLM service unavailable**: Fall back to keyword-based intent detection
- **Project data corruption**: Log error, alert ops team, inform user to contact support
- **Discord API rate limit**: Queue the message and send when rate limit resets
- **Milestone generation failure**: Offer to let user create milestones manually

## Testing Strategy

### Unit Tests

- Test intent classification with various phrasings
- Test milestone date calculations
- Test Discord message formatting and splitting
- Test project plan retrieval with different data states
- Test timeline adjustment algorithms
- Test multi-project context switching

### Property-Based Tests

We will use Hypothesis (Python's property-based testing library) to verify the correctness properties defined above. Each property will be implemented as a separate test that generates random valid inputs and verifies the property holds.

Configuration:
- Minimum 100 iterations per property test
- Each test will be tagged with the format: `# Feature: discord-project-plan-management, Property N: <property text>`

### Integration Tests

- Test end-to-end conversation flows (view → edit → confirm)
- Test Discord bot message handling with real Discord API (staging)
- Test LLM service integration with various prompts
- Test database operations with concurrent users
- Test error recovery scenarios

## Implementation Notes

### LLM Prompt Design

The intent classifier will use carefully crafted prompts to ensure accurate intent detection:

```
You are analyzing a message from a user about their project plan. 
The user's project is: {project_name}
Goal: {project_goal}
Deadline: {deadline}

Recent conversation:
{conversation_history}

User message: {message}

Classify the user's intent into one of these categories:
- VIEW_PLAN: User wants to see their project plan
- EDIT_DEADLINE: User wants to change the project deadline
- ADD_MILESTONE: User wants to add a new milestone
- EDIT_MILESTONE: User wants to modify an existing milestone
- DELETE_MILESTONE: User wants to remove a milestone
- MARK_COMPLETE: User wants to mark a milestone as complete
- ASK_QUESTION: User has a question about their project
- UNCLEAR: Intent cannot be determined

Extract any relevant parameters (dates, milestone names, etc.)
```

### Milestone Generation Algorithm

When generating initial milestones for a project:

1. Calculate the number of weeks until deadline
2. Create 3-5 milestones depending on project duration
3. Distribute milestones evenly across the timeline
4. Use LLM to generate milestone titles based on project goal
5. Set first milestone 1-2 weeks out to create immediate action

### Timeline Adjustment Strategy

When deadline changes:

1. Calculate the ratio of new timeline to old timeline
2. Adjust each incomplete milestone proportionally
3. Ensure minimum spacing between milestones (3 days)
4. Round dates to end of day for clarity
5. Present changes to user for confirmation

### Discord Formatting Standards

- Use **bold** for project names and milestone titles
- Use `code blocks` for dates
- Use emojis: ⏳ (pending), 🔄 (in progress), ✅ (complete)
- Use numbered lists for milestones
- Include blank lines between sections for readability
- Split messages at natural boundaries (between milestones)

## Security Considerations

- Validate user owns the project before allowing modifications
- Sanitize user input before passing to LLM
- Rate limit requests to prevent abuse
- Log all modifications for audit trail
- Redact PII from logs and error messages

## Performance Considerations

- Cache project plans for 5 minutes to reduce database queries
- Use database indexes on user_id and project_id
- Batch milestone updates when adjusting timeline
- Limit conversation history to last 10 messages
- Use async operations for all I/O

## Deployment Strategy

1. Add milestones table via database migration
2. Deploy new services without enabling feature
3. Test with internal users
4. Enable feature for beta users
5. Monitor metrics and error rates
6. Gradual rollout to all users
