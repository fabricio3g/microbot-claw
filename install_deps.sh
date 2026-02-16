#!/bin/sh
# Install curl, micropython, and scp server on OpenWrt.

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

echo "[1/2] Updating package lists..."
opkg update

echo "[2/2] Installing packages..."

if ! command -v curl >/dev/null 2>&1; then
    opkg install curl
fi

if ! command -v micropython >/dev/null 2>&1; then
    opkg install micropython
fi

# scp server is provided by openssh-server
if ! command -v sshd >/dev/null 2>&1; then
    opkg install openssh-server
fi

# Enable/start sshd if available
if [ -x /etc/init.d/sshd ]; then
    /etc/init.d/sshd enable
    /etc/init.d/sshd start
fi

echo "Dependencies installed."
