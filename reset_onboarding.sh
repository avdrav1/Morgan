#!/bin/bash
# Script to reset and create a fresh onboarding session for testing
# Usage: ./reset_onboarding.sh [discord_id] [user_id] [email]

# Default values
DISCORD_ID="${1:-353988409917833217}"
USER_ID="${2:-f6e77b09-17e9-4243-9646-f4f973aec8c0}"
EMAIL="${3:-avdrav@gmail.com}"

# Load JWT secret from backend/.env
JWT_SECRET=$(grep "JWT_SECRET_KEY" backend/.env | cut -d'=' -f2)

echo ""
echo "🔄 Resetting onboarding session for Discord ID: $DISCORD_ID"
echo ""

# Step 1: Delete existing session from database
echo "Step 1: Deleting existing session..."
docker exec accountability-backend psql postgresql://accountability:accountability_dev@postgres:5432/accountability_db -c "DELETE FROM onboarding_sessions WHERE discord_id = '$DISCORD_ID';" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Deleted existing session(s)"
else
    echo "✗ Error deleting session"
    exit 1
fi

# Step 2: Create fresh session via API
echo ""
echo "Step 2: Creating fresh session..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/webhooks/onboarding/start \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $JWT_SECRET" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"discord_id\": \"$DISCORD_ID\",
    \"email\": \"$EMAIL\"
  }")

if [ $? -eq 0 ]; then
    echo "✓ Created fresh session"
    echo ""
    echo "Response:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    echo "✗ Error creating session"
    exit 1
fi

echo ""
echo "✅ Onboarding session reset complete!"
echo ""
echo "You can now message the bot to start the onboarding flow from the beginning."
echo ""
