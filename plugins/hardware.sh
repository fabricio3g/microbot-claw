#!/bin/sh
# MicroBot Plugin: Hardware Monitoring
# Inspired by MimiClaw status sensors

tool_get_sys_health() {
    echo "--- System Health ---"
    
    # CPU Temp
    local temp=""
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        temp=$(cat /sys/class/thermal/thermal_zone0/temp)
    elif [ -f /sys/class/hwmon/hwmon0/temp1_input ]; then
        temp=$(cat /sys/class/hwmon/hwmon0/temp1_input)
    fi
    [ -n "$temp" ] && echo "CPU Temp: $((temp/1000))°C"
    
    # Load Average
    echo "Load: $(cat /proc/loadavg | awk '{print $1 ", " $2 ", " $3}')"
    
    # Memory usage (more robust for BusyBox)
    local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local mem_free=$(grep MemFree /proc/meminfo | awk '{print $2}')
    local mem_avail=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
    [ -z "$mem_avail" ] && mem_avail=$mem_free
    
    echo "RAM: Total $((mem_total/1024))MB | Avail $((mem_avail/1024))MB"
    
    # Disk usage (focus on root and overlay)
    echo "Disk Usage:"
    df -h | grep -E '^/dev/|^overlay|^tmpfs' | awk '{printf "  %s: %s/%s (%s)\n", $6, $3, $2, $5}'
    
    # Uptime
    local up_sec=$(cut -d. -f1 /proc/uptime)
    echo "Uptime: $((up_sec/3600))h $(((up_sec%3600)/60))m"
}

tool_get_wifi_status() {
    echo "--- Wi-Fi Status ---"
    
    # Find active interfaces
    for iface in $(iw dev | grep Interface | awk '{print $2}'); do
        echo "Interface: $iface"
        # Get signal strength if connected
        iw dev "$iface" link 2>/dev/null | grep -E "SSID|signal|tx bitrate"
        # Count connected clients if in AP mode
        local clients=$(iw dev "$iface" station dump 2>/dev/null | grep Station | wc -l)
        if [ "$clients" -gt 0 ]; then
            echo "Connected Clients: $clients"
        fi
    done
}
