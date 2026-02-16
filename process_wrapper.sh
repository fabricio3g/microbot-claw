#!/bin/sh
# Wrapper script called by Python bot to process messages using existing shell functions

# Source all the modules
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
[ -z "$SCRIPT_DIR" ] && SCRIPT_DIR="."
cd "$SCRIPT_DIR"

. ./config.sh
. ./llm.sh
. ./tools.sh
. ./memory.sh

# Get message from environment
USER_MESSAGE="$MESSAGE"

# Build system prompt
SYSTEM=$(build_system_prompt)

# Get API key
API_KEY=$(get_api_key)

# Simple message processing (no tools, just chat)
echo "[process] Processing: ${USER_MESSAGE:0:50}..."

# Escape message for JSON
ESCAPED=$(json_escape "$USER_MESSAGE")

# Build request
if [ "$PROVIDER" = "openrouter" ]; then
    # OpenRouter format
    BODY="{\"model\":\"${OPENROUTER_MODEL}\",\"max_tokens\":${MAX_TOKENS},\"messages\":[{\"role\":\"system\",\"content\":\"$(json_escape "$SYSTEM")\"},{\"role\":\"user\",\"content\":\"${ESCAPED}\"}]}"
    URL="$OPENROUTER_URL"
    AUTH="--header=\"Authorization: Bearer ${OPENROUTER_KEY}\""
else
    # Anthropic format
    BODY="{\"model\":\"${MODEL}\",\"max_tokens\":${MAX_TOKENS},\"system\":\"$(json_escape "$SYSTEM")\",\"messages\":[{\"role\":\"user\",\"content\":\"${ESCAPED}\"}]}"
    URL="$ANTHROPIC_URL"
    AUTH="--header=\"x-api-key: ${API_KEY}\""
fi

# Make request using wget
RESPONSE=$(wget -q -O - \
    --header="Content-Type: application/json" \
    $AUTH \
    --header="anthropic-version: 2023-06-01" \
    --no-check-certificate \
    --post-data="$BODY" \
    "$URL" 2>/dev/null)

# Extract response text
if [ "$PROVIDER" = "openrouter" ]; then
    REPLY=$(echo "$RESPONSE" | jsonfilter -e '@.choices[0].message.content' 2>/dev/null)
else
    REPLY=$(echo "$RESPONSE" | jsonfilter -e '@.content[0].text' 2>/dev/null)
fi

# Output response
if [ -n "$REPLY" ]; then
    echo "$REPLY"
else
    echo "Sorry, I couldn't get a response. Error: $RESPONSE"
fi
