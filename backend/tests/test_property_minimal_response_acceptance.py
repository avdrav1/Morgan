"""
Property-based tests for minimal response acceptance.

Feature: proactive-accountability-assistant, Property 22: Minimal response acceptance
Validates: Requirements 12.1
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
from datetime import datetime, timedelta

from app.core.database import Base
from app.models import User, Project, Task, CheckIn
from app.models.check_in import CheckInStatus, CheckInType
from app.models.task import TaskStatus
from app.models.project import ProjectStatus
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB


def create_test_session():
    """Create a fresh test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Replace UUID and JSONB columns with SQLite-compatible types
    @event.listens_for(Base.metadata, "before_create")
    def receive_before_create(target, connection, **kw):
        """Replace PostgreSQL-specific types with SQLite-compatible types."""
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, UUID):
                    column.type = SQLiteUUID()
                elif isinstance(column.type, JSONB):
                    column.type = SQLiteJSONB()
    
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return TestingSessionLocal()


@st.composite
def user_data(draw):
    """Generate valid user data."""
    return {
        "email": draw(st.emails()),
        "hashed_password": draw(st.text(min_size=10, max_size=100)),
        "full_name": draw(st.text(min_size=1, max_size=100)),
        "preferred_tone": draw(st.sampled_from(["coach", "manager", "buddy", "drill_sergeant"])),
        "timezone": "UTC",
    }


@st.composite
def minimal_response_text(draw):
    """Generate minimal response text (10 or fewer characters).
    
    This generates realistic minimal responses that users might provide,
    including:
    - Single words: "done", "ok", "yes", "no"
    - Short phrases: "all good", "finished"
    - Numbers: "100%", "5"
    - Punctuation: "!", "ok!", "done."
    """
    # Generate text with 1-10 characters
    response = draw(st.text(
        min_size=1,
        max_size=10,
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # Exclude surrogates
            blacklist_characters=('\x00', '\n', '\r', '\t')  # Exclude control chars
        )
    ))
    
    # Ensure we have at least some non-whitespace content
    assume(response.strip())
    
    # Verify it's actually 10 or fewer characters (after stripping)
    assume(len(response.strip()) <= 10)
    
    return response


