# OAuth Callback to Onboarding Webhook Integration

## Overview

This document describes the integration between the Discord OAuth callback and the onboarding webhook system. When a new user completes Discord OAuth authentication, the system automatically triggers the onboarding webhook to start the Discord DM onboarding flow.

## Implementation Details

### Changes Made

1. **Updated `backend/app/api/auth.py`**:
   - Added `httpx` import for making HTTP requests
   - Created `trigger_onboarding_webhook()` helper function
   - Modified `discord_oauth_callback()` to call the webhook for new users
   - Added graceful error handling for webhook failures
   - Updated frontend redirect URL to include `dm_onboarding` parameter

2. **Created `backend/tests/test_oauth_webhook_integration.py`**:
   - Unit tests for webhook trigger functionality
   - Tests for success, timeout, and HTTP error scenarios
   - Tests for correct data passing

### Webhook Trigger Function

The `trigger_onboarding_webhook()` function:
- Makes an HTTP POST request to `/api/webhooks/onboarding/start`
- Passes `user_id`, `discord_id`, and `email` in the payload
- Includes authentication via `X-Webhook-Token` header
- Has a 10-second timeout
- Returns `True` on success, `False` on any failure
- Logs all operations for debugging

### Error Handling

The implementation handles webhook failures gracefully:
- **Timeout**: Logs error and returns `False`
- **HTTP Error**: Logs status code and error message, returns `False`
- **Other Exceptions**: Logs full exception with stack trace, returns `False`

When webhook fails:
- User is still authenticated successfully
- Frontend receives `dm_onboarding=false` parameter
- User can fall back to web-based onboarding
- No disruption to the OAuth flow

### OAuth Callback Flow

```
1. User completes Discord OAuth
2. Backend exchanges code for tokens
3. Backend fetches user info from Discord
4. Backend creates/updates user account
5. IF user.is_new == True:
   a. Trigger onboarding webhook
   b. Log success or failure
6. Generate JWT token
7. Redirect to frontend with:
   - token: JWT for authentication
   - new_user: true/false
   - dm_onboarding: true/false (indicates webhook success)
```

### Frontend Integration

The frontend receives three parameters in the OAuth callback:
- `token`: JWT authentication token
- `new_user`: Whether this is a new user
- `dm_onboarding`: Whether DM onboarding was triggered successfully

Frontend logic:
```javascript
if (new_user && dm_onboarding) {
  // Show "Check your Discord DMs" message
  // User will complete onboarding via Discord
} else if (new_user && !dm_onboarding) {
  // Redirect to web-based onboarding form
  // DM onboarding failed or unavailable
} else {
  // Existing user, redirect to dashboard
}
```

## Testing

### Unit Tests

Run the unit tests:
```bash
cd backend
pytest tests/test_oauth_webhook_integration.py -v
```

Tests cover:
- Successful webhook trigger
- Timeout handling
- HTTP error handling
- Correct data passing

### Integration Tests

The existing webhook tests in `test_webhook_onboarding.py` verify:
- Webhook endpoint authentication
- Session creation
- Error handling
- Idempotency

### Manual Testing

1. **Start the backend**:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Initiate Discord OAuth**:
   - Navigate to `http://localhost:8000/api/auth/discord/login`
   - Complete Discord OAuth flow
   - Check logs for webhook trigger messages

3. **Verify webhook call**:
   - Check backend logs for "Triggering onboarding webhook"
   - Check for "Onboarding webhook triggered successfully" or error messages
   - Verify frontend redirect includes `dm_onboarding` parameter

4. **Test failure scenarios**:
   - Stop the backend temporarily to simulate timeout
   - Verify OAuth still completes successfully
   - Verify `dm_onboarding=false` in redirect URL

## Configuration

### Environment Variables

The webhook uses the following configuration:
- `WEBHOOK_SECRET`: Secret token for webhook authentication (optional)
  - Falls back to `JWT_SECRET_KEY` if not set
- `FRONTEND_URL`: Frontend URL for OAuth redirect

### Webhook URL

The webhook URL is currently hardcoded to:
```
http://localhost:8000/api/webhooks/onboarding/start
```

For production, this should be:
- Configurable via environment variable
- Use HTTPS
- Point to the correct backend domain

## Security Considerations

1. **Authentication**: Webhook requires `X-Webhook-Token` header
2. **Validation**: Webhook validates user exists and Discord ID matches
3. **Logging**: All operations are logged with correlation IDs
4. **Error Handling**: Failures don't expose sensitive information

## Requirements Validation

This implementation validates **Requirement 1.1**:
> WHEN a new user completes Discord OAuth THEN the Discord Bot SHALL send a welcome DM within 5 seconds

The webhook trigger is the first step in this flow:
1. ✅ OAuth callback detects new user
2. ✅ Webhook is triggered with user data
3. ✅ Webhook creates onboarding session
4. ⏳ Discord bot sends welcome DM (Task 8)

## Next Steps

Task 8 will implement the Discord bot handler to:
- Listen for webhook events (or poll for new sessions)
- Send welcome DM to new users
- Handle DM delivery failures
- Route user responses to onboarding service

## Troubleshooting

### Webhook not triggered
- Check logs for "New user detected" message
- Verify `user.is_new == True` in database
- Check for errors in webhook trigger function

### Webhook fails
- Check backend is running
- Verify webhook endpoint is accessible
- Check `WEBHOOK_SECRET` configuration
- Review error logs for specific failure reason

### Frontend not receiving dm_onboarding parameter
- Check OAuth callback redirect URL in logs
- Verify frontend is parsing URL parameters correctly
- Check for URL encoding issues
