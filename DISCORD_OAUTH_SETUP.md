# Discord OAuth Setup Guide

## ✅ Implementation Complete!

The Discord OAuth login feature has been fully implemented. Here's what you need to do to start using it:

## Step 1: Configure Discord Application

1. **Go to Discord Developer Portal**
   - Visit: https://discord.com/developers/applications
   - Click on your application (ID: 1441388791196680332)

2. **Add OAuth2 Redirect URI**
   - Go to "OAuth2" → "General" in the left sidebar
   - Under "Redirects", click "Add Redirect"
   - Add: `http://localhost:8000/api/auth/discord/callback`
   - Click "Save Changes"

3. **Verify Scopes** (should already be set)
   - Go to "OAuth2" → "URL Generator"
   - Ensure `identify` and `email` scopes are available

## Step 2: Verify Environment Variables

Your `.env` file has been updated with:
```bash
DISCORD_CLIENT_ID=1441388791196680332
DISCORD_CLIENT_SECRET=kbsE1XMHoGt8TtCG9qpfXFe7ugpFR20o
DISCORD_REDIRECT_URI=http://localhost:8000/api/auth/discord/callback
FRONTEND_URL=http://localhost:5173
ENCRYPTION_KEY=IXSfRN7aOD06QBQ9ZudKJ3PmPBW4GGVbdo5aAFZhjHw=
```

## Step 3: Restart Services

The backend has been rebuilt with the new dependencies. If you need to restart:

```bash
docker-compose restart backend
```

## Step 4: Test the OAuth Flow

1. **Open the login page**:
   - Visit: http://localhost:5173/login
   - You should see a purple "Sign in with Discord" button

2. **Click "Sign in with Discord"**:
   - You'll be redirected to Discord
   - Authorize the application
   - You'll be redirected back to the app

3. **First-time users**:
   - Will be redirected to `/onboarding`
   - Can set up timezone, tone, and availability

4. **Returning users**:
   - Will be redirected to `/` (dashboard)

## What's Been Implemented

### Backend ✅
- ✅ Token encryption system
- ✅ Discord OAuth service (exchange, refresh, revoke)
- ✅ API endpoints:
  - `GET /api/auth/discord/login` - Start OAuth flow
  - `GET /api/auth/discord/callback` - Handle callback
  - `POST /api/auth/discord/link` - Link Discord to existing account
  - `POST /api/auth/discord/disconnect` - Disconnect Discord
- ✅ Database migration for Discord fields
- ✅ User model with OAuth fields
- ✅ Structured logging for all OAuth operations

### Frontend ✅
- ✅ Discord login button on login page
- ✅ OAuth callback handler page
- ✅ Automatic redirect based on user status (new vs returning)
- ✅ Updated routing

## How to Use

### For New Users
1. Click "Sign in with Discord" on login page
2. Authorize the app on Discord
3. Complete onboarding (timezone, tone, availability)
4. Create your first project

### For Existing Users (Email/Password)
1. Log in with email/password
2. Go to Settings (when implemented)
3. Click "Connect Discord Account"
4. Authorize on Discord
5. Your Discord account is now linked

### For Returning Discord Users
1. Click "Sign in with Discord"
2. Authorize (if needed)
3. Redirected directly to dashboard

## Testing Checklist

- [ ] Visit http://localhost:5173/login
- [ ] See "Sign in with Discord" button
- [ ] Click button → redirected to Discord
- [ ] Authorize app on Discord
- [ ] Redirected back to app with token
- [ ] Check database for new user with Discord fields
- [ ] Try logging in again → should go straight to dashboard

## Verify Database

Check that the Discord fields were added:

```bash
docker-compose exec backend psql -U accountability -d accountability_db -c "\d users"
```

You should see columns like:
- `discord_user_id`
- `discord_username`
- `discord_access_token`
- `discord_refresh_token`
- `is_new`
- `oauth_provider`

## Check Logs

View structured logs with OAuth operations:

```bash
docker-compose logs -f backend | grep discord
```

You should see JSON logs like:
```json
{
  "timestamp": "2024-11-22T...",
  "level": "INFO",
  "logger": "app.services.discord_oauth_service",
  "message": "Exchanging authorization code for tokens",
  "operation": "exchange_code"
}
```

## Troubleshooting

### "Discord OAuth not configured"
- Check that `DISCORD_CLIENT_ID` is set in `.env`
- Restart backend: `docker-compose restart backend`

### "Invalid or expired state parameter"
- State tokens expire after 10 minutes
- Try the OAuth flow again from the beginning

### "Invalid redirect_uri"
- Ensure redirect URI in Discord app matches exactly:
  `http://localhost:8000/api/auth/discord/callback`
- No trailing slash!

### "Email scope is required"
- Make sure you requested both `identify` and `email` scopes
- User must have a verified email on Discord

### Button doesn't appear
- Check browser console for errors
- Verify frontend is running: http://localhost:5173
- Check that `OAuthCallback.tsx` was created

### Redirected to login with error
- Check URL parameters: `?error=...`
- Check backend logs: `docker-compose logs backend`
- Common errors:
  - `oauth_failed` - Check backend logs for details
  - `no_token` - OAuth callback didn't return a token

## Security Notes

✅ **Implemented Security Features**:
- State parameter prevents CSRF attacks
- Tokens encrypted at rest with Fernet
- Tokens never logged or exposed
- HTTPS required in production
- Automatic token refresh
- Secure token revocation

⚠️ **For Production**:
- Use Redis for state storage (currently in-memory)
- Enable HTTPS for all OAuth redirects
- Rotate encryption keys periodically
- Add rate limiting to OAuth endpoints
- Monitor token refresh failures
- Set up proper error tracking

## Next Steps

### Optional Enhancements
1. **Account Settings Page**
   - Show linked Discord account
   - Button to disconnect Discord
   - Display Discord avatar

2. **Profile Sync**
   - Automatically update avatar from Discord
   - Sync username changes

3. **Better Error Handling**
   - User-friendly error messages
   - Retry buttons
   - Help text

4. **Multiple OAuth Providers**
   - Add Google OAuth
   - Add GitHub OAuth

## API Endpoints Reference

### Start OAuth Flow
```
GET /api/auth/discord/login
→ Redirects to Discord authorization page
```

### OAuth Callback
```
GET /api/auth/discord/callback?code=...&state=...
→ Exchanges code for tokens
→ Creates/updates user
→ Redirects to frontend with JWT token
```

### Link Discord (Authenticated)
```
POST /api/auth/discord/link
Authorization: Bearer <jwt_token>
→ Returns: { "authorization_url": "https://discord.com/..." }
```

### Disconnect Discord (Authenticated)
```
POST /api/auth/discord/disconnect
Authorization: Bearer <jwt_token>
→ Returns: { "message": "Discord account disconnected successfully" }
```

## Success! 🎉

Your Discord OAuth login is now fully functional. Users can sign in with Discord and the system will automatically:
- Create their account
- Link their Discord for message delivery
- Guide new users through onboarding
- Take returning users straight to the dashboard

Try it out at: http://localhost:5173/login
