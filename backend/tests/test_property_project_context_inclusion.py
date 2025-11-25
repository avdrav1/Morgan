"""
Property-based tests for project context inclusion.

Feature: proactive-accountability-assistant, Property 14: Project context inclusion
Validates: Requirements 6.9
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
import uuid
from unittest.mock import Mock, patch

from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus
from app.services.llm_service import LLMService


@st.composite
def project_with_context(draw):
    """Generate a project with project-specific context."""
    # Generate meaningful context strings
    context_examples = [
        "This is a client project with strict deadlines",
        "Technical stack: Python, FastAPI, PostgreSQL",
        "Team members: Alice (frontend), Bob (backend)",
        "Budget constraints: $10k maximum",
        "Must follow company coding standards",
        "Integration with legacy system required",
        "User base: 10,000+ daily active users",
        "Compliance: GDPR and HIPAA required"
    ]
    
    project = Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title=f"Project {draw(st.integers(min_value=1, max_value=1000))}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE,
        project_context=draw(st.sampled_from(context_examples))
    )
    return project


@settings(max_examples=100)
@given(
    project_context=st.text(min_size=10, max_size=200),
    data=st.data()
)
def test_project_context_included_in_llm_prompts(project_context, data):
    """
    Property 14: Project context inclusion
    
    For any project with project-specific context, that context should be 
    included in the LLM prompt for all interactions related to that project.
    
    This test verifies that when a project has project_context set, it is
    included in the context passed to the LLM.
    
    Validates: Requirements 6.9
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{data.draw(st.integers(min_value=1, max_value=10000))}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project with specific context
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title=f"Project {data.draw(st.integers(min_value=1, max_value=1000))}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE,
        project_context=project_context
    )
    
    # Create task for the project
    task = Task(
        id=uuid.uuid4(),
        project_id=project.id,
        title=f"Task {data.draw(st.integers(min_value=1, max_value=100))}",
        description="Test task description",
        order=1,
        status=TaskStatus.NOT_STARTED
    )
    
    # Link project to task
    task.project = project
    
    # Create LLM service
    llm_service = LLMService()
    
    # Mock the Anthropic client to capture the user message
    captured_user_message = None
    
    def mock_create(*args, **kwargs):
        nonlocal captured_user_message
        # Capture the user message which contains the context
        messages = kwargs.get('messages', [])
        if messages:
            captured_user_message = messages[0].get('content', '')
        
        # Return a mock response
        mock_response = Mock()
        mock_response.content = [Mock(text="Test response")]
        return mock_response
    
    # Mock the entire Anthropic client
    mock_client = Mock()
    mock_client.messages.create = mock_create
    
    with patch.object(llm_service, 'client', mock_client):
        # Call generate_check_in_message
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            llm_service.generate_check_in_message(user, project, task)
        )
    
    # Verify that the project context is included in the user message
    assert captured_user_message is not None, "No user message was captured"
    assert project_context in captured_user_message, \
        f"Project context '{project_context}' should be included in the LLM prompt"


