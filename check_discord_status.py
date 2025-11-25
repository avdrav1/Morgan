#!/usr/bin/env python3
"""
Quick script to check if a user is set up for Discord messaging.
Run this from the backend directory.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal
from app.models.user import User

def check_user_discord_status(email: str):
    """Check if a user is configured for Discord messaging."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User with email '{email}' not found")
            return
        
        print(f"\n📊 User Status for: {email}")
        print(f"{'='*60}")
        print(f"User ID: {user.id}")
        print(f"Discord User ID: {user.discord_user_id or '❌ Not set'}")
        print(f"Discord Username: {user.discord_username or 'N/A'}")
        print(f"OAuth Provider: {user.oauth_provider or 'N/A'}")
        print(f"Is New User: {user.is_new}")
        print(f"Messaging Paused: {user.messaging_paused}")
        print(f"{'='*60}")
        
        if user.discord_user_id:
            print("\n✅ Discord is configured!")
            print("   → Check-ins will be sent via Discord DMs")
            print("   → Make sure you have DMs enabled from server members")
        else:
            print("\n❌ Discord is NOT configured")
            print("   → Check-ins will be sent via web interface")
            print("   → Log in via Discord OAuth to enable Discord DMs")
        
        # Check for existing check-ins
        from app.models.check_in import CheckIn
        check_ins = db.query(CheckIn).join(
            CheckIn.project
        ).filter(
            CheckIn.project.has(user_id=user.id)
        ).order_by(CheckIn.created_at.desc()).limit(5).all()
        
        if check_ins:
            print(f"\n📬 Recent Check-ins:")
            for ci in check_ins:
                print(f"   - {ci.check_in_type.value} | Platform: {ci.platform} | Status: {ci.status.value}")
        else:
            print("\n📭 No check-ins scheduled yet")
            
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_discord_status.py <email>")
        print("Example: python check_discord_status.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    check_user_discord_status(email)
