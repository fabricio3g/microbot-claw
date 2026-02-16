#!/bin/sh
# Skill: ping_host - Ping a host and return latency summary

tool_ping_host() {
    local json_args="$1"
    local host="" count="3"

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        host=$(echo "$json_args" | jsonfilter -e '@.host' 2>/dev/null)
        count=$(echo "$json_args" | jsonfilter -e '@.count' 2>/dev/null)
    else
        [ -n "$json_args" ] && host=$(echo "$json_args" | grep -o '"host"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"host"[[:space:]]*:[[:space:]]*"//;s/"$//')
    fi

    [ -z "$host" ] && { echo "Error: host required (e.g. 8.8.8.8 or google.com)"; return; }
    [ -z "$count" ] && count=3

    if ! command -v ping >/dev/null 2>&1; then
        echo "Error: ping not available"
        return
    fi

    echo "=== Ping $host (${count} packets) ==="
    ping -c "$count" -W 3 "$host" 2>&1 || true
}