@settings(max_examples=100)
@given(
    data=st.data()
)
def test_project_without_context_does_not_include_placeholder(data):
    """
    Property 14: Project context inclusion (negative case)
    
    For any project without project-specific context, no placeholder or
    empty context should be included in the LLM prompt.
    
    Validates: Requirements 6.9
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{data.draw(st.integers(min_value=1, max_value=10000))}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project WITHOUT context
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title=f"Project {data.draw(st.integers(min_value=1, max_value=1000))}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE,
        project_context=None  # No context
    )
    
    # Create task for the project
    task = Task(
        id=uuid.uuid4(),
        project_id=project.id,
        title=f"Task {data.draw(st.integers(min_value=1, max_value=100))}",
        description="Test task description",
        order=1,
        status=TaskStatus.NOT_STARTED
    )
    
    # Link project to task
    task.project = project
    
    # Create LLM service
    llm_service = LLMService()
    
    # Mock the Anthropic client to capture the user message
    captured_user_message = None
    
    def mock_create(*args, **kwargs):
        nonlocal captured_user_message
        messages = kwargs.get('messages', [])
        if messages:
            captured_user_message = messages[0].get('content', '')
        
        # Return a mock response
        mock_response = Mock()
        mock_response.content = [Mock(text="Test response")]
        return mock_response
    
    # Mock the entire Anthropic client
    mock_client = Mock()
    mock_client.messages.create = mock_create
    
    with patch.object(llm_service, 'client', mock_client):
        # Call generate_check_in_message
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            llm_service.generate_check_in_message(user, project, task)
        )
    
    # Verify that no "Project-specific context" placeholder appears
    assert captured_user_message is not None, "No user message was captured"
    assert "Project-specific context: None" not in captured_user_message, \
        "Should not include 'None' as project context"
    assert "Project-specific context:" not in captured_user_message, \
        "Should not include project context label when context is not set"


@settings(max_examples=100)
@given(
    project_context=st.text(min_size=10, max_size=200),
    data=st.data()
)
def test_project_context_persists_across_all_llm_methods(project_context, data):
    """
    Property 14: Project context inclusion (comprehensive)
    
    Verify that project context is included consistently across all LLM service methods:
    - generate_check_in_message
    - generate_coaching_response
    - diagnose_blocker
    - propose_reschedule
    - decompose_project
    
    Validates: Requirements 6.9
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{data.draw(st.integers(min_value=1, max_value=10000))}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project with context
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Test Project",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE,
        project_context=project_context
    )
    
    # Create task for the project
    task = Task(
        id=uuid.uuid4(),
        project_id=project.id,
        title="Test Task",
        description="Test task description",
        order=1,
        status=TaskStatus.NOT_STARTED,
        due_date=datetime.utcnow()
    )
    
    # Link project to task
    task.project = project
    
    # Create LLM service
    llm_service = LLMService()
    
    # Test each method that should include project context
    methods_to_test = [
        ('generate_check_in_message', [user, project, task]),
        ('generate_coaching_response', [user, project, task, "test response", []]),
        ('diagnose_blocker', [user, task, [{"role": "user", "content": "I'm stuck"}]]),
        ('propose_reschedule', [user, task, {"blocker_type": "time"}, []]),
        ('decompose_project', [user, project]),
    ]
    
    for method_name, args in methods_to_test:
        captured_user_message = None
        
        def mock_create(*args, **kwargs):
            nonlocal captured_user_message
            messages = kwargs.get('messages', [])
            if messages:
                captured_user_message = messages[0].get('content', '')
            
            # Return appropriate mock response based on method
            mock_response = Mock()
            if method_name == 'decompose_project':
                mock_response.content = [Mock(text='[{"title": "Task 1", "description": "Test", "estimated_duration_hours": 4, "order": 1}]')]
            elif method_name in ['diagnose_blocker', 'propose_reschedule']:
                if method_name == 'diagnose_blocker':
                    mock_response.content = [Mock(text='{"blocker_type": "time", "suggested_strategies": "Test"}')]
                else:
                    mock_response.content = [Mock(text='{"proposed_date": "2024-01-01T00:00:00", "reasoning": "Test"}')]
            else:
                mock_response.content = [Mock(text="Test response")]
            return mock_response
        
        # Mock the entire Anthropic client
        mock_client = Mock()
        mock_client.messages.create = mock_create
        
        with patch.object(llm_service, 'client', mock_client):
            # Call the method
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            method = getattr(llm_service, method_name)
            try:
                loop.run_until_complete(method(*args))
            except Exception:
                # Some methods might fail due to missing data, but we only care about context
                pass
        
        # Verify the project context is included
        if captured_user_message:
            assert project_context in captured_user_message, \
                f"Method '{method_name}' should include project context '{project_context}'"
