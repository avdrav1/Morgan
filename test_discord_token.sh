#!/bin/bash
# Simple script to test if your Discord bot token is valid

echo "============================================================"
echo "Discord Bot Token Validator"
echo "============================================================"

# Read token from .env file
if [ ! -f "discord-bot/.env" ]; then
    echo "❌ ERROR: discord-bot/.env file not found"
    exit 1
fi

DISCORD_TOKEN=$(grep "^DISCORD_TOKEN=" discord-bot/.env | cut -d'=' -f2)

if [ -z "$DISCORD_TOKEN" ]; then
    echo "❌ ERROR: DISCORD_TOKEN not found in discord-bot/.env"
    exit 1
fi

echo ""
echo "📋 Token found in .env file"
echo "   Length: ${#DISCORD_TOKEN} characters"
echo "   First 20 chars: ${DISCORD_TOKEN:0:20}..."
echo "   Last 10 chars: ...${DISCORD_TOKEN: -10}"

# Check token format
if [[ ! "$DISCORD_TOKEN" =~ ^MT ]]; then
    echo ""
    echo "⚠️  WARNING: Token doesn't start with 'MT' (unusual for bot tokens)"
fi

if [ ${#DISCORD_TOKEN} -lt 50 ]; then
    echo ""
    echo "⚠️  WARNING: Token seems short (${#DISCORD_TOKEN} chars). Bot tokens are usually 70+ characters"
fi

# Test the token with Discord API
echo ""
echo "🔍 Testing token with Discord API..."
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bot $DISCORD_TOKEN" \
    -H "Content-Type: application/json" \
    https://discord.com/api/v10/users/@me)

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ SUCCESS! Token is valid!"
    echo ""
    echo "🤖 Bot Information:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    echo ""
    echo "✨ Your bot is ready to use!"
    echo ""
    echo "Next steps:"
    echo "  1. Restart the Discord bot: docker-compose restart discord-bot"
    echo "  2. Check logs: docker-compose logs discord-bot --tail=20"
    echo "  3. You should see 'Bot is ready!' message"
    exit 0
    
elif [ "$HTTP_CODE" = "401" ]; then
    echo "❌ INVALID TOKEN!"
    echo ""
    echo "The token was rejected by Discord (401 Unauthorized)"
    echo ""
    echo "Possible reasons:"
    echo "  1. Token was regenerated and you're using an old one"
    echo "  2. Token was copied incorrectly (extra spaces, missing characters)"
    echo "  3. You copied the Client Secret instead of the Bot Token"
    echo ""
    echo "How to fix:"
    echo "  1. Go to: https://discord.com/developers/applications/1441388791196680332/bot"
    echo "  2. Click 'Reset Token' button"
    echo "  3. Copy the ENTIRE token (it's shown only once!)"
    echo "  4. Edit discord-bot/.env and replace DISCORD_TOKEN value"
    echo "  5. Run this script again: bash test_discord_token.sh"
    exit 1
    
else
    echo "❌ Unexpected response: HTTP $HTTP_CODE"
    echo ""
    echo "Response body:"
    echo "$BODY"
    exit 1
fi
