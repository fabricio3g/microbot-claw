#!/bin/sh
# Skill: get_uptime - System uptime

tool_get_uptime() {
    echo "=== System uptime ==="
    if [ -f /proc/uptime ]; then
        sec=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
        [ -n "$sec" ] && [ "$sec" -ge 0 ] && {
            days=$((sec / 86400))
            hours=$((sec % 86400 / 3600))
            mins=$((sec % 3600 / 60))
            [ "$days" -gt 0 ] && printf "%d day(s) " "$days"
            [ "$hours" -gt 0 ] && printf "%d hour(s) " "$hours"
            printf "%d minute(s)\n" "$mins"
        }
    fi
    uptime 2>/dev/null || true
}
