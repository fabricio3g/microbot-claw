#!/bin/sh
# Skill: router_capabilities - OpenWrt modem/router capability snapshot

tool_router_capabilities() {
    local json_args="$1"
    local detail="short"
    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        local d
        d=$(echo "$json_args" | jsonfilter -e '@.detail' 2>/dev/null)
        [ -n "$d" ] && detail="$d"
    fi

    echo "=== Router / Modem Capabilities ==="
    echo ""

    echo "-- Board --"
    if command -v ubus >/dev/null 2>&1 && command -v jsonfilter >/dev/null 2>&1; then
        local board_json model target release
        board_json=$(ubus call system board 2>/dev/null)
        model=$(echo "$board_json" | jsonfilter -e '@.model' 2>/dev/null)
        target=$(echo "$board_json" | jsonfilter -e '@.release.target' 2>/dev/null)
        release=$(echo "$board_json" | jsonfilter -e '@.release.description' 2>/dev/null)
        [ -n "$model" ] && echo "Model: $model"
        [ -n "$target" ] && echo "Target: $target"
        [ -n "$release" ] && echo "OpenWrt: $release"
    else
        uname -a
    fi
    echo ""

    echo "-- Memory --"
    free -m 2>/dev/null || cat /proc/meminfo | head -8
    echo ""

    echo "-- Disk --"
    df -h | grep -E 'Filesystem|overlay|/tmp|/mnt|/dev/root'
    echo ""

    echo "-- Network --"
    ip -4 addr show 2>/dev/null | grep -E '^[0-9]+: |inet ' | head -20
    ip route show 2>/dev/null | head -10
    echo ""

    echo "-- WiFi --"
    if command -v iwinfo >/dev/null 2>&1; then
        iwinfo 2>/dev/null | head -40
    elif command -v wifi >/dev/null 2>&1; then
        wifi status 2>/dev/null | head -60
    else
        echo "No iwinfo/wifi command found"
    fi
    echo ""

    echo "-- MicroPython --"
    if command -v micropython >/dev/null 2>&1; then
        echo "micropython: $(which micropython)"
        micropython -h 2>&1 | head -1
    else
        echo "micropython: missing"
    fi
    echo ""

    echo "-- Cron --"
    /etc/init.d/cron status 2>/dev/null || true
    ps w | grep crond | grep -v grep || true
    [ -d /etc/crontabs ] && ls -la /etc/crontabs 2>/dev/null
    echo ""

    echo "-- AgentWRT Services --"
    /etc/init.d/agentwrt status 2>/dev/null || true
    /etc/init.d/agentwrt-ui status 2>/dev/null || true
    ps w | grep -E 'agentwrt.py|ui_server.py' | grep -v grep || true
    echo ""

    echo "-- Internal Tools --"
    for c in uci ubus jsonfilter curl wget opkg logread nft ip iw iwinfo wifi ifstatus service netstat free df awk sed grep tar gzip; do
        command -v "$c" >/dev/null 2>&1 && printf '%s ' "$c"
    done
    echo ""

    if [ "$detail" = "full" ]; then
        echo ""
        echo "-- Open Ports --"
        netstat -lntup 2>/dev/null || true
        echo ""
        echo "-- UBUS Objects --"
        ubus list 2>/dev/null | head -80 || true
    fi
}
