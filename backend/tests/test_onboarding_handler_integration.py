"""
Integration tests for Discord bot onboarding handler.

Tests the integration between the Discord bot handler and the backend
onboarding service through the webhook endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime

from app.main import app
from app.models.user import User
from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.core.config import settings
from app.core.database import get_db


@pytest.fixture
def client(db_session):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_with_discord(db_session):
    """Create a test user with Discord linked."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        discord_user_id="123456789",
        is_new=True,
        preferred_tone="supportive"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_onboarding_session(db_session, test_user_with_discord: User):
    """Create a test onboarding session."""
    session = OnboardingSession(
        id=uuid4(),
        user_id=test_user_with_discord.id,
        discord_id=test_user_with_discord.discord_user_id,
        current_state=OnboardingState.COLLECT_PROJECT_NAME,
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        conversation_history=[]
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_check_onboarding_status_active_session(
    client: TestClient,
    test_user_with_discord: User,
    test_onboarding_session: OnboardingSession
):
    """Test checking onboarding status with active session."""
    response = client.get(
        f"/api/webhooks/onboarding/status/{test_user_with_discord.discord_user_id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_session"] is True
    assert data["current_state"] == OnboardingState.COLLECT_PROJECT_NAME.value
    assert "session_id" in data


def test_check_onboarding_status_no_session(
    client: TestClient,
    test_user_with_discord: User
):
    """Test checking onboarding status with no active session."""
    response = client.get(
        f"/api/webhooks/onboarding/status/{test_user_with_discord.discord_user_id}"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_session"] is False


def test_check_onboarding_status_user_not_found(client: TestClient):
    """Test checking onboarding status for non-existent user."""
    response = client.get("/api/webhooks/onboarding/status/999999999")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_process_onboarding_message_success(
    client: TestClient,
    test_user_with_discord: User,
    test_onboarding_session: OnboardingSession
):
    """Test processing an onboarding message successfully."""
    response = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "discord_user_id": test_user_with_discord.discord_user_id,
            "message": "My Awesome Project",
            "author_name": "TestUser"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "current_state" in data
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0


def test_process_onboarding_message_no_session(
    client: TestClient,
    test_user_with_discord: User
):
    """Test processing message with no active onboarding session."""
    response = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "discord_user_id": test_user_with_discord.discord_user_id,
            "message": "Hello",
            "author_name": "TestUser"
        }
    )
    
    assert response.status_code == 404
    assert "no active onboarding session" in response.json()["detail"].lower()


def test_process_onboarding_message_user_not_found(client: TestClient):
    """Test processing message for non-existent user."""
    response = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "discord_user_id": "999999999",
            "message": "Hello",
            "author_name": "TestUser"
        }
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_process_onboarding_message_missing_fields(client: TestClient):
    """Test processing message with missing required fields."""
    # Missing message
    response = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "discord_user_id": "123456789",
            "author_name": "TestUser"
        }
    )
    
    assert response.status_code == 400
    assert "missing required fields" in response.json()["detail"].lower()
    
    # Missing discord_user_id
    response = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "message": "Hello",
            "author_name": "TestUser"
        }
    )
    
    assert response.status_code == 400
    assert "missing required fields" in response.json()["detail"].lower()


def test_onboarding_conversation_flow(
    client: TestClient,
    db_session: Session,
    test_user_with_discord: User,
    test_onboarding_session: OnboardingSession
):
    """Test a multi-message onboarding conversation flow."""
    # First message - project name
    response1 = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "discord_user_id": test_user_with_discord.discord_user_id,
            "message": "My Awesome Project",
            "author_name": "TestUser"
        }
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert "reply" in data1
    
    # Verify conversation history was updated
    db_session.refresh(test_onboarding_session)
    assert len(test_onboarding_session.conversation_history) >= 2  # User message + bot response
    
    # Second message - continue conversation
    response2 = client.post(
        "/api/webhooks/onboarding/message",
        json={
            "discord_user_id": test_user_with_discord.discord_user_id,
            "message": "Build a great app",
            "author_name": "TestUser"
        }
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert "reply" in data2
    
    # Verify conversation history grew
    db_session.refresh(test_onboarding_session)
    assert len(test_onboarding_session.conversation_history) >= 4  # 2 user messages + 2 bot responses
