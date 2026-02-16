#!/bin/sh
# MicroBot AI - LLM API (Anthropic & OpenRouter)
# Do NOT source config.sh here - it's sourced by main script

ANTHROPIC_URL="https://api.anthropic.com/v1/messages"
OPENROUTER_URL="https://openrouter.ai/api/v1/chat/completions"

# HTTP request helper
# HTTP request helper
http_post() {
    local url="$1"
    local data="$2"
    
    # Use curl if available (preferred)
    if command -v curl >/dev/null 2>&1; then
        if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
            curl -k -s -x "http://${PROXY_HOST}:${PROXY_PORT}" \
                -H "Content-Type: application/json" \
                -H "x-api-key: ${API_KEY}" \
                -H "anthropic-version: 2023-06-01" \
                -d "$data" \
                "$url"
        else
            curl -k -s \
                -H "Content-Type: application/json" \
                -H "x-api-key: ${API_KEY}" \
                -H "anthropic-version: 2023-06-01" \
                -d "$data" \
                "$url"
        fi
    else
        # Fallback to wget (BusyBox wget usually fails with headers)
        # We try best effort with whatever flags might work or fail
        if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
            wget -q -O - \
                -e "http_proxy=http://${PROXY_HOST}:${PROXY_PORT}" \
                -e "https_proxy=http://${PROXY_HOST}:${PROXY_PORT}" \
                --header="Content-Type: application/json" \
                --header="x-api-key: ${API_KEY}" \
                --header="anthropic-version: 2023-06-01" \
                --no-check-certificate \
                --post-data="$data" \
                "$url" 2>/dev/null
        else
            wget -q -O - \
                --header="Content-Type: application/json" \
                --header="x-api-key: ${API_KEY}" \
                --header="anthropic-version: 2023-06-01" \
                --no-check-certificate \
                --post-data="$data" \
                "$url" 2>/dev/null
        fi
    fi
}

# HTTP request for OpenRouter
http_post_or() {
    local url="$1"
    local data="$2"
    
    if command -v curl >/dev/null 2>&1; then
        if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
            curl -k -s -x "http://${PROXY_HOST}:${PROXY_PORT}" \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer ${OPENROUTER_KEY}" \
                -H "HTTP-Referer: https://microbot-ai" \
                -H "X-Title: MicroBot AI" \
                -d "$data" \
                "$url"
        else
             curl -k -s \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer ${OPENROUTER_KEY}" \
                -H "HTTP-Referer: https://microbot-ai" \
                -H "X-Title: MicroBot AI" \
                -d "$data" \
                "$url"
        fi
    else
        if [ -n "$PROXY_HOST" ] && [ -n "$PROXY_PORT" ]; then
            wget -q -O - \
                -e "http_proxy=http://${PROXY_HOST}:${PROXY_PORT}" \
                -e "https_proxy=http://${PROXY_HOST}:${PROXY_PORT}" \
                --header="Content-Type: application/json" \
                --header="Authorization: Bearer ${OPENROUTER_KEY}" \
                --header="HTTP-Referer: https://microbot-ai" \
                --header="X-Title: MicroBot AI" \
                --no-check-certificate \
                --post-data="$data" \
                "$url" 2>/dev/null
        else
            wget -q -O - \
                --header="Content-Type: application/json" \
                --header="Authorization: Bearer ${OPENROUTER_KEY}" \
                --header="HTTP-Referer: https://microbot-ai" \
                --header="X-Title: MicroBot AI" \
                --no-check-certificate \
                --post-data="$data" \
                "$url" 2>/dev/null
        fi
    fi
}

# Build Anthropic request
llm_anthropic() {
    local system="$1"
    local messages="$2"
    local tools="$3"
    
    local escaped_system=$(json_escape "$system")
    local body="{\"model\":\"${MODEL}\",\"max_tokens\":${MAX_TOKENS},\"system\":\"${escaped_system}\",\"messages\":${messages}"
    
    # If tools provided and native tools enabled, add to body
    if [ -n "$tools" ] && [ "$USE_NATIVE_TOOLS" = "true" ]; then
        body="${body},\"tools\":${tools}"
    fi
    
    body="${body}}"
    
    http_post "$ANTHROPIC_URL" "$body"
}

# Build OpenRouter request
llm_openrouter() {
    local system="$1"
    local messages="$2"
    local tools="$3"
    
    local escaped_system=$(json_escape "$system")
    
    # Strip outer brackets from messages array since we are inserting it into another array
    # Handle optional spaces
    local inner_messages=$(echo "$messages" | sed 's/^ *\[//; s/\] *$//')
    
    local body="{\"model\":\"${OPENROUTER_MODEL}\",\"max_tokens\":${MAX_TOKENS},\"messages\":[{\"role\":\"system\",\"content\":\"${escaped_system}\"},${inner_messages}]"
    
    # If tools provided and native tools enabled, add to body
    if [ -n "$tools" ] && [ "$USE_NATIVE_TOOLS" = "true" ]; then
        body="${body},\"tools\":${tools}"
    fi
    
    body="${body}}"
    
    # DEBUG: Log request body
    echo "[agent] LLM REQUEST: $body" >&2
    
    http_post_or "$OPENROUTER_URL" "$body"
}

