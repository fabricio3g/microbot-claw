#!/bin/sh
# Stop background MicroBot using PID file.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -d "/data" ]; then
    DATA_DIR="/data"
else
    DATA_DIR="${SCRIPT_DIR}/data"
fi

PID_FILE="${DATA_DIR}/microbot.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "PID file not found: $PID_FILE"
    exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null)"

if [ -z "$pid" ]; then
    echo "Empty PID file: $PID_FILE"
    rm -f "$PID_FILE"
    exit 0
fi

if ! kill -0 "$pid" 2>/dev/null; then
    echo "Process not running (PID $pid)"
    rm -f "$PID_FILE"
    exit 0
fi

kill "$pid" 2>/dev/null
sleep 1

if kill -0 "$pid" 2>/dev/null; then
    echo "Process still running, sending SIGKILL..."
    kill -9 "$pid" 2>/dev/null
fi

rm -f "$PID_FILE"
echo "MicroBot stopped"
