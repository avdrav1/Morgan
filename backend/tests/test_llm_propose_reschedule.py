"""
Test for LLMService.propose_reschedule method.
"""
import pytest
from datetime import datetime, timedelta
from app.services.llm_service import LLMService
from app.models import User, Project, Task, TaskStatus


@pytest.mark.asyncio
async def test_propose_reschedule_returns_valid_structure(db_session):
    """Test that propose_reschedule returns a valid response structure."""
    
    # Create test user (let SQLAlchemy generate the ID)
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="America/New_York"
    )
    db_session.add(user)
    db_session.flush()  # Flush to get ID
    
    # Create test project
    project = Project(
        user_id=user.id,
        title="Test Project",
        description="A test project",
        goal="Complete the test"
    )
    db_session.add(project)
    db_session.flush()  # Flush to get ID
    
    # Create test task with due date
    due_date = datetime.utcnow() + timedelta(days=2)
    task = Task(
        project_id=project.id,
        title="Test Task",
        description="A test task",
        order=1,
        status=TaskStatus.BLOCKED,
        due_date=due_date,
        estimated_duration_hours=4,
        blocker_type="time",
        blocker_description="Not enough time to complete"
    )
    db_session.add(task)
    db_session.commit()
    
    # Refresh to load relationships
    db_session.refresh(task)
    
    # Prepare test data
    blocker_info = {
        "blocker_type": "time",
        "suggested_strategies": "Break task into smaller chunks, allocate specific time blocks"
    }
    
    conversation_history = [
        {"role": "assistant", "content": "How is the task going?"},
        {"role": "user", "content": "I'm behind schedule, I underestimated the time needed"},
        {"role": "assistant", "content": "What's preventing you from completing it?"},
        {"role": "user", "content": "I have other urgent work that came up"}
    ]
    
    # Call the method
    llm_service = LLMService()
    result = await llm_service.propose_reschedule(
        user=user,
        task=task,
        blocker_info=blocker_info,
        conversation_history=conversation_history
    )
    
    # Verify structure
    assert "proposed_date" in result
    assert "reasoning" in result
    
    # Verify proposed_date is a valid ISO format string
    proposed_date = datetime.fromisoformat(result["proposed_date"].replace("Z", "+00:00"))
    assert isinstance(proposed_date, datetime)
    
    # Verify reasoning is a non-empty string
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0
    
    # Verify proposed date is in the future
    assert proposed_date > datetime.utcnow()
    
    print(f"✓ propose_reschedule returned valid structure")
    print(f"  Proposed date: {result['proposed_date']}")
    print(f"  Reasoning: {result['reasoning']}")
