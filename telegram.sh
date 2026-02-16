#!/bin/sh
# MicroBot AI - Telegram Bot API

# Do not source config.sh here - it's sourced by main script
# This file provides telegram functions

TG_API="https://api.telegram.org/bot"
UPDATE_OFFSET=0

# Send HTTP request
tg_request() {
    local method="$1"
    local data="$2"
    
    if [ -z "$TG_TOKEN" ]; then
        echo "ERROR: TG_TOKEN not set"
        return 1
    fi
    
    local url="${TG_API}${TG_TOKEN}/${method}"
    
    if command -v curl >/dev/null 2>&1; then
        if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
            curl -k -s --connect-timeout 5 -m 10 -x "http://${PROXY_HOST}:${PROXY_PORT}" \
                -H "Content-Type: application/json" \
                -d "$data" \
                "$url"
        else
            curl -k -s --connect-timeout 5 -m 10 \
                -H "Content-Type: application/json" \
                -d "$data" \
                "$url"
        fi
    else
        if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
            wget -q -O - \
                -e "http_proxy=http://${PROXY_HOST}:${PROXY_PORT}" \
                -e "https_proxy=http://${PROXY_HOST}:${PROXY_PORT}" \
                --header="Content-Type: application/json" \
                --post-data="$data" \
                "$url" 2>/dev/null
        else
            wget -q -O - \
                --header="Content-Type: application/json" \
                --post-data="$data" \
                --no-check-certificate \
                "$url" 2>/dev/null
        fi
    fi
}

# Get updates
tg_get_updates() {
    local data="{\"offset\":${UPDATE_OFFSET},\"timeout\":30,\"allowed_updates\":[\"message\"]}"
    local resp=$(tg_request "getUpdates" "$data")

    # DEBUG: Show response for troubleshooting
    # echo "$resp" > /tmp/tg_debug.txt

    # Check for valid response
    if [ -z "$resp" ]; then
        return
    fi

    if ! echo "$resp" | grep -q '"ok":true'; then
        echo "[telegram] API error: $resp"
        return
    fi

    # Check if result array is empty []
    if echo "$resp" | grep -q '"result":\[\]'; then
        return
    fi

    # Try to extract the first result's update_id
    local first_update=$(echo "$resp" | jsonfilter -e '@.result[0].update_id' 2>/dev/null)

    # If no update_id, return
    if [ -z "$first_update" ]; then
        return
    fi

    # Extract message fields
    local chat_id=$(echo "$resp" | jsonfilter -e "@.result[0].message.chat.id" 2>/dev/null)
    local text=$(echo "$resp" | jsonfilter -e "@.result[0].message.text" 2>/dev/null)
    local username=$(echo "$resp" | jsonfilter -e "@.result[0].message.from.username" 2>/dev/null)

    # Update offset to acknowledge this message
    UPDATE_OFFSET=$((first_update + 1))

    # Only output if we have both chat_id and text
    if [ -n "$chat_id" ] && [ -n "$text" ]; then
        echo "MSG:${chat_id}:${username}:${text}"
    fi
}

# Send message
tg_send_message() {
    local chat_id="$1"
    local text="$2"
    
    # Escape text for JSON
    local escaped_text=$(echo "$text" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
    
    local data="{\"chat_id\":${chat_id},\"text\":\"${escaped_text}\",\"parse_mode\":\"Markdown\"}"
    local resp=$(tg_request "sendMessage" "$data")
    
    # Retry without markdown if failed
    if [ -z "$resp" ] || ! echo "$resp" | grep -q '"ok":true'; then
        data="{\"chat_id\":${chat_id},\"text\":\"${escaped_text}\"}"
        tg_request "sendMessage" "$data"
    fi
}

# Send typing action
tg_send_action() {
    local chat_id="$1"
    local action="${2:-typing}"
    local data="{\"chat_id\":${chat_id},\"action\":\"${action}\"}"
    tg_request "sendChatAction" "$data"
}
