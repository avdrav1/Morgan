# Discord OAuth Implementation Status

## ✅ Completed Backend Implementation

### 1. Core Infrastructure
- ✅ Created `backend/app/core/encryption.py` for secure token storage
- ✅ Updated `backend/app/core/config.py` with Discord OAuth settings
- ✅ Created database migration `i8a9b0c1d2e3_add_discord_oauth_fields.py`
- ✅ Updated User model with Discord OAuth fields

### 2. Discord OAuth Service
- ✅ Created `backend/app/services/discord_oauth_service.py` with:
  - Token exchange
  - Token refresh
  - User info fetching
  - Token revocation
  - User creation/linking logic

### 3. API Endpoints
- ✅ Added to `backend/app/api/auth.py`:
  - `GET /api/auth/discord/login` - Initiate OAuth flow
  - `GET /api/auth/discord/callback` - Handle OAuth callback
  - `POST /api/auth/discord/link` - Link Discord to existing account
  - `POST /api/auth/discord/disconnect` - Disconnect Discord account

### 4. Dependencies
- ✅ Added `cryptography==41.0.7` to requirements.txt
- ✅ Updated `.env.example` with Discord OAuth configuration

## 🚧 Next Steps

### Backend
1. **Run database migration**:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

2. **Rebuild backend container** (for new dependencies):
   ```bash
   docker-compose up -d --build backend
   ```

3. **Set up Discord Application**:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to OAuth2 settings
   - Add redirect URI: `http://localhost:8000/api/auth/discord/callback`
   - Copy Client ID and Client Secret
   - Add to `backend/.env`:
     ```
     DISCORD_CLIENT_ID=your_client_id
     DISCORD_CLIENT_SECRET=your_client_secret
     ENCRYPTION_KEY=generate_with_fernet
     ```

4. **Generate encryption key**:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

### Frontend (Still TODO)
1. **Create OAuth Callback Page** (`frontend/src/pages/OAuthCallback.tsx`)
2. **Add Discord Login Button** to Login page
3. **Update Login Page** with Discord button styling
4. **Add Discord Icon** component
5. **Update Auth Context** to handle OAuth tokens
6. **Add Account Settings** page for Discord linking/unlinking

### Testing (Still TODO)
1. **Unit Tests** for Discord OAuth service
2. **Integration Tests** for OAuth flow
3. **Property-Based Tests** for the 10 correctness properties

## Configuration Required

### Environment Variables
Add these to `backend/.env`:
```bash
# Discord OAuth
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
DISCORD_REDIRECT_URI=http://localhost:8000/api/auth/discord/callback

# Frontend
FRONTEND_URL=http://localhost:5173

# Encryption
ENCRYPTION_KEY=your_fernet_key_here
```

### Discord Application Setup
1. Visit https://discord.com/developers/applications
2. Click "New Application"
3. Name it "Accountability Assistant" (or your preferred name)
4. Go to "OAuth2" → "General"
5. Add Redirect URI: `http://localhost:8000/api/auth/discord/callback`
6. Under "OAuth2" → "URL Generator":
   - Select scopes: `identify`, `email`
   - Copy the generated URL for testing
7. Copy Client ID and Client Secret to your `.env` file

## How It Works

### OAuth Flow
1. User clicks "Sign in with Discord" button
2. Frontend redirects to `/api/auth/discord/login`
3. Backend generates state token and redirects to Discord
4. User authorizes the app on Discord
5. Discord redirects back to `/api/auth/discord/callback` with code
6. Backend exchanges code for access/refresh tokens
7. Backend fetches user info from Discord
8. Backend creates/updates user account
9. Backend generates JWT token
10. Backend redirects to frontend with JWT token
11. Frontend stores token and redirects to dashboard or onboarding

### Security Features
- State parameter prevents CSRF attacks
- Tokens encrypted at rest with Fernet
- Automatic token refresh before expiration
- Secure token revocation on disconnect
- HTTPS-only in production

## Frontend Implementation Guide

### 1. OAuth Callback Page
Create `frontend/src/pages/OAuthCallback.tsx`:
```typescript
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  
  useEffect(() => {
    const token = searchParams.get('token');
    const newUser = searchParams.get('new_user') === 'true';
    const error = searchParams.get('error');
    
    if (error) {
      navigate('/login?error=' + error);
      return;
    }
    
    if (token) {
      localStorage.setItem('token', token);
      // Redirect based on whether user is new
      navigate(newUser ? '/onboarding' : '/');
    } else {
      navigate('/login?error=no_token');
    }
  }, [searchParams, navigate]);
  
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing sign in...</p>
      </div>
    </div>
  );
}
```

### 2. Discord Login Button
Add to `frontend/src/pages/Login.tsx`:
```typescript
const handleDiscordLogin = () => {
  window.location.href = 'http://localhost:8000/api/auth/discord/login';
};

// In your JSX:
<button
  onClick={handleDiscordLogin}
  className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-base font-medium rounded-lg text-white bg-indigo-600 hover:bg-indigo-700"
>
  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
    {/* Discord icon SVG path */}
  </svg>
  Sign in with Discord
</button>
```

### 3. Update Routes
Add to `frontend/src/App.tsx`:
```typescript
import OAuthCallback from './pages/OAuthCallback';

// In your routes:
<Route path="/auth/callback" element={<OAuthCallback />} />
```

## Testing the Implementation

### Manual Testing Steps
1. Start the backend: `docker-compose up -d backend`
2. Visit: `http://localhost:8000/api/auth/discord/login`
3. Authorize the app on Discord
4. Verify you're redirected back with a token
5. Check database to see user was created with Discord fields populated

### Verify Database
```sql
SELECT id, email, discord_user_id, discord_username, is_new, oauth_provider 
FROM users 
WHERE discord_user_id IS NOT NULL;
```

## Troubleshooting

### "Discord OAuth not configured"
- Ensure `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` are set in `.env`
- Restart backend after adding environment variables

### "Invalid or expired state parameter"
- State tokens expire after 10 minutes
- Try the OAuth flow again from the beginning

### "Failed to exchange authorization code"
- Check that redirect URI in Discord app matches exactly
- Verify client secret is correct
- Check backend logs for detailed error

### "Email scope is required"
- Ensure you requested `identify email` scopes in Discord app
- User must have a verified email on Discord

## Production Considerations

1. **Use Redis for state storage** instead of in-memory dict
2. **Enable HTTPS** for all OAuth redirects
3. **Rotate encryption keys** periodically
4. **Monitor token refresh** failures
5. **Set up proper error tracking** (Sentry, etc.)
6. **Add rate limiting** to OAuth endpoints
7. **Implement proper session management**
8. **Add CSRF protection** beyond state parameter
9. **Log all OAuth events** for security auditing
10. **Test token revocation** thoroughly
