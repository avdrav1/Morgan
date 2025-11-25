# Guide: Switching to Discord Messages

This guide explains how to switch from web-based check-ins to Discord DMs for an existing user.

## How It Works

The system automatically determines the messaging platform based on:
1. **If user has `discord_user_id`** → Use Discord DMs
2. **Otherwise** → Use web interface

## Prerequisites

✅ You must have logged in via Discord OAuth (which you have)
✅ Discord bot must be running
✅ You must have DMs enabled from server members in Discord

## Step 1: Check Your Current Status

Run this command to check if Discord is configured:

```bash
docker-compose exec backend python /app/../check_discord_status.py your-email@example.com
```

This will show:
- Whether you have a Discord user ID
- Your current check-in platform
- Recent check-ins and their platforms

## Step 2: Enable Discord DMs (If Needed)

If you can't receive DMs from the bot:

1. Open Discord
2. Go to **User Settings** → **Privacy & Safety**
3. Enable **"Allow direct messages from server members"**
4. If you're in a server with the bot, make sure DMs are enabled for that server

## Step 3: Update Existing Check-ins (Optional)

If you have pending check-ins scheduled for "web" platform, you can update them:

### Dry Run (See what would change):
```bash
docker-compose exec backend python /app/../update_checkin_platform.py your-email@example.com
```

### Actually Update:
```bash
docker-compose exec backend python /app/../update_checkin_platform.py your-email@example.com --apply
```

## Step 4: Test Discord Messaging

### Option A: Wait for Next Scheduled Check-in
New check-ins will automatically use Discord if you have a `discord_user_id`.

### Option B: Manually Trigger a Test Message
You can create a test check-in or project to verify Discord messaging works.

## Troubleshooting

### "User has no discord_user_id"
**Solution:** Log out and log back in via Discord OAuth. The OAuth flow should populate your `discord_user_id`.

### "DM delivery failed"
**Possible causes:**
1. DMs are disabled in Discord settings
2. You've blocked the bot
3. Bot doesn't share a server with you
4. Bot is offline

**Check bot status:**
```bash
docker-compose logs discord-bot
```

### Check-ins still going to web
**Possible causes:**
1. Check-ins were created before Discord was configured (update them with the script above)
2. `discord_user_id` is not set in database
3. Bot can't send DMs to you

## How New Check-ins Are Created

When the scheduler creates new check-ins, it uses this logic:

```python
# From backend/app/tasks/scheduler.py
platform = "discord" if user.discord_user_id else "web"
```

So as long as you have a `discord_user_id`, all **new** check-ins will use Discord automatically.

## Manual Database Update (Advanced)

If you need to manually set your Discord user ID:

```bash
docker-compose exec backend python
```

Then in Python:
```python
from app.core.database import SessionLocal
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email == "your-email@example.com").first()

# Check current value
print(f"Current discord_user_id: {user.discord_user_id}")

# If it's None, you need to log in via Discord OAuth again
# The OAuth flow will populate this automatically

db.close()
```

## Verification

After switching, verify Discord messaging is working:

1. Check your Discord DMs for messages from the bot
2. Run the status check script to see platform is "discord"
3. Check logs: `docker-compose logs discord-bot | grep "Sent DM"`

## Need Help?

If you're still having issues:
1. Check bot logs: `docker-compose logs discord-bot`
2. Check backend logs: `docker-compose logs backend`
3. Verify Discord OAuth is working: Check `TEST_DISCORD_OAUTH.md`