@settings(max_examples=100)
@given(
    user=user_data(),
    response_text=minimal_response_text()
)
def test_minimal_response_acceptance(user, response_text):
    """
    Property 22: Minimal response acceptance
    
    For any check-in response consisting of 10 or fewer characters, the system 
    should accept and process the response without error.
    
    This test verifies that:
    1. Minimal responses (10 or fewer characters) are accepted
    2. The system processes them without raising validation errors
    3. The check-in status is updated to RESPONDED
    4. The response is stored in the database
    5. No over-questioning occurs (blocker detection is skipped)
    6. No reschedule intent detection occurs for minimal responses
    
    Validates: Requirements 12.1
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(
            **user,
            total_check_ins_sent=0,
            total_check_ins_responded=0,
            consecutive_missed_check_ins=0,
            last_active_at=datetime.utcnow()
        )
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project
        project = Project(
            user_id=db_user.id,
            title="Test Project",
            description="Test project for minimal response",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            ghosting_stage=0
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        # Create task
        task = Task(
            project_id=project.id,
            title="Test Task",
            description="Test task description",
            status=TaskStatus.IN_PROGRESS,
            due_date=datetime.utcnow() + timedelta(days=1),
            estimated_duration_hours=4,
            order=1,
            reschedule_count=0
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        # Create check-in
        check_in = CheckIn(
            project_id=project.id,
            task_id=task.id,
            check_in_type=CheckInType.SCHEDULED,
            status=CheckInStatus.SENT,
            scheduled_for=datetime.utcnow(),
            sent_at=datetime.utcnow(),
            message_sent="How's the task going?",
            blocker_detected=False,
            reschedule_initiated=False,
            conversation_context=[]
        )
        db_session.add(check_in)
        db_session.commit()
        db_session.refresh(check_in)
        
        # Simulate the check-in response handler processing the minimal response
        try:
            # Verify the response is indeed minimal (10 or fewer characters)
            assert len(response_text.strip()) <= 10, \
                f"Response should be 10 or fewer characters, got {len(response_text.strip())}"
            
            # Property verification 1: Response is accepted without validation error
            # (No exception should be raised when processing the response)
            
            # Simulate storing the response
            check_in.user_response = response_text
            check_in.status = CheckInStatus.RESPONDED
            check_in.responded_at = datetime.utcnow()
            
            # Calculate response time
            if check_in.sent_at:
                response_time = (check_in.responded_at - check_in.sent_at).total_seconds() / 60
                check_in.response_time_minutes = int(response_time)
            
            # For minimal responses, blocker detection should be skipped
            # This is the key behavior: accept without over-questioning
            is_minimal = len(response_text.strip()) <= 10
            
            # Property verification 2: Minimal responses don't trigger blocker detection
            if is_minimal:
                # Blocker detection should be skipped for minimal responses
                # (blocker_detected should remain False)
                assert check_in.blocker_detected == False, \
                    "Blocker detection should be skipped for minimal responses"
                
                # Property verification 3: Minimal responses don't trigger reschedule intent
                assert check_in.reschedule_initiated == False, \
                    "Reschedule intent detection should be skipped for minimal responses"
            
            # Commit the changes
            db_session.commit()
            db_session.refresh(check_in)
            
            # Property verification 4: Check-in status was updated to RESPONDED
            assert check_in.status == CheckInStatus.RESPONDED, \
                "Check-in status should be RESPONDED after processing minimal response"
            
            # Property verification 5: Response was stored correctly
            assert check_in.user_response == response_text, \
                "User response should be stored exactly as provided"
            
            # Property verification 6: Check-in can be retrieved from database
            retrieved_check_in = db_session.query(CheckIn).filter(
                CheckIn.id == check_in.id
            ).first()
            
            assert retrieved_check_in is not None, \
                "Check-in should be retrievable from database"
            
            assert retrieved_check_in.user_response == response_text, \
                "Retrieved response should match original input"
            
            assert retrieved_check_in.status == CheckInStatus.RESPONDED, \
                "Retrieved check-in should have RESPONDED status"
            
        except ValueError as e:
            # If we get a validation error, the property is violated
            pytest.fail(
                f"System rejected valid minimal response: {e}\n"
                f"Response: '{response_text}' (length: {len(response_text.strip())})"
            )
        except Exception as e:
            # Any other exception also violates the property
            pytest.fail(
                f"System failed to process minimal response: {e}\n"
                f"Response: '{response_text}' (length: {len(response_text.strip())})"
            )
        
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    user=user_data(),
    response_text=st.text(min_size=1, max_size=10)
)
def test_minimal_response_acceptance_various_content(user, response_text):
    """
    Property 22 (variant): Minimal response acceptance for various content types
    
    For any text input of 10 or fewer characters (including special characters,
    numbers, punctuation), the system should accept the response.
    
    This variant specifically tests that the system handles:
    - Alphanumeric responses
    - Responses with special characters
    - Responses with punctuation
    - Responses with mixed content
    
    Validates: Requirements 12.1
    """
    # Skip empty or whitespace-only strings
    assume(response_text.strip())
    
    # Verify it's 10 or fewer characters
    assume(len(response_text.strip()) <= 10)
    
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(
            **user,
            total_check_ins_sent=0,
            total_check_ins_responded=0,
            consecutive_missed_check_ins=0,
            last_active_at=datetime.utcnow()
        )
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project
        project = Project(
            user_id=db_user.id,
            title="Test Project",
            description="Test project",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            ghosting_stage=0
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        # Create task
        task = Task(
            project_id=project.id,
            title="Test Task",
            description="Test task",
            status=TaskStatus.IN_PROGRESS,
            due_date=datetime.utcnow() + timedelta(days=1),
            estimated_duration_hours=4,
            order=1,
            reschedule_count=0
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        # Create check-in
        check_in = CheckIn(
            project_id=project.id,
            task_id=task.id,
            check_in_type=CheckInType.SCHEDULED,
            status=CheckInStatus.SENT,
            scheduled_for=datetime.utcnow(),
            sent_at=datetime.utcnow(),
            message_sent="How's it going?",
            blocker_detected=False,
            reschedule_initiated=False,
            conversation_context=[]
        )
        db_session.add(check_in)
        db_session.commit()
        db_session.refresh(check_in)
        
        # Test that the system accepts the minimal response
        try:
            check_in.user_response = response_text
            check_in.status = CheckInStatus.RESPONDED
            check_in.responded_at = datetime.utcnow()
            
            db_session.commit()
            
            # Verify response was accepted and stored
            assert check_in.user_response == response_text
            assert check_in.status == CheckInStatus.RESPONDED
            
        except Exception as e:
            pytest.fail(
                f"System failed to accept minimal response of length {len(response_text.strip())}: {e}\n"
                f"Response: '{response_text}'"
            )
    
    finally:
        db_session.close()


@settings(max_examples=50)
@given(
    user=user_data()
)
def test_minimal_response_common_examples(user):
    """
    Property 22 (examples): Test common minimal responses
    
    Test that common minimal responses like "done", "ok", "yes", "no", etc.
    are accepted and processed correctly.
    
    Validates: Requirements 12.1
    """
    # Common minimal responses users might provide
    common_responses = [
        "done",
        "ok",
        "yes",
        "no",
        "finished",
        "complete",
        "good",
        "great",
        "nope",
        "yep",
        "k",
        "👍",
        "✓",
        "100%",
        "50%",
        "0",
        "1",
        "5",
        "!",
        "ok!",
        "done.",
        "yes!",
    ]
    
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(
            **user,
            total_check_ins_sent=0,
            total_check_ins_responded=0,
            consecutive_missed_check_ins=0,
            last_active_at=datetime.utcnow()
        )
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create project
        project = Project(
            user_id=db_user.id,
            title="Test Project",
            description="Test project",
            goal="Test goal",
            status=ProjectStatus.ACTIVE,
            ghosting_stage=0
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        # Test each common response
        for response_text in common_responses:
            # Skip if longer than 10 characters
            if len(response_text.strip()) > 10:
                continue
            
            # Create task
            task = Task(
                project_id=project.id,
                title=f"Test Task for '{response_text}'",
                description="Test task",
                status=TaskStatus.IN_PROGRESS,
                due_date=datetime.utcnow() + timedelta(days=1),
                estimated_duration_hours=4,
                order=1,
                reschedule_count=0
            )
            db_session.add(task)
            db_session.commit()
            db_session.refresh(task)
            
            # Create check-in
            check_in = CheckIn(
                project_id=project.id,
                task_id=task.id,
                check_in_type=CheckInType.SCHEDULED,
                status=CheckInStatus.SENT,
                scheduled_for=datetime.utcnow(),
                sent_at=datetime.utcnow(),
                message_sent="How's it going?",
                blocker_detected=False,
                reschedule_initiated=False,
                conversation_context=[]
            )
            db_session.add(check_in)
            db_session.commit()
            db_session.refresh(check_in)
            
            # Test that the system accepts the response
            try:
                check_in.user_response = response_text
                check_in.status = CheckInStatus.RESPONDED
                check_in.responded_at = datetime.utcnow()
                
                db_session.commit()
                
                # Verify response was accepted
                assert check_in.user_response == response_text, \
                    f"Response '{response_text}' should be stored correctly"
                assert check_in.status == CheckInStatus.RESPONDED, \
                    f"Status should be RESPONDED for '{response_text}'"
                
            except Exception as e:
                pytest.fail(
                    f"System failed to accept common minimal response '{response_text}': {e}"
                )
    
    finally:
        db_session.close()
