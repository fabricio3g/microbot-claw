#!/bin/sh
# Skill: world_time - World Time API (no key): by timezone or by IP

tool_world_time() {
    local json_args="$1"
    local timezone=""
    local use_ip=""

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        timezone=$(echo "$json_args" | jsonfilter -e '@.timezone' 2>/dev/null)
        use_ip=$(echo "$json_args" | jsonfilter -e '@.ip' 2>/dev/null)
    else
        [ -n "$json_args" ] && {
            timezone=$(echo "$json_args" | grep -o '"timezone"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"timezone"[[:space:]]*:[[:space:]]*"//;s/"$//')
            use_ip=$(echo "$json_args" | grep -o '"ip"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"ip"[[:space:]]*:[[:space:]]*"//;s/"$//')
        }
    fi

    local url
    if [ -n "$timezone" ]; then
        # Time by timezone: Europe/London, America/New_York (space -> underscore)
        timezone=$(echo "$timezone" | sed 's/ /_/g')
        url="http://worldtimeapi.org/api/timezone/${timezone}"
    else
        # Time by client IP (or explicit ip request)
        url="http://worldtimeapi.org/api/ip"
    fi

    local result
    result=$(curl -k -s -m 10 "$url" 2>/dev/null)
    [ -z "$result" ] && { echo "Error: Could not fetch World Time API."; return; }

    local datetime="" tz="" abbreviation=""
    if command -v jsonfilter >/dev/null 2>&1; then
        datetime=$(echo "$result" | jsonfilter -e '@.datetime' 2>/dev/null)
        tz=$(echo "$result" | jsonfilter -e '@.timezone' 2>/dev/null)
        abbreviation=$(echo "$result" | jsonfilter -e '@.abbreviation' 2>/dev/null)
    fi
    if [ -z "$datetime" ]; then
        datetime=$(echo "$result" | grep -o '"datetime"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"datetime"[[:space:]]*:[[:space:]]*"//;s/"$//')
        tz=$(echo "$result" | grep -o '"timezone"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"timezone"[[:space:]]*:[[:space:]]*"//;s/"$//')
        abbreviation=$(echo "$result" | grep -o '"abbreviation"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"abbreviation"[[:space:]]*:[[:space:]]*"//;s/"$//')
    fi

    echo "=== Current time ==="
    [ -n "$datetime" ] && echo "Date/time: $datetime"
    [ -n "$tz" ] && echo "Timezone: $tz"
    [ -n "$abbreviation" ] && echo "Abbrev: $abbreviation"
}
