import pytest
import json
from sqlalchemy import create_engine, event, TypeDecorator, String, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.core.database import Base


# Custom UUID type for SQLite compatibility
class SQLiteUUID(TypeDecorator):
    """Platform-independent UUID type.
    
    Uses PostgreSQL's UUID type when available, otherwise uses
    String(36) for SQLite.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


# Custom JSONB type for SQLite compatibility
class SQLiteJSONB(TypeDecorator):
    """Platform-independent JSONB type.
    
    Uses PostgreSQL's JSONB type when available, otherwise uses
    Text with JSON serialization for SQLite.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            return json.loads(value)


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database for testing."""
    # Use in-memory SQLite for fast testing
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
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session with expire_on_commit=False to prevent detached instance errors
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine,
        expire_on_commit=False  # This prevents objects from being expired after commit
    )
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)



@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    from app.models import User
    from datetime import datetime
    
    user = User(
        email="test@example.com",
        hashed_password="hashed_password_here",
        preferred_tone="coach",
        timezone="UTC",
        total_check_ins_sent=0,
        total_check_ins_responded=0,
        consecutive_missed_check_ins=0,
        last_active_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_project(db_session, test_user):
    """Create a test project."""
    from app.models import Project
    from app.models.project import ProjectStatus
    
    project = Project(
        user_id=test_user.id,
        title="Test Project",
        description="A test project for property testing",
        goal="Complete the test successfully",
        status=ProjectStatus.ACTIVE,
        ghosting_stage=0
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
