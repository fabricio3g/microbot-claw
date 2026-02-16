#!/bin/sh
# Skill: log_tail - Last N lines of a log file

tool_log_tail() {
    local json_args="$1"
    local path="" lines="20"

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        path=$(echo "$json_args" | jsonfilter -e '@.path' 2>/dev/null)
        lines=$(echo "$json_args" | jsonfilter -e '@.lines' 2>/dev/null)
    else
        [ -n "$json_args" ] && {
            path=$(echo "$json_args" | grep -o '"path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"path"[[:space:]]*:[[:space:]]*"//;s/"$//')
            lines=$(echo "$json_args" | grep -o '"lines"[[:space:]]*:[[:space:]]*[0-9]*' | sed 's/.*:[[:space:]]*//')
        }
    fi

    [ -z "$path" ] && { echo "Error: path required (e.g. /var/log/messages)"; return; }
    [ -z "$lines" ] && lines=20

    # Limit lines for safety
    [ "$lines" -gt 100 ] 2>/dev/null && lines=100

    echo "=== Last ${lines} lines of $path ==="
    if [ -f "$path" ] && [ -r "$path" ]; then
        tail -n "$lines" "$path" 2>/dev/null || echo "Error: could not read file"
    else
        # OpenWrt: logread as fallback if path is "syslog" or "log"
        case "$path" in
            syslog|log|logread)
                command -v logread >/dev/null 2>&1 && logread | tail -n "$lines" || echo "Error: logread not available"
                ;;
            *)
                echo "Error: file not found or not readable: $path"
                ;;
        esac
    fi
}
