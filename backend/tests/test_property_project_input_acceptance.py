"""
Property-based tests for project input acceptance.

Feature: proactive-accountability-assistant, Property 1: Project input acceptance
Validates: Requirements 1.1
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from app.core.database import Base
from app.models import User, Project
from app.schemas.project import ProjectCreate
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
    }


@st.composite
def free_form_project_description(draw):
    """Generate free-form project descriptions of various types.
    
    This generates realistic free-form text that users might provide,
    including:
    - Short descriptions
    - Long descriptions
    - Descriptions with special characters
    - Descriptions with numbers
    - Descriptions with punctuation
    """
    # Generate text with various characteristics
    base_text = draw(st.text(
        min_size=1,
        max_size=1000,
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # Exclude surrogates
            blacklist_characters=('\x00',)  # Exclude null bytes
        )
    ))
    
    # Ensure we have at least some non-whitespace content
    assume(base_text.strip())
    
    return base_text


@settings(max_examples=100)
@given(
    user=user_data(),
    description=free_form_project_description()
)
def test_project_input_acceptance(user, description):
    """
    Property 1: Project input acceptance
    
    For any free-form text input describing a project, the system should accept 
    the input and respond with a clarification request rather than an error.
    
    This test verifies that:
    1. Any non-empty text can be used as a project description
    2. The system accepts the input without raising validation errors
    3. A project is created in the database (even if in draft/clarification state)
    4. The system does not reject valid free-form input
    
    Validates: Requirements 1.1
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        user_id = db_user.id
        
        # Create a ProjectCreate schema with just the free-form description
        # This simulates what the API endpoint receives
        try:
            project_create = ProjectCreate(description=description)
            
            # Verify the schema accepts the input
            assert project_create.description == description, \
                "Description should be preserved exactly as provided"
            
            # Simulate what the endpoint does: create a project with the description
            # Even if clarification is needed, a project should be created
            project = Project(
                user_id=user_id,
                title="Draft Project",  # Temporary title
                description=description,
                goal=description  # Temporary goal
            )
            
            db_session.add(project)
            db_session.commit()
            project_id = project.id
            project_description = project.description
            
            # Property verification 1: Project was created successfully
            assert project_id is not None, \
                "Project should have an ID after creation"
            
            # Property verification 2: Description was stored correctly
            assert project_description == description, \
                "Project description should match the input exactly"
            
            # Property verification 3: Project can be retrieved from database
            retrieved_project = db_session.query(Project).filter(
                Project.id == project_id
            ).first()
            
            assert retrieved_project is not None, \
                "Project should be retrievable from database"
            
            assert retrieved_project.description == description, \
                "Retrieved project description should match original input"
            
            # Property verification 4: No exceptions were raised
            # (If we got here, the test passed - the system accepted the input)
            
        except ValueError as e:
            # If we get a validation error, the property is violated
            pytest.fail(
                f"System rejected valid free-form input: {e}\n"
                f"Description: {description[:100]}..."
            )
        
    finally:
        db_session.close()


@settings(max_examples=100)
@given(
    user=user_data(),
    description=st.text(min_size=1, max_size=5000)
)
def test_project_input_acceptance_various_lengths(user, description):
    """
    Property 1 (variant): Project input acceptance for various text lengths
    
    For any text input of varying length (from very short to very long),
    the system should accept the input without errors.
    
    This variant specifically tests that the system handles:
    - Very short descriptions (1 character)
    - Medium descriptions (typical user input)
    - Very long descriptions (detailed project plans)
    
    Validates: Requirements 1.1
    """
    # Skip empty or whitespace-only strings
    assume(description.strip())
    
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        user_id = db_user.id
        
        # Test that ProjectCreate schema accepts the description
        try:
            project_create = ProjectCreate(description=description)
            
            # Create project in database
            project = Project(
                user_id=user_id,
                title="Draft Project",
                description=description,
                goal=description
            )
            
            db_session.add(project)
            db_session.commit()
            
            # Verify project was created successfully
            assert project.id is not None
            assert project.description == description
            
        except Exception as e:
            pytest.fail(
                f"System failed to accept description of length {len(description)}: {e}"
            )
    
    finally:
        db_session.close()
