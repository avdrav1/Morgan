#!/usr/bin/env python3
"""
Script to reset and create a fresh onboarding session for testing.
Usage: python reset_onboarding.py [discord_id]
"""
import sys
import os
import requests
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv('backend/.env')

# Configuration
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'accountability_db')
DB_USER = os.getenv('DB_USER', 'accountability')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'accountability_dev')
JWT_SECRET = os.getenv('JWT_SECRET_KEY')

# Default test user
DEFAULT_DISCORD_ID = '353988409917833217'
DEFAULT_USER_ID = 'f6e77b09-17e9-4243-9646-f4f973aec8c0'
DEFAULT_EMAIL = 'avdrav@gmail.com'


def delete_existing_session(discord_id: str):
    """Delete existing onboarding session from database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM onboarding_sessions WHERE discord_id = %s",
            (discord_id,)
        )
        deleted_count = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✓ Deleted {deleted_count} existing session(s) for Discord ID: {discord_id}")
        return True
    except Exception as e:
        print(f"✗ Error deleting session: {e}")
        return False


def create_fresh_session(discord_id: str, user_id: str, email: str):
    """Create a fresh onboarding session via API."""
    try:
        url = f"{BACKEND_URL}/api/webhooks/onboarding/start"
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Token': JWT_SECRET
        }
        data = {
            'user_id': user_id,
            'discord_id': discord_id,
            'email': email
        }
        
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Created fresh session:")
        print(f"  - Session ID: {result['session_id']}")
        print(f"  - User ID: {result['user_id']}")
        print(f"  - Discord ID: {result['discord_id']}")
        print(f"  - Current State: {result['current_state']}")
        print(f"  - DM Sent: {result['dm_sent']}")
        return True
    except Exception as e:
        print(f"✗ Error creating session: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False


def main():
    discord_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DISCORD_ID
    user_id = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_USER_ID
    email = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_EMAIL
    
    print(f"\n🔄 Resetting onboarding session for Discord ID: {discord_id}\n")
    
    # Step 1: Delete existing session
    if not delete_existing_session(discord_id):
        print("\n❌ Failed to delete existing session")
        sys.exit(1)
    
    # Step 2: Create fresh session
    if not create_fresh_session(discord_id, user_id, email):
        print("\n❌ Failed to create fresh session")
        sys.exit(1)
    
    print("\n✅ Onboarding session reset complete!")
    print("\nYou can now message the bot to start the onboarding flow from the beginning.")


if __name__ == '__main__':
    main()
