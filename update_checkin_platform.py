#!/usr/bin/env python3
"""
Script to update the platform for existing check-ins.
This is useful if you want to switch from web to Discord for pending check-ins.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.check_in import CheckIn, CheckInStatus

def update_user_checkin_platform(email: str, new_platform: str = "discord", dry_run: bool = True):
    """Update the platform for a user's pending check-ins."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User with email '{email}' not found")
            return
        
        if new_platform == "discord" and not user.discord_user_id:
            print(f"❌ Cannot switch to Discord - user has no discord_user_id")
            print(f"   Please log in via Discord OAuth first")
            return
        
        # Find pending check-ins
        pending_checkins = db.query(CheckIn).join(
            CheckIn.project
        ).filter(
            CheckIn.project.has(user_id=user.id),
            CheckIn.status == CheckInStatus.PENDING
        ).all()
        
        if not pending_checkins:
            print(f"✅ No pending check-ins to update for {email}")
            return
        
        print(f"\n📊 Found {len(pending_checkins)} pending check-ins")
        print(f"{'='*60}")
        
        for ci in pending_checkins:
            old_platform = ci.platform
            print(f"Check-in {ci.id[:8]}... | {old_platform} → {new_platform}")
            
            if not dry_run:
                ci.platform = new_platform
        
        if dry_run:
            print(f"\n⚠️  DRY RUN - No changes made")
            print(f"   Run with --apply to actually update the check-ins")
        else:
            db.commit()
            print(f"\n✅ Updated {len(pending_checkins)} check-ins to use {new_platform}")
            
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_checkin_platform.py <email> [--apply]")
        print("Example: python update_checkin_platform.py user@example.com --apply")
        print("\nWithout --apply, runs in dry-run mode (shows what would change)")
        sys.exit(1)
    
    email = sys.argv[1]
    dry_run = "--apply" not in sys.argv
    
    update_user_checkin_platform(email, "discord", dry_run)
