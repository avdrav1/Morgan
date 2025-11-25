# Design Document: Discord OAuth Login

## Overview

This feature implements Discord OAuth 2.0 authentication using the Authorization Code Flow. Users can sign in with their Discord account, which automatically creates or links their account and enables Discord DM delivery without additional configuration.

The implementation follows Discord's OAuth2 best practices and integrates seamlessly with the existing authentication system while maintaining security and user privacy.

## Architecture

### OAuth Flow Diagram

```
┌─────────┐                                    ┌─────────────┐
│ Browser │                                    │   Discord   │
│         │                                    │   OAuth     │
└────┬────┘                                    └──────┬──────┘
     │                                                │
     │  1. Click "Sign in with Discord"              │
     │────────────────────────────────────────►      │
     │                                                │
     │  2. Redirect to Discord OAuth                 │
     │◄───────────────────────────────────────       │
     │                                                │
     │  3. User authorizes app                       │
     │───────────────────────────────────────►       │
     │                                                │
     │  4. Redirect with code & state                │
     │◄───────────────────────────────────────       │
     │                                                │
┌────▼────┐                                    ┌─────▼──────┐
│ Backend │                                    │  Discord   │
│   API   │                                    │    API     │
└────┬────┘                                    └──────┬─────┘
     │                                                │
     │  5. Exchange code for tokens                  │
     │───────────────────────────────────────►       │
     │                                                │
     │  6. Return access & refresh tokens            │
     │◄───────────────────────────────────────       │
     │                                                │
     │  7. Fetch user info                           │
     │───────────────────────────────────────►       │
     │                                                │
     │  8. Return user data                          │
     │◄───────────────────────────────────────       │
     │                                                │
     │  9. Create/update user account                │
     │  10. Generate JWT token                       │
     │  11. Return to frontend                       │
     │                                                │
```

## Components and Interfaces

### 1. Frontend Components

#### Login Page Enhancement

```typescript
// frontend/src/pages/Login.tsx
interface LoginPageProps {
  onSuccess: (token: string) => void;
}

// New Discord OAuth button component
const DiscordLoginButton: React.FC = () => {
  const handleDiscordLogin = () => {
    // Redirect to backend OAuth initiation endpoint
    window.location.href = `${API_URL}/api/auth/discord/login`;
  };
  
  return (
    <button onClick={handleDiscordLogin}>
      <DiscordIcon />
      Sign in with Discord
    </button>
  );
};
```

#### OAuth Callback Handler

```typescript
// frontend/src/pages/OAuthCallback.tsx
const OAuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');
    
    if (error) {
      // Handle OAuth error
      navigate('/login?error=' + error);
      return;
    }
    
    if (code && state) {
      // Exchange code for token via backend
      exchangeCodeForToken(code, state);
    }
  }, [searchParams]);
  
  return <LoadingSpinner />;
};
```

### 2. Backend API Endpoints

#### OAuth Initiation Endpoint

```python
# backend/app/api/auth.py

@router.get("/discord/login")
async def discord_login_initiate(
    redirect_uri: Optional[str] = None
):
    """
    Initiate Discord OAuth flow.
    
    Generates a state token, stores it in session/cache,
    and redirects to Discord's authorization URL.
    """
    state = secrets.token_urlsafe(32)
    
    # Store state in Redis with 10-minute expiration
    await redis_client.setex(
        f"oauth_state:{state}",
        600,  # 10 minutes
        "pending"
    )
    
    # Build Discord OAuth URL
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    
    discord_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    
    return RedirectResponse(discord_url)
```

#### OAuth Callback Endpoint

```python
@router.get("/discord/callback")
async def discord_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle Discord OAuth callback.
    
    Validates state, exchanges code for tokens,
    fetches user info, creates/updates user account,
    and returns JWT token.
    """
    # Validate state
    stored_state = await redis_client.get(f"oauth_state:{state}")
    if not stored_state:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter"
        )
    
    # Delete used state
    await redis_client.delete(f"oauth_state:{state}")
    
    # Exchange code for tokens
    token_data = await discord_oauth_service.exchange_code(code)
    
    # Fetch user info from Discord
    discord_user = await discord_oauth_service.get_user_info(
        token_data["access_token"]
    )
    
    # Create or update user account
    user = await discord_oauth_service.create_or_update_user(
        db=db,
        discord_user=discord_user,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
    )
    
    # Generate JWT token
    jwt_token = create_access_token(data={"sub": user.email})
    
    # Redirect to frontend with token
    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}&new_user={user.is_new}"
    
    return RedirectResponse(frontend_url)
```

#### Account Linking Endpoint

```python
@router.post("/discord/link")
async def link_discord_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate Discord OAuth flow for linking to existing account.
    
    Similar to login but stores user_id in state for linking.
    """
    state = secrets.token_urlsafe(32)
    
    # Store state with user_id for linking
    await redis_client.setex(
        f"oauth_state:{state}",
        600,
        json.dumps({"user_id": str(current_user.id), "action": "link"})
    )
    
    # Build Discord OAuth URL
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    
    discord_url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    
    return {"authorization_url": discord_url}
```