# Main chat function
llm_chat() {
    local system="$1"
    local messages="$2"
    local tools="$3"
    
    if [ "$PROVIDER" = "openrouter" ]; then
        llm_openrouter "$system" "$messages" "$tools"
    else
        llm_anthropic "$system" "$messages" "$tools"
    fi
}

# Parse response - extract text
llm_get_text() {
    local resp="$1"
    
    if [ "$PROVIDER" = "openrouter" ]; then
        echo "$resp" | jsonfilter -e '@.choices[0].message.content' 2>/dev/null
    else
        local text=""
        local count=$(echo "$resp" | jsonfilter -e '@.content[*].type' 2>/dev/null | wc -l)
        local i=0
        while [ $i -lt $count ]; do
            local block_type=$(echo "$resp" | jsonfilter -e "@.content[$i].type" 2>/dev/null)
            if [ "$block_type" = "text" ]; then
                local block_text=$(echo "$resp" | jsonfilter -e "@.content[$i].text" 2>/dev/null)
                text="${text}${block_text}"
            fi
            i=$((i + 1))
        done
        echo "$text"
    fi
}

# Check if tool use
llm_is_tool_use() {
    local resp="$1"
    
    # Check for native tool use first
    if [ "$USE_NATIVE_TOOLS" = "true" ]; then
        if [ "$PROVIDER" = "openrouter" ]; then
            local finish=$(echo "$resp" | jsonfilter -e '@.choices[0].finish_reason' 2>/dev/null)
            [ "$finish" = "tool_calls" ]
            return $?
        else
            local stop=$(echo "$resp" | jsonfilter -e '@.stop_reason' 2>/dev/null)
            [ "$stop" = "tool_use" ]
            return $?
        fi
    else
        # Simulated tool use: Look for "TOOL:name:args" pattern in content
        local content=$(llm_get_text "$resp")
        echo "$content" | grep -q "^TOOL:"
        return $?
    fi
}

# Get tool calls - returns one per line: TOOL:id:name:args_json
llm_get_tool_calls() {
    local resp="$1"
    
    if [ "$USE_NATIVE_TOOLS" = "true" ]; then
        if [ "$PROVIDER" = "openrouter" ]; then
            local count=$(echo "$resp" | jsonfilter -e '@.choices[0].message.tool_calls[*].id' 2>/dev/null | wc -l)
            local i=0
            while [ $i -lt $count ]; do
                local id=$(echo "$resp" | jsonfilter -e "@.choices[0].message.tool_calls[$i].id" 2>/dev/null)
                local name=$(echo "$resp" | jsonfilter -e "@.choices[0].message.tool_calls[$i].function.name" 2>/dev/null)
                local args=$(echo "$resp" | jsonfilter -e "@.choices[0].message.tool_calls[$i].function.arguments" 2>/dev/null)
                if [ -n "$name" ]; then
                    echo "TOOL:${id}:${name}:${args}"
                fi
                i=$((i + 1))
            done
        else
            local count=$(echo "$resp" | jsonfilter -e '@.content[*].type' 2>/dev/null | wc -l)
            local i=0
            while [ $i -lt $count ]; do
                local block_type=$(echo "$resp" | jsonfilter -e "@.content[$i].type" 2>/dev/null)
                if [ "$block_type" = "tool_use" ]; then
                    local id=$(echo "$resp" | jsonfilter -e "@.content[$i].id" 2>/dev/null)
                    local name=$(echo "$resp" | jsonfilter -e "@.content[$i].name" 2>/dev/null)
                    local args=$(echo "$resp" | jsonfilter -e "@.content[$i].input" 2>/dev/null)
                    if [ -n "$name" ]; then
                        echo "TOOL:${id}:${name}:${args}"
                    fi
                fi
                i=$((i + 1))
            done
        fi
    else
        # Simulated tool calls parsing
        # Expecting: TOOL:name:args
        # We start looking from the beginning of the line
        local content=$(llm_get_text "$resp")
        
        # We need to extract lines starting with TOOL:
        # And ensure we capture multiple if present (though prompt says one per msg usually)
        echo "$content" | grep "^TOOL:" | while IFS=':' read -r tag name args; do
             # Generate a fake ID
             local id="call_$(date +%s)_$RANDOM"
             echo "TOOL:${id}:${name}:${args}"
        done
    fi
}

