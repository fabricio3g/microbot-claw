#!/bin/sh
# MicroBot-Claw Uninstaller (OpenWrt)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
[ -z "$SCRIPT_DIR" ] && SCRIPT_DIR="."
INSTALL_DIR="$SCRIPT_DIR"
LEGACY_DIR="/opt/microbot-ash"
LEGACY_DIR2="/opt/microbot-claw"
DATA_DIR="/data"
KEEP_DATA="false"

if [ "$1" = "--keep-data" ]; then
    KEEP_DATA="true"
fi

echo "=========================================="
echo "  MicroBot-Claw - Uninstaller"
echo "=========================================="

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

stop_service() {
    if [ -x "/etc/init.d/$1" ]; then
        /etc/init.d/"$1" stop || true
        /etc/init.d/"$1" disable || true
        rm -f "/etc/init.d/$1" || true
    fi
}

echo "[1/3] Stopping services..."
stop_service microbot-claw
stop_service microbot-claw-ui
stop_service microbot-claw-research
stop_service microbot-claw-matrix
# Legacy service names (old installs)
stop_service microbot-ai
stop_service microbot-ui

echo "[2/3] Removing files..."
cd / || true
rm -rf "$INSTALL_DIR" || true
rm -rf "$LEGACY_DIR" || true
rm -rf "$LEGACY_DIR2" || true

if [ "$KEEP_DATA" = "true" ]; then
    echo "[3/3] Keeping data directory."
else
    echo "[3/3] Removing data..."
    rm -f "$DATA_DIR/config.json" || true
    rm -f "$DATA_DIR/config.json.template" || true
    rm -rf "$DATA_DIR/config" || true
    rm -rf "$DATA_DIR/memory" || true
    rm -rf "$DATA_DIR/sessions" || true
    rm -rf "$DATA_DIR/deepsearch" || true
fi

echo ""
echo "Uninstall complete."
