#!/bin/sh
# Skill: wifi_scan - Scan WiFi networks (OpenWrt: iw, or iwlist)

tool_wifi_scan() {
    local json_args="$1"
    local iface=""

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$json_args" ]; then
        iface=$(echo "$json_args" | jsonfilter -e '@.interface' 2>/dev/null)
    else
        [ -n "$json_args" ] && iface=$(echo "$json_args" | grep -o '"interface"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"interface"[[:space:]]*:[[:space:]]*"//;s/"$//')
    fi

    echo "=== WiFi scan ==="
    if [ -z "$iface" ]; then
        # Try common OpenWrt interface
        for w in wlan0 wlan1 radio0; do
            [ -d "/sys/class/net/$w" ] && { iface="$w"; break; }
        done
        [ -z "$iface" ] && iface="wlan0"
    fi

    if command -v iw >/dev/null 2>&1; then
        iw dev "$iface" scan 2>/dev/null | awk '
            /^BSS/ { gsub(/^BSS |\(.*$/, ""); mac=$0; ssid=""; rssi="" }
            /SSID:/ { ssid=substr($0, index($0,":")+2); if(ssid=="") ssid="(hidden)" }
            /signal:/ { rssi=$2 }
            /primary channel/ { if(ssid!="" || rssi!="") print rssi " dBm | " ssid " | " mac }
        ' 2>/dev/null | head -30
    elif command -v iwlist >/dev/null 2>&1; then
        iwlist "$iface" scan 2>/dev/null | grep -E "ESSID|Quality|Address" | head -60
    else
        echo "Error: iw or iwlist not available (install wpad or wireless-tools)"
    fi
}
