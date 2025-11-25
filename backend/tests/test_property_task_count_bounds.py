"""
Property-based tests for task count bounds.

Feature: proactive-accountability-assistant, Property 3: Task count bounds
Validates: Requirements 2.1
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import uuid
from unittest.mock import Mock, patch
import json

from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.services.llm_service import LLMService


@st.composite
def valid_task_list(draw):
    """Generate a valid task list with 5-20 tasks."""
    num_tasks = draw(st.integers(min_value=5, max_value=20))
    tasks = []
    for i in range(num_tasks):
        tasks.append({
            "title": f"Task {i+1}",
            "description": f"Description for task {i+1}",
            "estimated_duration_hours": draw(st.integers(min_value=1, max_value=40)),
            "order": i + 1
        })
    return tasks


@st.composite
def invalid_task_list_too_few(draw):
    """Generate an invalid task list with fewer than 5 tasks."""
    num_tasks = draw(st.integers(min_value=0, max_value=4))
    tasks = []
    for i in range(num_tasks):
        tasks.append({
            "title": f"Task {i+1}",
            "description": f"Description for task {i+1}",
            "estimated_duration_hours": draw(st.integers(min_value=1, max_value=40)),
            "order": i + 1
        })
    return tasks


@st.composite
def invalid_task_list_too_many(draw):
    """Generate an invalid task list with more than 20 tasks."""
    num_tasks = draw(st.integers(min_value=21, max_value=50))
    tasks = []
    for i in range(num_tasks):
        tasks.append({
            "title": f"Task {i+1}",
            "description": f"Description for task {i+1}",
            "estimated_duration_hours": draw(st.integers(min_value=1, max_value=40)),
            "order": i + 1
        })
    return tasks


@settings(max_examples=100)
@given(
    task_list=valid_task_list(),
    data=st.data()
)
def test_task_count_within_bounds(task_list, data):
    """
    Property 3: Task count bounds
    
    For any project decomposition, the number of generated tasks should be 
    between 5 and 20 inclusive.
    
    This test verifies that when decompose_project returns successfully,
    it always returns between 5 and 20 tasks.
    
    Validates: Requirements 2.1
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{data.draw(st.integers(min_value=1, max_value=10000))}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title=f"Project {data.draw(st.integers(min_value=1, max_value=1000))}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Create LLM service
    llm_service = LLMService()
    
    # Mock the Anthropic client to return our task list
    def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps(task_list))]
        return mock_response
    
    # Mock the entire Anthropic client
    mock_client = Mock()
    mock_client.messages.create = mock_create
    
    with patch.object(llm_service, 'client', mock_client):
        # Call decompose_project
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            llm_service.decompose_project(user, project)
        )
    
    # Verify task count is within bounds
    assert 5 <= len(result) <= 20, \
        f"Task count {len(result)} is not within bounds [5, 20]"


@settings(max_examples=100)
@given(
    task_list=invalid_task_list_too_few(),
    data=st.data()
)
def test_task_count_too_few_raises_error(task_list, data):
    """
    Property 3: Task count bounds (validation - too few)
    
    For any project decomposition that returns fewer than 5 tasks,
    the system should raise a ValueError.
    
    Validates: Requirements 2.1
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{data.draw(st.integers(min_value=1, max_value=10000))}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title=f"Project {data.draw(st.integers(min_value=1, max_value=1000))}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Create LLM service
    llm_service = LLMService()
    
    # Mock the Anthropic client to return our task list
    def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps(task_list))]
        return mock_response
    
    # Mock the entire Anthropic client
    mock_client = Mock()
    mock_client.messages.create = mock_create
    
    with patch.object(llm_service, 'client', mock_client):
        # Call decompose_project and expect ValueError
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        with pytest.raises(ValueError) as exc_info:
            loop.run_until_complete(
                llm_service.decompose_project(user, project)
            )
        
        # Verify the error message mentions task count
        assert "Task count must be between 5 and 20" in str(exc_info.value), \
            f"Expected error message about task count, got: {exc_info.value}"


@settings(max_examples=100)
@given(
    task_list=invalid_task_list_too_many(),
    data=st.data()
)
def test_task_count_too_many_raises_error(task_list, data):
    """
    Property 3: Task count bounds (validation - too many)
    
    For any project decomposition that returns more than 20 tasks,
    the system should raise a ValueError.
    
    Validates: Requirements 2.1
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{data.draw(st.integers(min_value=1, max_value=10000))}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title=f"Project {data.draw(st.integers(min_value=1, max_value=1000))}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Create LLM service
    llm_service = LLMService()
    
    # Mock the Anthropic client to return our task list
    def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps(task_list))]
        return mock_response
    
    # Mock the entire Anthropic client
    mock_client = Mock()
    mock_client.messages.create = mock_create
    
    with patch.object(llm_service, 'client', mock_client):
        # Call decompose_project and expect ValueError
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        with pytest.raises(ValueError) as exc_info:
            loop.run_until_complete(
                llm_service.decompose_project(user, project)
            )
        
        # Verify the error message mentions task count
        assert "Task count must be between 5 and 20" in str(exc_info.value), \
            f"Expected error message about task count, got: {exc_info.value}"


@settings(max_examples=100)
@given(
    num_tasks=st.integers(min_value=5, max_value=20)
)
def test_all_valid_task_counts_accepted(num_tasks):
    """
    Property 3: Task count bounds (exhaustive)
    
    Verify that all task counts from 5 to 20 (inclusive) are accepted
    without raising an error.
    
    Validates: Requirements 2.1
    """
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=f"user_{num_tasks}@example.com",
        hashed_password="hashed",
        preferred_tone="coach",
        timezone="UTC"
    )
    
    # Create project
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        title=f"Project {num_tasks}",
        description="Test project description",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Create task list with exact count
    task_list = []
    for i in range(num_tasks):
        task_list.append({
            "title": f"Task {i+1}",
            "description": f"Description for task {i+1}",
            "estimated_duration_hours": 4,
            "order": i + 1
        })
    
    # Create LLM service
    llm_service = LLMService()
    
    # Mock the Anthropic client to return our task list
    def mock_create(*args, **kwargs):
        mock_response = Mock()
        mock_response.content = [Mock(text=json.dumps(task_list))]
        return mock_response
    
    # Mock the entire Anthropic client
    mock_client = Mock()
    mock_client.messages.create = mock_create
    
    with patch.object(llm_service, 'client', mock_client):
        # Call decompose_project - should not raise
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            llm_service.decompose_project(user, project)
        )
    
    # Verify we got the expected number of tasks
    assert len(result) == num_tasks, \
        f"Expected {num_tasks} tasks, got {len(result)}"