### 3. Discord OAuth Service

```python
# backend/app/services/discord_oauth_service.py

class DiscordOAuthService:
    """Service for handling Discord OAuth operations."""
    
    def __init__(self):
        self.client_id = settings.DISCORD_CLIENT_ID
        self.client_secret = settings.DISCORD_CLIENT_SECRET
        self.redirect_uri = settings.DISCORD_REDIRECT_URI
        self.token_url = "https://discord.com/api/oauth2/token"
        self.api_base = "https://discord.com/api/v10"
    
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from Discord
            
        Returns:
            Dict with access_token, refresh_token, expires_in, token_type
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dict with new access_token, refresh_token, expires_in
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch user information from Discord API.
        
        Args:
            access_token: Valid Discord access token
            
        Returns:
            Dict with id, username, discriminator, email, avatar, etc.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/users/@me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def revoke_token(self, token: str) -> None:
        """
        Revoke a Discord access or refresh token.
        
        Args:
            token: Token to revoke
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "token": token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://discord.com/api/oauth2/token/revoke",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
    
    async def create_or_update_user(
        self,
        db: Session,
        discord_user: Dict[str, Any],
        access_token: str,
        refresh_token: str,
        expires_at: datetime
    ) -> User:
        """
        Create a new user or update existing user with Discord info.
        
        Args:
            db: Database session
            discord_user: User data from Discord API
            access_token: Discord access token
            refresh_token: Discord refresh token
            expires_at: Token expiration time
            
        Returns:
            User object
        """
        discord_id = discord_user["id"]
        
        # Check if user exists with this Discord ID
        user = db.query(User).filter(User.discord_user_id == discord_id).first()
        
        if user:
            # Update existing user
            user.discord_username = discord_user["username"]
            user.discord_discriminator = discord_user.get("discriminator", "0")
            user.discord_avatar = discord_user.get("avatar")
            user.discord_access_token = encrypt_token(access_token)
            user.discord_refresh_token = encrypt_token(refresh_token)
            user.discord_token_expires_at = expires_at
            user.is_new = False
        else:
            # Create new user
            email = discord_user.get("email")
            if not email:
                raise HTTPException(
                    status_code=400,
                    detail="Email scope is required for registration"
                )
            
            # Check if email already exists
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                # Link Discord to existing account
                existing_user.discord_user_id = discord_id
                existing_user.discord_username = discord_user["username"]
                existing_user.discord_discriminator = discord_user.get("discriminator", "0")
                existing_user.discord_avatar = discord_user.get("avatar")
                existing_user.discord_access_token = encrypt_token(access_token)
                existing_user.discord_refresh_token = encrypt_token(refresh_token)
                existing_user.discord_token_expires_at = expires_at
                user = existing_user
            else:
                # Create completely new user
                user = User(
                    email=email,
                    full_name=discord_user.get("global_name") or discord_user["username"],
                    discord_user_id=discord_id,
                    discord_username=discord_user["username"],
                    discord_discriminator=discord_user.get("discriminator", "0"),
                    discord_avatar=discord_user.get("avatar"),
                    discord_access_token=encrypt_token(access_token),
                    discord_refresh_token=encrypt_token(refresh_token),
                    discord_token_expires_at=expires_at,
                    preferred_tone="coach",  # Default
                    timezone="UTC",  # Will be set in onboarding
                    is_new=True
                )
                db.add(user)
        
        db.commit()
        db.refresh(user)
        return user


# Singleton instance
discord_oauth_service = DiscordOAuthService()
```

## Data Models

### Enhanced User Model

```python
class User(Base):
    __tablename__ = "users"
    
    # Existing fields...
    id: UUID
    email: str
    full_name: Optional[str]
    hashed_password: Optional[str]  # Now optional for OAuth users
    
    # Discord OAuth fields
    discord_user_id: Optional[str] = Column(String, unique=True, index=True)
    discord_username: Optional[str]
    discord_discriminator: Optional[str]
    discord_avatar: Optional[str]
    discord_access_token: Optional[str]  # Encrypted
    discord_refresh_token: Optional[str]  # Encrypted
    discord_token_expires_at: Optional[datetime]
    
    # Flags
    is_new: bool = Column(Boolean, default=True)  # For onboarding redirect
    oauth_provider: Optional[str]  # 'discord', 'email', etc.
```

### Token Encryption

