#!/bin/sh
# Run MicroBot in the background with a PID file.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Match config.sh data dir logic
if [ -d "/data" ]; then
    DATA_DIR="/data"
else
    DATA_DIR="${SCRIPT_DIR}/data"
fi

PID_FILE="${DATA_DIR}/microbot.pid"
LOG_FILE="${DATA_DIR}/microbot.log"

mkdir -p "$DATA_DIR"

if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "MicroBot already running (PID $pid)"
        exit 0
    fi
fi

nohup micropython "${SCRIPT_DIR}/microbot.py" >> "$LOG_FILE" 2>&1 &
pid="$!"
echo "$pid" > "$PID_FILE"

echo "MicroBot started in background (PID $pid)"
echo "Log: $LOG_FILE"
