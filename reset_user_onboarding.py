#!/usr/bin/env python3
"""
Simple script to reset a user's onboarding status.
This will make them go through Discord DM onboarding on next login.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal
from app.models.user import User


def reset_user_onboarding(email: str):
    """Reset a user's onboarding status."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User with email '{email}' not found")
            return False
        
        print(f"\n📊 Current Status:")
        print(f"   Email: {user.email}")
        print(f"   Discord ID: {user.discord_user_id or '❌ Not set'}")
        print(f"   Is New: {user.is_new}")
        
        if not user.discord_user_id:
            print(f"\n❌ Cannot enable Discord onboarding - user has no Discord ID")
            print(f"   Please log in via Discord OAuth first")
            return False
        
        # Set user as new
        user.is_new = True
        db.commit()
        
        print(f"\n✅ User marked as new!")
        print(f"\n📝 Next Steps:")
        print(f"   1. Log out of the web app")
        print(f"   2. Log back in via Discord OAuth")
        print(f"   3. You should receive a Discord DM to start onboarding")
        print(f"\n💡 Make sure:")
        print(f"   - Discord bot is running: docker-compose ps discord-bot")
        print(f"   - DMs are enabled in Discord settings")
        
        return True
        
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reset_user_onboarding.py <email>")
        print("Example: python reset_user_onboarding.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    reset_user_onboarding(email)
