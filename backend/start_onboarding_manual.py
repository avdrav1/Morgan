#!/usr/bin/env python3
"""
Manually trigger onboarding for an existing user.
This script queries the database and calls the webhook to start onboarding.
"""

import asyncio
import httpx
import sys
import os

# Configuration
API_BASE_URL = "http://localhost:8000"
DISCORD_USER_ID = "353988409917833217"  # Your Discord ID from the logs

async def get_user_from_db():
    """Query the database directly to get user info."""
    import psycopg2
    
    # Database connection from docker-compose
    conn = psycopg2.connect(
        host="postgres",  # Docker service name
        port="5432",
        database="accountability_db",
        user="accountability",
        password="accountability_dev"
    )
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, discord_user_id FROM users WHERE discord_user_id = %s",
            (DISCORD_USER_ID,)
        )
        result = cursor.fetchone()
        
        if result:
            return {
                "id": str(result[0]),
                "email": result[1],
                "discord_user_id": result[2]
            }
        return None
    finally:
        conn.close()

async def trigger_onboarding():
    """Trigger onboarding by calling the webhook endpoint."""
    
    print(f"Looking up user with Discord ID: {DISCORD_USER_ID}")
    
    try:
        user_data = await get_user_from_db()
        
        if not user_data:
            print("❌ User not found in database.")
            print("   You need to authenticate via Discord OAuth first.")
            return False
        
        user_id = user_data["id"]
        email = user_data.get("email", "test@example.com")
        
        print(f"✅ Found user: {user_id}")
        print(f"   Email: {email}")
        print(f"   Discord ID: {DISCORD_USER_ID}")
        
    except Exception as e:
        print(f"❌ Error looking up user: {e}")
        print("   Make sure the database is running and accessible.")
        return False
    
    # Trigger onboarding webhook
    print("\nTriggering onboarding webhook...")
    
    # Get webhook secret from environment or use JWT secret
    webhook_secret = "c477c4fdbde5834bf08459443585d58b809dba85f05690616874e66dbf27e5"  # From .env
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/api/webhooks/onboarding/start",
                json={
                    "user_id": user_id,
                    "discord_id": DISCORD_USER_ID,
                    "email": email
                },
                headers={
                    "X-Webhook-Token": webhook_secret
                }
            )
            
            if response.status_code == 202:
                data = response.json()
                print(f"✅ Onboarding started successfully!")
                print(f"   Session ID: {data.get('session_id')}")
                print(f"   DM sent: {data.get('dm_sent')}")
                print(f"   Current state: {data.get('current_state')}")
                print("\n🎉 Check your Discord DMs! The bot should have sent you a welcome message.")
                print("   You can now send messages to the bot to continue the onboarding flow.")
                return True
            else:
                print(f"❌ Error starting onboarding: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error triggering onboarding: {e}")
            return False

if __name__ == "__main__":
    print("=" * 60)
    print("Manual Onboarding Trigger")
    print("=" * 60)
    print()
    
    success = asyncio.run(trigger_onboarding())
    
    if success:
        print("\n✅ Done! You should now be able to have an onboarding conversation with the bot.")
        print("   Send a message to the bot in Discord to continue.")
    else:
        print("\n❌ Failed to start onboarding. Check the errors above.")
        sys.exit(1)
