"""
Property-based tests for adaptive frequency logic.

Feature: proactive-accountability-assistant, Property 8 & 9: Adaptive frequency
Validates: Requirements 3.4, 3.5
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
import uuid

from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.check_in import CheckIn, CheckInStatus
from app.services.scheduler_service import SchedulerService


@st.composite
def check_in_list_with_response_rate(draw, target_rate):
    """
    Generate a list of check-ins with approximately the target response rate.
    
    Args:
        target_rate: Target response rate (0.0 to 1.0)
    """
    # Generate 10 check-ins (as per requirements analysis of "last 10 check-ins")
    num_check_ins = 10
    num_responded = int(num_check_ins * target_rate)
    
    # Create check-ins with appropriate status
    check_ins = []
    for i in range(num_check_ins):
        status = CheckInStatus.RESPONDED if i < num_responded else CheckInStatus.MISSED
        check_in = CheckIn(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            check_in_type="scheduled",
            status=status,
            scheduled_for=datetime(2024, 6, 1 + i, 12, 0)
        )
        check_ins.append(check_in)
    
    return check_ins


@settings(max_examples=100)
@given(
    response_rate=st.floats(min_value=0.0, max_value=0.29, allow_nan=False, allow_infinity=False)
)
def test_adaptive_frequency_for_low_responsiveness(response_rate):
    """
    Property 8: Adaptive frequency for low responsiveness
    
    For any user with a response rate below 30% over the last 10 check-ins, 
    the check-in frequency should be reduced compared to the baseline.
    
    Validates: Requirements 3.4
    """
    # Create test data
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone="UTC"
    )
    
    project = Project(
        user_id=user.id,
        title="Test Project",
        description="Test",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Generate check-ins with low response rate
    num_check_ins = 10
    num_responded = int(num_check_ins * response_rate)
    
    check_ins = []
    for i in range(num_check_ins):
        status = CheckInStatus.RESPONDED if i < num_responded else CheckInStatus.MISSED
        check_in = CheckIn(
            id=uuid.uuid4(),
            project_id=project.id,
            task_id=uuid.uuid4(),
            check_in_type="scheduled",
            status=status,
            scheduled_for=datetime(2024, 6, 1 + i, 12, 0)
        )
        check_ins.append(check_in)
    
    # Test adaptive frequency logic
    scheduler = SchedulerService()
    adaptation, reason = scheduler.should_adapt_frequency(user, project, check_ins)
    
    # Verify frequency should be decreased for low responsiveness
    assert adaptation == "decrease", \
        f"Expected 'decrease' for response rate {response_rate:.1%}, got '{adaptation}'"
    assert "Low response rate" in reason or "reducing" in reason.lower(), \
        f"Reason should mention low response rate: {reason}"


@settings(max_examples=100)
@given(
    response_rate=st.floats(min_value=0.71, max_value=1.0, allow_nan=False, allow_infinity=False)
)
def test_adaptive_frequency_for_high_responsiveness(response_rate):
    """
    Property 9: Adaptive frequency for high responsiveness
    
    For any user with a response rate above 70% over the last 10 check-ins, 
    the check-in frequency should be maintained or increased compared to the baseline.
    
    Validates: Requirements 3.5
    """
    # Create test data
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone="UTC"
    )
    
    project = Project(
        user_id=user.id,
        title="Test Project",
        description="Test",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Generate check-ins with high response rate
    num_check_ins = 10
    num_responded = int(num_check_ins * response_rate)
    
    check_ins = []
    for i in range(num_check_ins):
        status = CheckInStatus.RESPONDED if i < num_responded else CheckInStatus.MISSED
        check_in = CheckIn(
            id=uuid.uuid4(),
            project_id=project.id,
            task_id=uuid.uuid4(),
            check_in_type="scheduled",
            status=status,
            scheduled_for=datetime(2024, 6, 1 + i, 12, 0)
        )
        check_ins.append(check_in)
    
    # Test adaptive frequency logic
    scheduler = SchedulerService()
    adaptation, reason = scheduler.should_adapt_frequency(user, project, check_ins)
    
    # Calculate actual response rate after integer rounding
    actual_response_rate = num_responded / num_check_ins
    
    # Verify frequency should be increased or maintained for high responsiveness
    # Note: Due to integer rounding, some rates may fall into "maintain" category
    if actual_response_rate > 0.70:
        assert adaptation == "increase", \
            f"Expected 'increase' for actual response rate {actual_response_rate:.1%}, got '{adaptation}'"
        assert "High response rate" in reason or "engaged" in reason.lower(), \
            f"Reason should mention high response rate or engagement: {reason}"
    else:
        # Edge case: rounding caused rate to be exactly 0.70
        assert adaptation in ["increase", "maintain"], \
            f"Expected 'increase' or 'maintain' for response rate {response_rate:.1%} " \
            f"(actual: {actual_response_rate:.1%}), got '{adaptation}'"


@settings(max_examples=100)
@given(
    response_rate=st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False)
)
def test_adaptive_frequency_for_moderate_responsiveness(response_rate):
    """
    Additional test: Moderate responsiveness should maintain frequency.
    
    For response rates between 30% and 70%, frequency should be maintained.
    """
    # Create test data
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        timezone="UTC"
    )
    
    project = Project(
        user_id=user.id,
        title="Test Project",
        description="Test",
        goal="Test goal",
        status=ProjectStatus.ACTIVE
    )
    
    # Generate check-ins with moderate response rate
    num_check_ins = 10
    num_responded = int(num_check_ins * response_rate)
    
    check_ins = []
    for i in range(num_check_ins):
        status = CheckInStatus.RESPONDED if i < num_responded else CheckInStatus.MISSED
        check_in = CheckIn(
            id=uuid.uuid4(),
            project_id=project.id,
            task_id=uuid.uuid4(),
            check_in_type="scheduled",
            status=status,
            scheduled_for=datetime(2024, 6, 1 + i, 12, 0)
        )
        check_ins.append(check_in)
    
    # Test adaptive frequency logic
    scheduler = SchedulerService()
    adaptation, reason = scheduler.should_adapt_frequency(user, project, check_ins)
    
    # Verify frequency should be maintained for moderate responsiveness
    assert adaptation == "maintain", \
        f"Expected 'maintain' for response rate {response_rate:.1%}, got '{adaptation}'"
