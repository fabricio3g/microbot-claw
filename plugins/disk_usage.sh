#!/bin/sh
# Skill: disk_usage - Show disk usage

tool_disk_usage() {
    local json_args="$1"
    local path=""

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        path=$(echo "$json_args" | jsonfilter -e '@.path' 2>/dev/null)
    else
        [ -n "$json_args" ] && path=$(echo "$json_args" | grep -o '"path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"path"[[:space:]]*:[[:space:]]*"//;s/"$//')
    fi

    echo "=== Disk usage ==="
    if [ -n "$path" ]; then
        df -h "$path" 2>/dev/null || df -h 2>/dev/null | head -1; df -h 2>/dev/null | grep -F "$path" || true
    else
        df -h 2>/dev/null || df 2>/dev/null
    fi
}
