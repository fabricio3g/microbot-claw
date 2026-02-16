#!/bin/sh
# Skill: wikipedia_summary - Wikipedia REST API summary (no key)

tool_wikipedia_summary() {
    local json_args="$1"
    local query=""

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        query=$(echo "$json_args" | jsonfilter -e '@.query' 2>/dev/null)
        [ -z "$query" ] && query=$(echo "$json_args" | jsonfilter -e '@.title' 2>/dev/null)
        [ -z "$query" ] && query=$(echo "$json_args" | jsonfilter -e '@.topic' 2>/dev/null)
    else
        [ -n "$json_args" ] && query=$(echo "$json_args" | grep -o '"query"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"query"[[:space:]]*:[[:space:]]*"//;s/"$//')
        [ -z "$query" ] && query=$(echo "$json_args" | grep -o '"title"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"title"[[:space:]]*:[[:space:]]*"//;s/"$//')
    fi

    [ -z "$query" ] && { echo "Error: query or title required (e.g. OpenWrt, Albert Einstein)"; return; }

    # URL-encode: space -> _, then curl will handle
    local slug
    slug=$(echo "$query" | sed 's/ /_/g' | sed 's/+/_/g')
    local url="https://en.wikipedia.org/api/rest_v1/page/summary/${slug}"

    local result
    if command -v curl >/dev/null 2>&1; then
        result=$(curl -k -s -L -m 10 -H "User-Agent: MicroBot/1.0" "$url")
    else
        result=$(wget -q -O - --no-check-certificate -U "MicroBot/1.0" "$url" 2>/dev/null)
    fi

    if [ -z "$result" ]; then
        echo "Error: Could not fetch Wikipedia."
        return
    fi

    local title="" extract=""
    if command -v jsonfilter >/dev/null 2>&1; then
        title=$(echo "$result" | jsonfilter -e '@.title' 2>/dev/null)
        extract=$(echo "$result" | jsonfilter -e '@.extract' 2>/dev/null)
    fi
    if [ -z "$extract" ]; then
        extract=$(echo "$result" | grep -o '"extract"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"extract"[[:space:]]*:[[:space:]]*"//;s/"$//' | head -1)
    fi
    if [ -z "$title" ]; then
        title=$(echo "$result" | grep -o '"title"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"title"[[:space:]]*:[[:space:]]*"//;s/"$//' | head -1)
    fi

    if [ -n "$extract" ]; then
        echo "=== Wikipedia: ${title:-$query} ==="
        echo ""
        echo "$extract"
    else
        echo "No summary found for: $query"
    fi
}
