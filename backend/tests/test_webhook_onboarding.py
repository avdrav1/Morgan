"""
Tests for the onboarding webhook endpoint.

These tests verify that the webhook endpoint correctly handles
onboarding session creation requests.
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.onboarding_session import OnboardingSession, OnboardingState


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override."""
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
def webhook_headers():
    """Create headers with valid webhook token."""
    # Use JWT_SECRET_KEY as fallback if WEBHOOK_SECRET is not set
    webhook_secret = getattr(settings, 'WEBHOOK_SECRET', None) or settings.JWT_SECRET_KEY
    return {"X-Webhook-Token": webhook_secret}


@pytest.fixture
def test_user_with_discord(db_session):
    """Create a test user with Discord linked."""
    user = User(
        email="discord_user@example.com",
        hashed_password="hashed_password",
        discord_user_id="123456789012345678",
        discord_username="testuser",
        is_new=True,
        preferred_tone="supportive",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_webhook_health_check(client):
    """Test webhook health check endpoint."""
    response = client.get("/api/webhooks/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "webhooks"


def test_start_onboarding_webhook_success(client, db_session, test_user_with_discord, webhook_headers, monkeypatch):
    """Test successful onboarding webhook call with DM success."""
    from unittest.mock import AsyncMock
    
    # Mock the _send_welcome_dm function to return True (DM sent successfully)
    async def mock_send_welcome_dm(discord_user_id: str) -> bool:
        return True
    
    import app.api.webhooks
    monkeypatch.setattr(app.api.webhooks, "_send_welcome_dm", mock_send_welcome_dm)
    
    payload = {
        "user_id": str(test_user_with_discord.id),
        "discord_id": test_user_with_discord.discord_user_id,
        "email": test_user_with_discord.email
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    
    assert response.status_code == 202
    data = response.json()
    assert data["message"] == "Onboarding session created successfully"
    assert data["user_id"] == str(test_user_with_discord.id)
    assert data["discord_id"] == test_user_with_discord.discord_user_id
    assert data["current_state"] == OnboardingState.WELCOME.value
    assert data["dm_sent"] is True
    assert data["use_web_onboarding"] is False
    assert "session_id" in data
    
    # Verify session was created in database
    session = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user_with_discord.id
    ).first()
    assert session is not None
    assert session.current_state == OnboardingState.WELCOME
    assert session.discord_id == test_user_with_discord.discord_user_id


def test_start_onboarding_webhook_missing_token(client, test_user_with_discord):
    """Test webhook call without authentication token."""
    payload = {
        "user_id": str(test_user_with_discord.id),
        "discord_id": test_user_with_discord.discord_user_id,
        "email": test_user_with_discord.email
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload)
    
    assert response.status_code == 401
    data = response.json()
    assert "authentication token" in data["detail"].lower()


def test_start_onboarding_webhook_invalid_token(client, test_user_with_discord):
    """Test webhook call with invalid authentication token."""
    payload = {
        "user_id": str(test_user_with_discord.id),
        "discord_id": test_user_with_discord.discord_user_id,
        "email": test_user_with_discord.email
    }
    
    headers = {"X-Webhook-Token": "invalid_token"}
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=headers)
    
    assert response.status_code == 401
    data = response.json()
    assert "invalid" in data["detail"].lower()


def test_start_onboarding_webhook_user_not_found(client, webhook_headers):
    """Test webhook call with non-existent user."""
    fake_user_id = str(uuid4())
    payload = {
        "user_id": fake_user_id,
        "discord_id": "123456789012345678",
        "email": "nonexistent@example.com"
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_start_onboarding_webhook_no_discord_linked(client, db_session, webhook_headers):
    """Test webhook call for user without Discord linked."""
    user = User(
        email="no_discord@example.com",
        hashed_password="hashed_password",
        is_new=True,
        preferred_tone="supportive",
        timezone="UTC"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    payload = {
        "user_id": str(user.id),
        "discord_id": "123456789012345678",
        "email": user.email
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    
    assert response.status_code == 400
    data = response.json()
    assert "discord" in data["detail"].lower()


def test_start_onboarding_webhook_discord_id_mismatch(client, test_user_with_discord, webhook_headers):
    """Test webhook call with mismatched Discord ID."""
    payload = {
        "user_id": str(test_user_with_discord.id),
        "discord_id": "999999999999999999",  # Different from user's discord_id
        "email": test_user_with_discord.email
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    
    assert response.status_code == 400
    data = response.json()
    assert "mismatch" in data["detail"].lower()


def test_start_onboarding_webhook_invalid_payload(client, webhook_headers):
    """Test webhook call with invalid payload."""
    payload = {
        "user_id": "not-a-uuid",
        "discord_id": "",  # Empty discord_id
        "email": "test@example.com"
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    
    assert response.status_code == 422  # Validation error


def test_start_onboarding_webhook_dm_failure(client, db_session, test_user_with_discord, webhook_headers, monkeypatch):
    """Test webhook call when DM delivery fails."""
    from unittest.mock import AsyncMock
    
    # Mock the _send_welcome_dm function to return False (DM failed)
    async def mock_send_welcome_dm(discord_user_id: str) -> bool:
        return False
    
    import app.api.webhooks
    monkeypatch.setattr(app.api.webhooks, "_send_welcome_dm", mock_send_welcome_dm)
    
    payload = {
        "user_id": str(test_user_with_discord.id),
        "discord_id": test_user_with_discord.discord_user_id,
        "email": test_user_with_discord.email
    }
    
    response = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    
    assert response.status_code == 202
    data = response.json()
    assert data["message"] == "DM delivery failed, user should use web onboarding"
    assert data["dm_sent"] is False
    assert data["use_web_onboarding"] is True
    assert "session_id" not in data  # No session created on DM failure
    
    # Verify no session was created in database
    session = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user_with_discord.id
    ).first()
    assert session is None


def test_start_onboarding_webhook_idempotent(client, db_session, test_user_with_discord, webhook_headers, monkeypatch):
    """Test that calling webhook multiple times is idempotent."""
    from unittest.mock import AsyncMock
    
    # Mock the _send_welcome_dm function to return True (DM sent successfully)
    async def mock_send_welcome_dm(discord_user_id: str) -> bool:
        return True
    
    import app.api.webhooks
    monkeypatch.setattr(app.api.webhooks, "_send_welcome_dm", mock_send_welcome_dm)
    
    payload = {
        "user_id": str(test_user_with_discord.id),
        "discord_id": test_user_with_discord.discord_user_id,
        "email": test_user_with_discord.email
    }
    
    # First call
    response1 = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    assert response1.status_code == 202
    session_id_1 = response1.json()["session_id"]
    
    # Second call
    response2 = client.post("/api/webhooks/onboarding/start", json=payload, headers=webhook_headers)
    assert response2.status_code == 202
    session_id_2 = response2.json()["session_id"]
    
    # Should return the same session
    assert session_id_1 == session_id_2
    
    # Verify only one session exists
    sessions = db_session.query(OnboardingSession).filter(
        OnboardingSession.user_id == test_user_with_discord.id
    ).all()
    assert len(sessions) == 1
