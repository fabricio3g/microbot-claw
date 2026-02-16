#!/bin/sh
# Skill: hacker_news_top - Hacker News Firebase API (no key)

tool_hacker_news_top() {
    local json_args="$1"
    local limit=5

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        limit=$(echo "$json_args" | jsonfilter -e '@.limit' 2>/dev/null)
    else
        [ -n "$json_args" ] && limit=$(echo "$json_args" | grep -o '"limit"[[:space:]]*:[[:space:]]*[0-9]*' | sed 's/.*:[[:space:]]*//')
    fi

    [ -z "$limit" ] && limit=5
    [ "$limit" -gt 20 ] 2>/dev/null && limit=20
    [ "$limit" -lt 1 ] 2>/dev/null && limit=5

    local ids
    ids=$(curl -k -s -m 10 "https://hacker-news.firebaseio.com/v0/topstories.json" 2>/dev/null)
    [ -z "$ids" ] && { echo "Error: Could not fetch Hacker News."; return; }

    # Get first N ids (array like [1,2,3,...])
    local count=0
    echo "=== Hacker News Top $limit ==="
    echo ""

    for id in $(echo "$ids" | sed 's/\[//;s/\]//;s/,/ /g'); do
        [ "$count" -ge "$limit" ] && break
        id=$(echo "$id" | tr -d ' ')
        [ -z "$id" ] && continue

        local item
        item=$(curl -k -s -m 5 "https://hacker-news.firebaseio.com/v0/item/${id}.json" 2>/dev/null)
        [ -z "$item" ] && continue

        local title="" url=""
        if command -v jsonfilter >/dev/null 2>&1; then
            title=$(echo "$item" | jsonfilter -e '@.title' 2>/dev/null)
            url=$(echo "$item" | jsonfilter -e '@.url' 2>/dev/null)
        else
            title=$(echo "$item" | grep -o '"title"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"title"[[:space:]]*:[[:space:]]*"//;s/"$//')
            url=$(echo "$item" | grep -o '"url"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"url"[[:space:]]*:[[:space:]]*"//;s/"$//')
        fi

        [ -n "$title" ] && {
            count=$((count + 1))
            if [ -n "$url" ]; then
                echo "${count}. ${title}"
                echo "   ${url}"
            else
                echo "${count}. ${title} (no link)"
            fi
            echo ""
        }
    done
}
