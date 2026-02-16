#!/bin/sh
# Skill: dns_lookup - Resolve hostname to IP

tool_dns_lookup() {
    local json_args="$1"
    local host=""

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        host=$(echo "$json_args" | jsonfilter -e '@.host' 2>/dev/null)
    else
        [ -n "$json_args" ] && host=$(echo "$json_args" | grep -o '"host"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"host"[[:space:]]*:[[:space:]]*"//;s/"$//')
    fi

    [ -z "$host" ] && { echo "Error: host required (e.g. google.com)"; return; }

    echo "=== DNS lookup: $host ==="
    if command -v nslookup >/dev/null 2>&1; then
        nslookup "$host" 2>&1
    elif command -v getent >/dev/null 2>&1; then
        getent hosts "$host" 2>&1
    elif command -v host >/dev/null 2>&1; then
        host "$host" 2>&1
    else
        echo "Error: no DNS tool (nslookup/getent/host) available"
    fi
}
