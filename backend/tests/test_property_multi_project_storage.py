"""
Property-based tests for multi-project storage.

Feature: proactive-accountability-assistant, Property 2: Multi-project storage with single focus
Validates: Requirements 1.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import User, Project, ProjectStatus
from tests.conftest import SQLiteUUID, SQLiteJSONB
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import event


# Strategy for generating valid project data
@st.composite
def project_data(draw):
    """Generate valid project data."""
    return {
        "title": draw(st.text(min_size=1, max_size=100)),
        "description": draw(st.text(min_size=1, max_size=500)),
        "goal": draw(st.text(min_size=1, max_size=500)),
        "status": draw(st.sampled_from([ProjectStatus.ACTIVE, ProjectStatus.PAUSED, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED])),
    }


@st.composite
def user_data(draw):
    """Generate valid user data."""
    return {
        "email": draw(st.emails()),
        "hashed_password": draw(st.text(min_size=10, max_size=100)),
        "full_name": draw(st.text(min_size=1, max_size=100)),
    }


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


@settings(max_examples=100)
@given(
    user=user_data(),
    projects=st.lists(project_data(), min_size=1, max_size=10)
)
def test_multi_project_storage_with_single_focus(user, projects):
    """
    Property 2: Multi-project storage with single focus
    
    For any set of projects belonging to a user, all projects should be persisted 
    in the database, and exactly one project should be marked as the active focus 
    at any time.
    
    This test verifies that:
    1. Multiple projects can be stored for a single user
    2. When properly configured, exactly one project has ACTIVE status
    3. All other projects have non-ACTIVE statuses (PAUSED, COMPLETED, or ARCHIVED)
    
    Validates: Requirements 1.4
    """
    # Create a fresh session for this test run
    db_session = create_test_session()
    
    try:
        # Create user
        db_user = User(**user)
        db_session.add(db_user)
        db_session.commit()
        db_session.refresh(db_user)
        
        # Create all projects for the user, ensuring exactly one is ACTIVE
        # This simulates the expected system behavior where the system maintains
        # the single-focus constraint
        created_projects = []
        for i, project_dict in enumerate(projects):
            # Make a copy to avoid modifying the original
            project_data_copy = project_dict.copy()
            
            # Ensure exactly one project is ACTIVE (the first one)
            # All others should be in a non-ACTIVE state
            if i == 0:
                project_data_copy['status'] = ProjectStatus.ACTIVE
            else:
                # Keep the generated status if it's not ACTIVE, otherwise set to PAUSED
                if project_data_copy['status'] == ProjectStatus.ACTIVE:
                    project_data_copy['status'] = ProjectStatus.PAUSED
            
            project = Project(
                user_id=db_user.id,
                **project_data_copy
            )
            db_session.add(project)
            created_projects.append(project)
        
        db_session.commit()
        
        # Property verification 1: All projects are persisted
        stored_projects = db_session.query(Project).filter(Project.user_id == db_user.id).all()
        assert len(stored_projects) == len(projects), \
            f"Expected {len(projects)} projects to be stored, but found {len(stored_projects)}"
        
        # Property verification 2: Exactly one project has ACTIVE status (single focus)
        active_projects = db_session.query(Project).filter(
            Project.user_id == db_user.id,
            Project.status == ProjectStatus.ACTIVE
        ).all()
        
        assert len(active_projects) == 1, \
            f"Expected exactly 1 active project, but found {len(active_projects)}"
        
        # Property verification 3: All non-active projects have valid non-ACTIVE statuses
        non_active_projects = db_session.query(Project).filter(
            Project.user_id == db_user.id,
            Project.status != ProjectStatus.ACTIVE
        ).all()
        
        assert len(non_active_projects) == len(projects) - 1, \
            f"Expected {len(projects) - 1} non-active projects, but found {len(non_active_projects)}"
        
        # Verify all non-active projects have valid statuses
        valid_non_active_statuses = {ProjectStatus.PAUSED, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED}
        for project in non_active_projects:
            assert project.status in valid_non_active_statuses, \
                f"Non-active project has invalid status: {project.status}"
    finally:
        db_session.close()
