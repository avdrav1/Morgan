"""
Integration test for OAuth callback triggering onboarding webhook.

This test verifies that when a new user completes Discord OAuth,
the onboarding webhook is triggered correctly.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

from app.api.auth import trigger_onboarding_webhook
from app.core.config import settings


@pytest.mark.asyncio
async def test_trigger_onboarding_webhook_success():
    """
    Test that onboarding webhook is triggered successfully for new users.
    
    Validates: Requirements 1.1
    """
    user_id = str(uuid4())
    discord_id = "123456789012345678"
    email = "test@example.com"
    
    # Mock httpx.AsyncClient
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "message": "Onboarding session created successfully",
        "dm_sent": True,
        "session_id": str(uuid4())
    })
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        result = await trigger_onboarding_webhook(user_id, discord_id, email)
        
        assert result is not None
        assert isinstance(result, dict)
        assert result.get("dm_sent") is True
        
        # Verify the webhook was called with correct parameters
        mock_client.return_value.__aenter__.return_value.post.assert_called_once()
        call_args = mock_client.return_value.__aenter__.return_value.post.call_args
        
        # Check URL
        assert "webhooks/onboarding/start" in call_args[0][0]
        
        # Check payload
        assert call_args[1]['json']['user_id'] == user_id
        assert call_args[1]['json']['discord_id'] == discord_id
        assert call_args[1]['json']['email'] == email
        
        # Check headers
        assert 'X-Webhook-Token' in call_args[1]['headers']


@pytest.mark.asyncio
async def test_trigger_onboarding_webhook_timeout():
    """
    Test that webhook timeout is handled gracefully.
    
    Validates: Requirements 1.1
    """
    user_id = str(uuid4())
    discord_id = "123456789012345678"
    email = "test@example.com"
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("Timeout")
        )
        
        result = await trigger_onboarding_webhook(user_id, discord_id, email)
        
        # Should return None on timeout, not raise exception
        assert result is None


@pytest.mark.asyncio
async def test_trigger_onboarding_webhook_http_error():
    """
    Test that webhook HTTP errors are handled gracefully.
    
    Validates: Requirements 1.1
    """
    user_id = str(uuid4())
    discord_id = "123456789012345678"
    email = "test@example.com"
    
    # Mock httpx.AsyncClient with HTTP error
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    import httpx
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        result = await trigger_onboarding_webhook(user_id, discord_id, email)
        
        # Should return None on HTTP error, not raise exception
        assert result is None


@pytest.mark.asyncio
async def test_trigger_onboarding_webhook_passes_correct_data():
    """
    Test that webhook receives all required data fields.
    
    Validates: Requirements 1.1
    """
    user_id = str(uuid4())
    discord_id = "987654321098765432"
    email = "newuser@example.com"
    
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "message": "Onboarding session created successfully",
        "dm_sent": True,
        "session_id": str(uuid4())
    })
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post
        
        result = await trigger_onboarding_webhook(user_id, discord_id, email)
        
        assert result is not None
        assert isinstance(result, dict)
        
        # Verify all required fields are passed
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        
        assert 'user_id' in payload
        assert 'discord_id' in payload
        assert 'email' in payload
        assert payload['user_id'] == user_id
        assert payload['discord_id'] == discord_id
        assert payload['email'] == email
