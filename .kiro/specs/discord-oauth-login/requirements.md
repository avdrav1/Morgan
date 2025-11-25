# Requirements Document: Discord OAuth Login

## Introduction

This feature adds Discord OAuth 2.0 authentication to the Proactive Accountability Assistant, allowing users to sign in with their Discord account. This streamlines onboarding by automatically linking the user's Discord account for message delivery and eliminates the need for separate email/password registration.

## Glossary

- **OAuth 2.0**: An authorization framework that enables applications to obtain limited access to user accounts
- **Discord OAuth**: Discord's implementation of OAuth 2.0 for third-party authentication
- **Authorization Code Flow**: OAuth flow where the user authorizes the app and receives a code that's exchanged for an access token
- **Access Token**: A credential used to access Discord's API on behalf of the user
- **Refresh Token**: A long-lived token used to obtain new access tokens when they expire
- **Discord User ID**: A unique identifier for a Discord user (snowflake ID)
- **Scope**: Permissions requested from the user (e.g., `identify`, `email`)
- **Redirect URI**: The URL where Discord sends the user after authorization
- **State Parameter**: A random value used to prevent CSRF attacks during OAuth flow

## Requirements

### Requirement 1: Discord OAuth Login Button

**User Story:** As a new user, I want to sign in with my Discord account so that I can quickly start using the accountability assistant without creating a separate account.

#### Acceptance Criteria

1. WHEN a user visits the login page THEN the system SHALL display a "Sign in with Discord" button prominently
2. WHEN a user clicks the "Sign in with Discord" button THEN the system SHALL redirect the user to Discord's OAuth authorization page
3. WHEN redirecting to Discord THEN the system SHALL request the `identify` and `email` scopes
4. WHEN redirecting to Discord THEN the system SHALL include a state parameter to prevent CSRF attacks
5. WHEN the user is already logged in THEN the system SHALL NOT display the login page

### Requirement 2: OAuth Authorization Flow

**User Story:** As a user authorizing the app, I want a secure and standard OAuth flow so that my Discord credentials remain protected.

#### Acceptance Criteria

1. WHEN Discord redirects back to the application THEN the system SHALL validate the state parameter matches the original request
2. WHEN the state parameter is invalid THEN the system SHALL reject the authorization and display an error
3. WHEN the state parameter is valid THEN the system SHALL exchange the authorization code for an access token
4. WHEN exchanging the code THEN the system SHALL use the client secret securely on the backend
5. WHEN the token exchange fails THEN the system SHALL display a user-friendly error message

### Requirement 3: User Account Creation and Linking

**User Story:** As a user signing in with Discord for the first time, I want the system to automatically create my account so that I can start immediately.

#### Acceptance Criteria

1. WHEN a user completes Discord OAuth for the first time THEN the system SHALL create a new user account
2. WHEN creating the account THEN the system SHALL store the Discord user ID, username, email, and avatar URL
3. WHEN creating the account THEN the system SHALL generate a secure JWT token for the user
4. WHEN a user with an existing Discord-linked account signs in THEN the system SHALL log them in without creating a duplicate account
5. WHEN creating the account THEN the system SHALL set default preferences (timezone, tone, availability)

### Requirement 4: Token Management

**User Story:** As a system administrator, I want Discord tokens to be securely stored and refreshed so that the system can continue sending messages to users.

#### Acceptance Criteria

1. WHEN receiving tokens from Discord THEN the system SHALL store the access token and refresh token encrypted in the database
2. WHEN the access token expires THEN the system SHALL automatically use the refresh token to obtain a new access token
3. WHEN the refresh token is invalid or expired THEN the system SHALL mark the Discord connection as disconnected
4. WHEN tokens are stored THEN the system SHALL NOT log or expose tokens in any way
5. WHEN a user revokes app access in Discord THEN the system SHALL handle the error gracefully and notify the user

### Requirement 5: Onboarding Integration

**User Story:** As a new user who just signed in with Discord, I want to be guided through onboarding so that I can set up my first project.

#### Acceptance Criteria

1. WHEN a new user completes Discord OAuth THEN the system SHALL redirect them to the onboarding flow
2. WHEN a returning user completes Discord OAuth THEN the system SHALL redirect them to the dashboard
3. WHEN in onboarding THEN the system SHALL collect timezone, preferred tone, and availability preferences
4. WHEN onboarding is complete THEN the system SHALL prompt the user to create their first project
5. WHEN the user skips project creation THEN the system SHALL allow them to proceed to an empty dashboard

### Requirement 6: Account Linking for Existing Users

**User Story:** As an existing user with email/password login, I want to link my Discord account so that I can receive messages via Discord.

#### Acceptance Criteria

1. WHEN a logged-in user visits account settings THEN the system SHALL display an option to "Connect Discord Account"
2. WHEN a user clicks "Connect Discord Account" THEN the system SHALL initiate the OAuth flow
3. WHEN OAuth completes successfully THEN the system SHALL link the Discord account to the existing user account
4. WHEN a Discord account is already linked to another user THEN the system SHALL prevent linking and display an error
5. WHEN a user has a linked Discord account THEN the system SHALL display the Discord username and option to disconnect

### Requirement 7: Security and Privacy

**User Story:** As a user, I want my Discord account information to be handled securely so that my privacy is protected.

#### Acceptance Criteria

1. WHEN storing Discord tokens THEN the system SHALL encrypt them at rest using industry-standard encryption
2. WHEN transmitting OAuth data THEN the system SHALL use HTTPS for all communications
3. WHEN a user disconnects their Discord account THEN the system SHALL delete all stored Discord tokens
4. WHEN accessing Discord user data THEN the system SHALL only request the minimum necessary scopes
5. WHEN a user deletes their account THEN the system SHALL revoke Discord tokens and delete all Discord-related data

### Requirement 8: Error Handling

**User Story:** As a user encountering an OAuth error, I want clear feedback so that I understand what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN the user denies authorization in Discord THEN the system SHALL display a message explaining they need to authorize to continue
2. WHEN the OAuth flow times out THEN the system SHALL display an error and provide a retry button
3. WHEN Discord's API is unavailable THEN the system SHALL display a temporary error message and suggest trying again later
4. WHEN an unexpected error occurs THEN the system SHALL log the error details and display a generic user-friendly message
5. WHEN displaying errors THEN the system SHALL NOT expose sensitive technical details to the user

### Requirement 9: Discord Bot Integration

**User Story:** As a user who signed in with Discord, I want the accountability bot to automatically work in my DMs so that I don't need additional setup.

#### Acceptance Criteria

1. WHEN a user completes Discord OAuth THEN the system SHALL have permission to send them direct messages
2. WHEN the bot sends a message THEN the system SHALL use the stored Discord user ID
3. WHEN the user has blocked the bot THEN the system SHALL detect the error and notify the user via the web interface
4. WHEN the user hasn't added the bot THEN the system SHALL provide instructions on how to enable DMs
5. WHEN sending messages THEN the system SHALL respect Discord's rate limits

### Requirement 10: Session Management

**User Story:** As a user, I want my login session to persist appropriately so that I don't have to re-authenticate frequently.

#### Acceptance Criteria

1. WHEN a user logs in via Discord THEN the system SHALL create a session that lasts 7 days
2. WHEN the session expires THEN the system SHALL prompt the user to log in again
3. WHEN a user logs out THEN the system SHALL invalidate their session immediately
4. WHEN a user closes the browser THEN the system SHALL maintain the session (not session-only cookies)
5. WHEN a user logs in from multiple devices THEN the system SHALL allow concurrent sessions
