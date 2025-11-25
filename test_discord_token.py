#!/usr/bin/env python3
"""
Simple script to test if your Discord bot token is valid.
"""

import os
import sys

try:
    import requests
except ImportError:
    print("❌ ERROR: 'requests' module not found.")
    print("   Install it with: pip3 install requests")
    sys.exit(1)

# Read token from .env file
DISCORD_TOKEN = None
try:
    with open('discord-bot/.env', 'r') as f:
        for line in f:
            if line.startswith('DISCORD_TOKEN='):
                DISCORD_TOKEN = line.split('=', 1)[1].strip()
                break
except FileNotFoundError:
    print("❌ ERROR: discord-bot/.env file not found")
    sys.exit(1)

def test_token():
    """Test if the Discord bot token is valid."""
    
    print("=" * 60)
    print("Discord Bot Token Validator")
    print("=" * 60)
    
    if not DISCORD_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN not found in discord-bot/.env")
        return False
    
    print(f"\n📋 Token found in .env file")
    print(f"   Length: {len(DISCORD_TOKEN)} characters")
    print(f"   First 20 chars: {DISCORD_TOKEN[:20]}...")
    print(f"   Last 10 chars: ...{DISCORD_TOKEN[-10:]}")
    
    # Check token format
    if not DISCORD_TOKEN.startswith('MT'):
        print("\n⚠️  WARNING: Token doesn't start with 'MT' (unusual for bot tokens)")
    
    if len(DISCORD_TOKEN) < 50:
        print(f"\n⚠️  WARNING: Token seems short ({len(DISCORD_TOKEN)} chars). Bot tokens are usually 70+ characters")
    
    # Test the token with Discord API
    print("\n🔍 Testing token with Discord API...")
    
    headers = {
        'Authorization': f'Bot {DISCORD_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            'https://discord.com/api/v10/users/@me',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ SUCCESS! Token is valid!")
            print(f"\n🤖 Bot Information:")
            print(f"   Name: {data.get('username')}#{data.get('discriminator')}")
            print(f"   ID: {data.get('id')}")
            print(f"   Bot: {data.get('bot', False)}")
            
            if data.get('verified'):
                print(f"   Verified: ✅")
            
            print("\n✨ Your bot is ready to use!")
            return True
            
        elif response.status_code == 401:
            print("\n❌ INVALID TOKEN!")
            print("\nThe token was rejected by Discord (401 Unauthorized)")
            print("\nPossible reasons:")
            print("  1. Token was regenerated and you're using an old one")
            print("  2. Token was copied incorrectly (extra spaces, missing characters)")
            print("  3. You copied the Client Secret instead of the Bot Token")
            print("\nHow to fix:")
            print("  1. Go to: https://discord.com/developers/applications/1441388791196680332/bot")
            print("  2. Click 'Reset Token' button")
            print("  3. Copy the ENTIRE token (it's shown only once!)")
            print("  4. Paste it in discord-bot/.env as: DISCORD_TOKEN=your_token_here")
            print("  5. Run this script again to verify")
            return False
            
        else:
            print(f"\n❌ Unexpected response: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out. Check your internet connection.")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Network error: {e}")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


if __name__ == '__main__':
    success = test_token()
    sys.exit(0 if success else 1)
