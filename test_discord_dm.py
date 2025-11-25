#!/usr/bin/env python3
"""
Script to test Discord DM functionality and manually trigger onboarding.
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal
from app.models.user import User
from app.services.onboarding_service import OnboardingService
import httpx


async def test_discord_dm(email: str, reset_onboarding: bool = False):
    """Test Discord DM functionality for a user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User with email '{email}' not found")
            return
        
        print(f"\n📊 User Information")
        print(f"{'='*60}")
        print(f"Email: {user.email}")
        print(f"User ID: {user.id}")
        print(f"Discord User ID: {user.discord_user_id or '❌ Not set'}")
        print(f"Discord Username: {user.discord_username or 'N/A'}")
        print(f"Is New: {user.is_new}")
        print(f"{'='*60}\n")
        
        if not user.discord_user_id:
            print("❌ User has no Discord ID. Please log in via Discord OAuth first.")
            return
        
        # Option 1: Reset is_new flag to trigger onboarding on next login
        if reset_onboarding:
            print("🔄 Resetting is_new flag to trigger onboarding...")
            user.is_new = True
            db.commit()
            print("✅ User marked as new. Log out and log back in via Discord OAuth to trigger onboarding.")
            return
        
        # Option 2: Manually trigger onboarding webhook
        print("🚀 Manually triggering onboarding webhook...")
        
        webhook_url = "http://localhost:8000/api/webhooks/onboarding/start"
        
        payload = {
            "user_id": str(user.id),
            "discord_id": user.discord_user_id,
            "email": user.email
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Token": "your-webhook-secret"  # Update this
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"\n✅ Webhook triggered successfully!")
                    print(f"   DM Sent: {result.get('dm_sent', False)}")
                    print(f"   Session Created: {result.get('session_created', False)}")
                    
                    if result.get('dm_sent'):
                        print(f"\n📬 Check your Discord DMs for the onboarding message!")
                    else:
                        print(f"\n⚠️  DM was not sent. Reason: {result.get('reason', 'unknown')}")
                        print(f"   Make sure:")
                        print(f"   1. Discord bot is running (docker-compose ps discord-bot)")
                        print(f"   2. You have DMs enabled in Discord settings")
                        print(f"   3. Bot has correct token in .env")
                else:
                    print(f"\n❌ Webhook failed with status {response.status_code}")
                    print(f"   Response: {response.text}")
                    
        except httpx.ConnectError:
            print(f"\n❌ Could not connect to backend. Is it running?")
            print(f"   Try: docker-compose ps backend")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        # Option 3: Test direct DM sending
        print(f"\n\n🧪 Testing direct DM send...")
        print(f"   Attempting to send test DM via Discord bot...")
        
        bot_url = "http://localhost:8001/send-dm"  # Discord bot API
        
        test_payload = {
            "discord_user_id": user.discord_user_id,
            "message": "🧪 **Test Message**\n\nThis is a test message from your accountability assistant! If you're seeing this, Discord DMs are working correctly. 🎉"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(bot_url, json=test_payload)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        print(f"   ✅ Test DM sent successfully!")
                        print(f"   📬 Check your Discord DMs!")
                    else:
                        print(f"   ❌ DM failed: {result.get('reason', 'unknown')}")
                else:
                    print(f"   ❌ Bot API returned status {response.status_code}")
                    
        except httpx.ConnectError:
            print(f"   ⚠️  Could not connect to Discord bot")
            print(f"   Is the bot running? Try: docker-compose ps discord-bot")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_discord_dm.py <email>                    # Test Discord DM")
        print("  python test_discord_dm.py <email> --reset-onboarding # Reset is_new flag")
        print("\nExamples:")
        print("  python test_discord_dm.py user@example.com")
        print("  python test_discord_dm.py user@example.com --reset-onboarding")
        sys.exit(1)
    
    email = sys.argv[1]
    reset = "--reset-onboarding" in sys.argv
    
    asyncio.run(test_discord_dm(email, reset))