```python
# backend/app/core/encryption.py

from cryptography.fernet import Fernet
from app.core.config import settings

cipher = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token."""
    return cipher.decrypt(encrypted_token.encode()).decode()
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: State parameter validation

*For any* OAuth callback request, the state parameter must match a previously generated and stored state value, otherwise the request should be rejected.
**Validates: Requirements 2.1, 2.2**

### Property 2: No duplicate Discord accounts

*For any* Discord user ID, there should be at most one user account in the system with that Discord ID.
**Validates: Requirements 3.4**

### Property 3: Token encryption at rest

*For any* stored Discord access or refresh token, the token must be encrypted in the database.
**Validates: Requirements 7.1**

### Property 4: Automatic token refresh

*For any* expired Discord access token with a valid refresh token, the system should automatically obtain a new access token before making API calls.
**Validates: Requirements 4.2**

### Property 5: OAuth scope validation

*For any* Discord OAuth request, the system should only request the `identify` and `email` scopes.
**Validates: Requirements 7.4**

### Property 6: New user onboarding redirect

*For any* user completing OAuth for the first time (is_new=true), the system should redirect them to the onboarding flow.
**Validates: Requirements 5.1**

### Property 7: Returning user dashboard redirect

*For any* user completing OAuth who is not new (is_new=false), the system should redirect them to the dashboard.
**Validates: Requirements 5.2**

### Property 8: Token revocation on disconnect

*For any* user who disconnects their Discord account, all stored Discord tokens should be revoked and deleted.
**Validates: Requirements 7.3**

### Property 9: Account linking uniqueness

*For any* Discord account being linked to an existing user, if that Discord account is already linked to a different user, the linking should fail.
**Validates: Requirements 6.4**

### Property 10: Session persistence

*For any* user who logs in via Discord, their session should remain valid for 7 days unless explicitly logged out.
**Validates: Requirements 10.1**

## Error Handling

### OAuth Errors

**User Denies Authorization**
- Redirect to login page with `error=access_denied`
- Display: "You need to authorize the app to continue. Please try again."

**Invalid State Parameter**
- Return 400 Bad Request
- Log security event
- Display: "Invalid authorization request. Please try logging in again."

**Token Exchange Failure**
- Log error details
- Display: "Failed to complete sign-in. Please try again."
- Provide retry button

**Discord API Unavailable**
- Return 503 Service Unavailable
- Display: "Discord is temporarily unavailable. Please try again in a few minutes."

### Account Linking Errors

**Discord Account Already Linked**
- Return 409 Conflict
- Display: "This Discord account is already linked to another user."

**User Already Has Discord Linked**
- Return 409 Conflict
- Display: "You already have a Discord account linked. Disconnect it first to link a different account."

## Security Considerations

### Token Storage
- All Discord tokens encrypted at rest using Fernet (symmetric encryption)
- Encryption key stored in environment variables, never in code
- Tokens never logged or exposed in API responses

### State Parameter
- Cryptographically random 32-byte value
- Stored in Redis with 10-minute expiration
- Validated and deleted after single use (prevents replay attacks)

### HTTPS Only
- All OAuth redirects use HTTPS
- Redirect URIs validated against whitelist

### Rate Limiting
- OAuth endpoints rate-limited to prevent abuse
- 5 attempts per IP per 15 minutes

### Token Refresh
- Automatic refresh before expiration
- Graceful handling of revoked tokens
- User notified if re-authorization needed

## Testing Strategy

### Unit Tests
- State parameter generation and validation
- Token encryption/decryption
- User creation logic
- Account linking logic
- Error handling for each OAuth step

### Integration Tests
- Complete OAuth flow (mocked Discord API)
- Token refresh flow
- Account linking flow
- Error scenarios (denied access, invalid state, etc.)

### Property-Based Tests
Using Hypothesis library:

1. **Property 1: State validation** - Generate random states, verify only stored ones are accepted
2. **Property 2: No duplicate Discord IDs** - Generate random Discord users, verify uniqueness constraint
3. **Property 3: Token encryption** - Generate random tokens, verify they're encrypted in DB
4. **Property 4: Token refresh** - Generate expired tokens, verify refresh is triggered
5. **Property 5: Scope validation** - Verify OAuth URLs only contain allowed scopes
6. **Property 6-7: Redirect logic** - Verify new vs returning user redirects
7. **Property 8: Token revocation** - Verify tokens are deleted on disconnect
8. **Property 9: Linking uniqueness** - Verify duplicate linking is prevented
9. **Property 10: Session duration** - Verify session expiration timing

## Configuration

### Environment Variables

```bash
# Discord OAuth
DISCORD_CLIENT_ID=your_client_id_here
DISCORD_CLIENT_SECRET=your_client_secret_here
DISCORD_REDIRECT_URI=http://localhost:8000/api/auth/discord/callback

# Encryption
ENCRYPTION_KEY=your_fernet_key_here  # Generate with: Fernet.generate_key()

# Frontend
FRONTEND_URL=http://localhost:5173
```

### Discord Application Setup

1. Create application at https://discord.com/developers/applications
2. Add OAuth2 redirect URI: `http://localhost:8000/api/auth/discord/callback`
3. Enable `identify` and `email` scopes
4. Copy Client ID and Client Secret to environment variables

## Future Enhancements

1. **Multiple OAuth Providers** - Add Google, GitHub, etc.
2. **Account Merging** - Allow users to merge multiple OAuth accounts
3. **Discord Server Integration** - Allow bot to work in servers, not just DMs
4. **Profile Sync** - Automatically update avatar/username from Discord
5. **OAuth Token Monitoring** - Dashboard showing token status and expiration
