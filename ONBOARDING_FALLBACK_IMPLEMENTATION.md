# Web Onboarding Fallback Implementation

## Overview

This document describes the implementation of the web onboarding fallback feature for users who cannot receive Discord DMs.

## Requirements Addressed

- **Requirement 7.3**: When DM delivery fails, the OAuth callback shall redirect to web onboarding instead of the dashboard
- **Requirement 7.4**: When the user completes web onboarding, the system shall mark them as onboarded

## Implementation Details

### 1. Backend Changes (auth.py)

**Modified OAuth Callback Flow:**
- When a new user completes Discord OAuth, the backend attempts to trigger the onboarding webhook
- The webhook response indicates whether DM delivery was successful (`dm_sent` field)
- Based on DM delivery status, the backend redirects to different frontend URLs:
  - **DM Success**: `/auth/callback?token={token}&new_user=true&dm_onboarding=true`
  - **DM Failure**: `/onboarding?token={token}&method=web&reason=dm_failed`

**Key Code Changes:**
```python
# Check if DM onboarding is available
if webhook_result and isinstance(webhook_result, dict):
    dm_onboarding_available = webhook_result.get('dm_sent', False)
    
    if not dm_onboarding_available:
        logger.warning("DM delivery failed, redirecting to web onboarding")

# Redirect based on DM availability
if user.is_new and not dm_onboarding_available:
    frontend_url = f"{settings.FRONTEND_URL}/onboarding?token={jwt_token}&method=web&reason=dm_failed"
else:
    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}&new_user={str(user.is_new).lower()}&dm_onboarding={str(dm_onboarding_available).lower()}"
```

### 2. Frontend Changes

#### OAuthCallback.tsx

**Enhanced URL Parameter Handling:**
- Added `dm_onboarding` parameter to determine onboarding method
- Routes new users to appropriate onboarding flow:
  - **DM Onboarding Active**: `/onboarding?method=dm`
  - **DM Onboarding Failed**: `/onboarding?method=web`

**Key Code Changes:**
```typescript
const dmOnboarding = searchParams.get('dm_onboarding') === 'true';

if (newUser) {
  if (dmOnboarding) {
    // DM onboarding is active - show "Check Discord DMs" message
    window.location.href = '/onboarding?method=dm';
  } else {
    // DM onboarding failed - show web onboarding form
    window.location.href = '/onboarding?method=web';
  }
}
```

#### Onboarding.tsx

**Three Onboarding States:**

1. **Loading State**: Shown while determining onboarding method
2. **DM Onboarding State** (`method=dm`): 
   - Displays "Check Your Discord DMs!" message
   - Explains what to expect in Discord
   - Provides fallback button to switch to web onboarding
3. **Web Onboarding State** (`method=web`):
   - Shows existing web onboarding form
   - Displays warning banner if DM delivery failed
   - Allows user to complete onboarding via web interface

**Key Features:**

**DM Onboarding View:**
```typescript
if (onboardingMethod === 'dm') {
  return (
    <div>
      <MessageCircle icon />
      <h1>Check Your Discord DMs!</h1>
      <p>We've sent you a direct message on Discord...</p>
      
      {/* What to expect section */}
      <ul>
        <li>A friendly welcome message</li>
        <li>Questions about your project</li>
        <li>Preferences for check-ins</li>
      </ul>
      
      {/* Fallback option */}
      <button onClick={() => setOnboardingMethod('web')}>
        Use Web Onboarding Instead
      </button>
    </div>
  );
}
```

**DM Failure Warning Banner:**
```typescript
{searchParams.get('reason') === 'dm_failed' && (
  <div className="warning-banner">
    <AlertCircle />
    <h3>Discord DMs Not Available</h3>
    <p>We couldn't send you a Discord DM. This might be because 
       you have DMs disabled from server members.</p>
  </div>
)}
```

## User Flow Diagrams

### Successful DM Onboarding Flow
```
User completes OAuth
  ↓
Backend triggers webhook
  ↓
DM sent successfully (dm_sent=true)
  ↓
Redirect to /auth/callback?dm_onboarding=true
  ↓
Frontend redirects to /onboarding?method=dm
  ↓
User sees "Check Discord DMs" message
  ↓
User completes onboarding in Discord
```

### Failed DM Onboarding Flow
```
User completes OAuth
  ↓
Backend triggers webhook
  ↓
DM delivery fails (dm_sent=false)
  ↓
Redirect to /onboarding?method=web&reason=dm_failed
  ↓
User sees warning banner
  ↓
User completes onboarding via web form
  ↓
User marked as onboarded (is_new=false)
```

### User-Initiated Fallback Flow
```
User sees "Check Discord DMs" message
  ↓
User clicks "Use Web Onboarding Instead"
  ↓
Frontend switches to web onboarding form
  ↓
User completes onboarding via web
```

## Testing Scenarios

### 1. Happy Path - DM Onboarding
- User completes Discord OAuth
- DMs are enabled
- User sees "Check Discord DMs" message
- User completes onboarding in Discord

### 2. DM Failure - Automatic Fallback
- User completes Discord OAuth
- DMs are disabled
- User automatically redirected to web onboarding
- Warning banner displayed
- User completes onboarding via web

### 3. User-Initiated Fallback
- User sees "Check Discord DMs" message
- User prefers web onboarding
- User clicks fallback button
- User completes onboarding via web

### 4. Direct Web Onboarding Access
- User navigates directly to /onboarding
- No method parameter provided
- Defaults to web onboarding
- User completes onboarding via web

## Error Handling

### Backend
- Webhook timeout: Logs error, treats as DM failure
- Webhook HTTP error: Logs error, treats as DM failure
- Webhook exception: Logs error, treats as DM failure

### Frontend
- Missing method parameter: Defaults to web onboarding
- Invalid method parameter: Defaults to web onboarding
- Token missing: Redirects to login with error

## Logging and Monitoring

### Backend Logs
- `onboarding_dm_failed`: Logged when DM delivery fails
- `redirect_to_web_onboarding`: Logged when redirecting to web fallback
- Includes user_id, discord_id, and reason in log context

### Frontend Behavior
- Stores token in localStorage before redirecting
- Preserves onboarding method in URL for page refreshes
- Allows switching between methods without losing progress

## Future Enhancements

1. **Session Persistence**: Save web onboarding progress to allow resumption
2. **DM Retry**: Allow users to retry DM onboarding after enabling DMs
3. **Hybrid Onboarding**: Start in web, continue in Discord
4. **Analytics**: Track which onboarding method users prefer
5. **A/B Testing**: Compare completion rates between methods

## Related Files

- `backend/app/api/auth.py`: OAuth callback and webhook trigger
- `frontend/src/pages/OAuthCallback.tsx`: OAuth callback handler
- `frontend/src/pages/Onboarding.tsx`: Onboarding page with fallback
- `backend/app/services/onboarding_service.py`: Onboarding service logic
- `backend/app/api/webhooks.py`: Onboarding webhook endpoint

## Validation

This implementation satisfies:
- ✅ Requirement 7.3: Redirect to web onboarding on DM failure
- ✅ Requirement 7.4: Mark user as onboarded after web completion
- ✅ User can see appropriate messaging based on onboarding method
- ✅ Fallback option available for users who prefer web onboarding
- ✅ Warning displayed when DM delivery fails
- ✅ Seamless transition between onboarding methods
