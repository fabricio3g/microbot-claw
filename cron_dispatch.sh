#!/bin/sh
# AgentWRT cron dispatch
# Called every minute by system cron (crond).
# Fires simple message-type schedules from data/schedules.txt.
# Complex types (tool, agent, probe, cmd) are left for the Python in-process scheduler.

SCRIPT_DIR="/mnt/usb/agentwrt-ash"
SCHED_FILE="${SCRIPT_DIR}/data/schedules.txt"
STATE_FILE="/tmp/cron_dispatch_state"
CONFIG_FILE="${SCRIPT_DIR}/data/config.json"

[ ! -f "$SCHED_FILE" ] && exit 0

# Read config for tg_token
TG_TOKEN=""
[ -f "$CONFIG_FILE" ] && command -v jsonfilter >/dev/null 2>&1 && \
  TG_TOKEN=$(jsonfilter -i "$CONFIG_FILE" -e '@.tg_token' 2>/dev/null)

[ -z "$TG_TOKEN" ] && exit 0

# Load last-fired timestamps
STATE=""
[ -f "$STATE_FILE" ] && STATE=$(cat "$STATE_FILE")

NOW_MIN=$(date +%M)
NOW_HR=$(date +%H)
NOW_DOM=$(date +%d)
NOW_MON=$(date +%m)
NOW_DOW=$(date +%w)
NOW_KEY="${NOW_HR}:${NOW_MIN}"

# Normalize to integers (strip leading zeros for shell arithmetic)
NOW_MIN=$(echo "$NOW_MIN" | sed 's/^0//')
[ -z "$NOW_MIN" ] && NOW_MIN=0
NOW_HR=$(echo "$NOW_HR" | sed 's/^0//')
[ -z "$NOW_HR" ] && NOW_HR=0
NOW_DOM=$(echo "$NOW_DOM" | sed 's/^0//')
[ -z "$NOW_DOM" ] && NOW_DOM=1
NOW_MON=$(echo "$NOW_MON" | sed 's/^0//')
[ -z "$NOW_MON" ] && NOW_MON=1

# Simple cron matcher
# Supports: *   exact   ,   a-b   */N
matches_cron() {
    local expr="$1"
    local f_min f_hour f_dom f_mon f_dow
    f_min=$(echo "$expr" | cut -d' ' -f1)
    f_hour=$(echo "$expr" | cut -d' ' -f2)
    f_dom=$(echo "$expr" | cut -d' ' -f3)
    f_mon=$(echo "$expr" | cut -d' ' -f4)
    f_dow=$(echo "$expr" | cut -d' ' -f5)

    _match_field() {
        local f="$1" v="$2" is_dow="$3"
        [ "$f" = "*" ] && return 0
        local step=1 base="$f"
        if echo "$f" | grep -q "/"; then
            base="${f%/*}"
            step="${f#*/}"
            [ -z "$step" ] && step=1
        fi
        if [ "$base" = "*" ]; then
            [ $(( v % step )) -eq 0 ] && return 0 || return 1
        fi
        # Comma list
        if echo "$base" | grep -q ","; then
            local p
            for p in $(echo "$base" | tr ',' ' '); do
                _match_field "$p" "$v" "$is_dow" && return 0
            done
            return 1
        fi
        # Range
        local start end
        if echo "$base" | grep -q "-"; then
            start="${base%-*}"
            end="${base#*-}"
        else
            start="$base"
            end="$base"
        fi
        [ "$is_dow" = "1" ] && { [ "$start" = "7" ] && start=0; [ "$end" = "7" ] && end=0; }
        start=$((10#$start)); end=$((10#$end)); v=$((10#$v))
        if [ "$start" -le "$end" ]; then
            [ "$v" -lt "$start" ] 2>/dev/null && return 1
            [ "$v" -gt "$end" ] 2>/dev/null && return 1
            [ $(( (v - start) % step )) -eq 0 ] && return 0 || return 1
        fi
        # Wrap range (e.g. 22-2)
        [ "$v" -ge "$start" ] 2>/dev/null || [ "$v" -le "$end" ] 2>/dev/null || return 1
        return 0
    }

    _match_field "$f_min"  "$NOW_MIN"  0 || return 1
    _match_field "$f_hour" "$NOW_HR"   0 || return 1
    _match_field "$f_dom"  "$NOW_DOM"  0 || return 1
    _match_field "$f_mon"  "$NOW_MON"  0 || return 1
    _match_field "$f_dow"  "$NOW_DOW"  1 || return 1
    return 0
}

# Function to send Telegram message
send_tg() {
    local chat="$1" text="$2"
    text=$(echo "$text" | sed 's/"/\\"/g; s/\\n/\\\\n/g')
    curl -k -s -m 10 \
      -H "Content-Type: application/json" \
      -d "{\"chat_id\":$chat,\"text\":\"$text\",\"parse_mode\":\"\"}" \
      "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" >/dev/null 2>&1
}

NEW_LINES=""
FIRED=""

while IFS= read -r line; do
    [ -z "$line" ] && continue

    sid=$(echo "$line" | cut -d'|' -f1)
    cron=$(echo "$line" | cut -d'|' -f2)
    chat=$(echo "$line" | cut -d'|' -f3)
    stype=$(echo "$line" | cut -d'|' -f4)
    content=$(echo "$line" | cut -d'|' -f5-)
    stype=$(echo "$stype" | tr '[:upper:]' '[:lower:]')

    [ -z "$sid" ] && continue
    [ -z "$cron" ] && { NEW_LINES="${NEW_LINES}${line}\n"; continue; }

    # Only handle message types here
    case "$stype" in
        msg|reminder)
            keep=1
            if matches_cron "$cron"; then
                echo "$STATE" | grep -q "${sid}|${NOW_KEY}" && { NEW_LINES="${NEW_LINES}${line}\n"; continue; }
                send_tg "$chat" "$content"
                FIRED="${FIRED} ${sid}|${NOW_KEY}"
            fi
            NEW_LINES="${NEW_LINES}${line}\n"
            ;;
        once)
            keep=1
            if matches_cron "$cron"; then
                echo "$STATE" | grep -q "${sid}|${NOW_KEY}" && { NEW_LINES="${NEW_LINES}${line}\n"; continue; }
                send_tg "$chat" "$content"
                FIRED="${FIRED} ${sid}|${NOW_KEY}"
                # Don't keep - remove after firing
                keep=0
            fi
            [ "$keep" = 1 ] && NEW_LINES="${NEW_LINES}${line}\n"
            ;;
        *)
            # Non-message types: pass through unchanged, let Python handle them
            NEW_LINES="${NEW_LINES}${line}\n"
            ;;
    esac
done < "$SCHED_FILE"

# Write back (removes fired once-type)
printf "%b" "$NEW_LINES" > "$SCHED_FILE" 2>/dev/null

# Save state
echo "$STATE $FIRED" | tr ' ' '\n' | grep -v '^$' | sort -u > "$STATE_FILE" 2>/dev/null
