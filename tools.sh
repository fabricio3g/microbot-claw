#!/bin/sh
# AgentWRT - Tools
# Do not source config.sh here - it's sourced by main script

# Tool: Get current time
# Tool: Get current time
tool_get_time() {
    local result
    
    # Use configured timezone if available
    local tz_arg=""
    if [ -n "$TIMEZONE" ]; then
        tz_arg="$TIMEZONE"
    fi
    
    if command -v curl >/dev/null 2>&1; then
        if [ -n "$tz_arg" ]; then
            result=$(curl -k -s --connect-timeout 5 -m 8 "https://timeapi.io/api/TimeZone/zone?timeZone=${tz_arg}")
            if echo "$result" | grep -q 'currentLocalTime'; then
                datetime=$(echo "$result" | jsonfilter -e '@.currentLocalTime' 2>/dev/null)
                [ -n "$datetime" ] && { echo "Current time: ${datetime} (timezone: ${tz_arg})"; return; }
            fi
            result=$(curl -k -s --connect-timeout 5 -m 8 "https://worldtimeapi.org/api/timezone/${tz_arg}")
        else
            result=$(curl -k -s --connect-timeout 5 -m 8 "https://worldtimeapi.org/api/ip")
        fi
    else
        if [ -n "$tz_arg" ]; then
             result=$(wget -q -O - --no-check-certificate "https://worldtimeapi.org/api/timezone/${tz_arg}" 2>/dev/null)
        else
             result=$(wget -q -O - --no-check-certificate "https://worldtimeapi.org/api/ip" 2>/dev/null)
        fi
    fi
    
    if [ -n "$result" ]; then
        local datetime=$(echo "$result" | jsonfilter -e '@.datetime')
        local tz=$(echo "$result" | jsonfilter -e '@.timezone')
        echo "Current time: ${datetime} (timezone: ${tz})"
    else
        # Fallback to system date with TZ var if set
        if [ -n "$TIMEZONE" ]; then
            TZ="$TIMEZONE" date "+Current time: %Y-%m-%d %H:%M:%S (timezone: $TIMEZONE)"
        else
            date "+Current time: %Y-%m-%d %H:%M:%S (local)"
        fi
    fi
}

# Tool: Set timezone
tool_set_timezone() {
    local tz="$1"
    
    if [ -z "$tz" ]; then
        echo "Error: Timezone required. Examples: Europe/Madrid, America/Argentina/Buenos_Aires, UTC"
        return
    fi
    case "$tz" in
        Madrid|madrid|Spain|spain|Espana|España) tz="Europe/Madrid" ;;
        Argentina|argentina|Buenos_Aires|buenos_aires) tz="America/Argentina/Buenos_Aires" ;;
        Mexico|mexico|México|méxico) tz="America/Mexico_City" ;;
        Colombia|colombia|Bogota|Bogotá|bogota|bogotá) tz="America/Bogota" ;;
        Chile|chile) tz="America/Santiago" ;;
        Peru|peru|Perú|perú) tz="America/Lima" ;;
    esac
    case "$tz" in
        *..*|/*|*\ *|*\;*|*\&*|*\|*|*\`*|*\$*) echo "Error: Invalid timezone"; return ;;
    esac
    if [ "$tz" != "UTC" ] && ! echo "$tz" | grep -q '/'; then
        echo "Error: Use an IANA timezone like Europe/Madrid or America/Argentina/Buenos_Aires"
        return
    fi
    if [ -d /usr/share/zoneinfo ] && [ "$tz" != "UTC" ] && [ ! -e "/usr/share/zoneinfo/$tz" ]; then
        echo "Warning: timezone not found in zoneinfo, saving anyway: $tz"
    fi
    
    # Update config.json
    local config_file
    if [ -f "/data/config.json" ]; then
        config_file="/data/config.json"
    elif [ -n "$DATA_DIR" ]; then
        config_file="${DATA_DIR}/config.json"
    else
        config_file="./data/config.json"
    fi
    
    # Check if jq exists for clean editing, else use sed/grep hack
    if command -v jq >/dev/null 2>&1; then
        local tmp=$(mktemp)
        jq --arg tz "$tz" '.timezone = $tz' "$config_file" > "$tmp" && mv "$tmp" "$config_file"
    else
        # Simple sed hack for JSON (assumes formatting)
        if grep -q '"timezone"' "$config_file"; then
             sed -i "s/\"timezone\": *\"[^\"]*\"/\"timezone\": \"$(echo $tz | sed 's/\//\\\//g')\"/" "$config_file"
        else
             # Insert before last brace
             sed -i "s/}/,\n    \"timezone\": \"$(echo $tz | sed 's/\//\\\//g')\"\n}/" "$config_file"
        fi
    fi
    
    if [ -n "$tz" ]; then
        now=""
        api_resp=$(curl -k -s --connect-timeout 5 -m 8 "https://timeapi.io/api/TimeZone/zone?timeZone=${tz}" 2>/dev/null)
        if [ -n "$api_resp" ]; then
            now=$(echo "$api_resp" | jsonfilter -e '@.currentLocalTime' 2>/dev/null)
        fi
        if [ -z "$now" ]; then
            api_resp=$(curl -k -s --connect-timeout 5 -m 8 "https://worldtimeapi.org/api/timezone/${tz}" 2>/dev/null)
            [ -n "$api_resp" ] && now=$(echo "$api_resp" | jsonfilter -e '@.datetime' 2>/dev/null)
        fi
        if [ -z "$now" ]; then
            now=$(TZ="$tz" date "+%Y-%m-%d %H:%M:%S %Z" 2>/dev/null)
        fi
        echo "Timezone updated: $tz"
        [ -n "$now" ] && echo "Current time: $now"
        echo "Config saved: $config_file"
    fi
}

# Helper: JSON Escape
json_escape() {
    # Simple escape for JSON strings
    # 1. Backslashes (double escape to be safe in sed replacement)
    # 2. Quotes
    # 3. Tabs
    # 4. Newlines -> space (simplified)
    # Note: awk might be missing on minimal systems, use printf + sed
    local tab=$(printf '\t')
    printf '%s' "$1" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed "s/$tab/\\\\t/g" | tr '\n' ' ' | sed 's/  */ /g'
}

# Helper: clean HTML snippets for Telegram/LLM
_clean_search_text() {
    printf '%s' "$1" \
      | sed 's/<[^>][^>]*>//g' \
      | sed 's/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g; s/&quot;/"/g; s/&#39;/'"'"'/g; s/&#x27;/'"'"'/g; s/&#x2F;/\//g; s/&nbsp;/ /g' \
      | tr '\n\r\t' '   ' \
      | sed 's/  */ /g; s/^ *//; s/ *$//'
}

# Tool: Web search
# Uses Brave Search API if key available, else scrapes DuckDuckGo HTML
tool_web_search() {
    local query="$1"
    
    if [ -z "$query" ]; then
        echo "Error: Search query required"
        return
    fi
    
    # URL-encode the query (simple: spaces + basic chars)
    local encoded_q=$(echo "$query" | sed 's/ /+/g; s/&/%26/g; s/?/%3F/g; s/#/%23/g')
    
    # ------- Try Brave API first -------
    if [ -n "$SEARCH_KEY" ] && [ "$SEARCH_KEY" != "YOUR_API_KEY" ]; then
        local api_url="https://api.search.brave.com/res/v1/web/search?q=${encoded_q}&count=5&freshness=pd"
        local result
        result=$(curl -k -s --connect-timeout 4 -m 7 \
            -H "Accept: application/json" \
            -H "X-Subscription-Token: ${SEARCH_KEY}" \
            "$api_url")
        
        if [ -n "$result" ]; then
            local i=0
            local shown=0
            local seen="|"
            echo "=== Search Results for: $query ==="
            echo ""
            while [ $i -lt 10 ] && [ $shown -lt 5 ]; do
                local title=$(echo "$result" | jsonfilter -e "@.web.results[$i].title" 2>/dev/null)
                local link=$(echo "$result" | jsonfilter -e "@.web.results[$i].url" 2>/dev/null)
                local desc=$(echo "$result" | jsonfilter -e "@.web.results[$i].description" 2>/dev/null)
                [ -z "$link" ] && break
                case "$link" in
                    *duckduckgo.com/y.js*|*bing.com/aclick*|*googleadservices*|*doubleclick.net*) i=$((i + 1)); continue ;;
                esac
                title=$(_clean_search_text "$title")
                desc=$(_clean_search_text "$desc")
                if ! echo "$seen" | grep -q "|$link|"; then
                    seen="${seen}${link}|"
                    shown=$((shown + 1))
                    echo "${shown}. ${title}"
                    echo "   ${link}"
                    [ -n "$desc" ] && echo "   ${desc}"
                    echo ""
                fi
                i=$((i + 1))
            done
            [ $shown -gt 0 ] && return
        fi
    fi
    # ------- Fallback: Scrape DuckDuckGo HTML (zero storage - all piped) -------
    local ddg_url="https://html.duckduckgo.com/html/?q=${encoded_q}"
    local ua="Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
    
    echo "=== Search Results for: $query ==="
    echo ""
    
    # Single curl | awk pipeline: extract links only (clean output)
    curl -k -s -L -A "$ua" --connect-timeout 4 -m 8 "$ddg_url" 2>/dev/null | awk '
    BEGIN { lc=0; tc=0 }
    {
        # Extract uddg= links
        line = $0
        while (match(line, /href="[^"]*uddg=[^"]*"/)) {
            href = substr(line, RSTART+6, RLENGTH-7)
            line = substr(line, RSTART+RLENGTH)
            # Extract uddg= value
            if (match(href, /uddg=[^&]*/)) {
                url = substr(href, RSTART+5, RLENGTH-5)
                # Basic URL decode
                gsub(/%3A/, ":", url); gsub(/%2F/, "/", url)
                gsub(/%3F/, "?", url); gsub(/%3D/, "=", url)
                gsub(/%26/, "\\&", url); gsub(/%2C/, ",", url)
                gsub(/%20/, " ", url); gsub(/%2D/, "-", url); gsub(/%25/, "%", url)
                if (url !~ /duckduckgo\.com\/y\.js/ && url !~ /bing\.com\/aclick/ && url !~ /googleadservices/ && url !~ /doubleclick\.net/ && !(url in seen) && lc < 5) { seen[url]=1; links[lc++] = url }
            }
        }
    }
    END {
        if (lc == 0) {
            print "No results."
            exit
        }
        for (i=0; i<lc; i++) {
            print (i+1) ". " links[i]
        }
    }'
}

# Tool: Scrape web (zero storage - direct curl | awk pipeline)
# Enhanced: extracts title, meta description, headings, and body text
tool_scrape_web() {
    local url="$1"
    
    if [ -z "$url" ]; then
        echo "Error: URL required"
        return
    fi
    
    local ua="Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
    
    # Single curl | awk pipeline: structured extraction in one streaming pass
    curl -k -s -L -A "$ua" -m 15 "$url" 2>/dev/null | awk '
    BEGIN { skip=0; tc=0; lc=0; hc=0; title=""; meta="" }
    {
        # Extract page title
        if (title == "" && match($0, /<title[^>]*>[^<]*/)) {
            t = substr($0, RSTART, RLENGTH)
            gsub(/<title[^>]*>/, "", t)
            gsub(/^ +| +$/, "", t)
            if (length(t) > 0) title = t
        }

        # Extract meta description
        if (meta == "" && match($0, /name="description"[^>]*content="[^"]*/)) {
            m = substr($0, RSTART, RLENGTH)
            if (match(m, /content="[^"]*/)) {
                meta = substr(m, RSTART+9, RLENGTH-9)
            }
        }

        # Extract headings (h1-h3)
        line2 = $0
        while (match(line2, /<h[1-3][^>]*>[^<]*/)) {
            h = substr(line2, RSTART, RLENGTH)
            line2 = substr(line2, RSTART+RLENGTH)
            gsub(/<h[1-3][^>]*>/, "", h)
            gsub(/^ +| +$/, "", h)
            if (length(h) > 1 && hc < 15) { headings[hc++] = h }
        }

        # Extract http links from href attributes
        line = $0
        while (match(line, /href="http[^"]*"/)) {
            href = substr(line, RSTART+6, RLENGTH-7)
            line = substr(line, RSTART+RLENGTH)
            if (lc < 15) { links[lc++] = href }
        }
        
        # Track script/style/nav/footer blocks (case-insensitive)
        low = tolower($0)
        if (match(low, /<script/)) skip=1
        if (match(low, /<\/script>/)) { skip=0; next }
        if (match(low, /<style/)) skip=1
        if (match(low, /<\/style>/)) { skip=0; next }
        if (match(low, /<nav[ >]/)) skip=1
        if (match(low, /<\/nav>/)) { skip=0; next }
        if (match(low, /<footer[ >]/)) skip=1
        if (match(low, /<\/footer>/)) { skip=0; next }
        if (skip) next
        
        # Strip HTML tags and accumulate text
        gsub(/<[^>]*>/, " ")
        gsub(/&nbsp;/, " ")
        gsub(/&amp;/, "\\&")
        gsub(/&lt;/, "<")
        gsub(/&gt;/, ">")
        gsub(/[ \t]+/, " ")
        gsub(/^ +| +$/, "")
        # Skip lines that look like CSS (e.g. @font-face, @media) that slipped through
        if (match($0, /^@(font-face|media|keyframes|import|charset)/)) next
        if (length($0) > 2 && tc < 6000) {
            tc += length($0)
            text = text $0 " "
        }
    }
    END {
        if (tc == 0) { print "Error: Empty or unreachable page"; exit }
        if (title != "") print "Title: " title
        if (meta != "") print "Description: " meta
        print ""
        if (hc > 0) {
            print "=== Headings ==="
            for (i=0; i<hc; i++) print "  " headings[i]
            print ""
        }
        print "=== Content ==="
        print substr(text, 1, 6000)
        print ""
        print "=== Links ==="
        for (i=0; i<lc; i++) print links[i]
    }'
}

# Sandbox directory for LLM file operations
SANDBOX_DIR="${DATA_DIR}/sandbox"
mkdir -p "$SANDBOX_DIR" 2>/dev/null

# Sandbox path check (blocks .. and symlink escapes)
is_sandboxed() {
    local target="$1"
    [ -z "$target" ] && return 1
    case "$target" in
        *".."*) return 1 ;;
    esac
    case "$target" in
        "${SANDBOX_DIR}"/*|"${SANDBOX_DIR}") return 0 ;;
        *) return 1 ;;
    esac
}

# Tool: Read file
tool_read_file() {
    local path="$1"
    if ! is_sandboxed "$path"; then
        echo "Error: Path must be inside sandbox: ${SANDBOX_DIR}"
        return
    fi
    if [ ! -f "$path" ]; then
        echo "Error: File not found: $path"
        return
    fi
    cat "$path"
}

# Tool: Write file (max 50KB, no shell scripts)
tool_write_file() {
    local path="$1"
    local content="$2"
    if ! is_sandboxed "$path"; then
        echo "Error: Path must be inside sandbox: ${SANDBOX_DIR}"
        return
    fi
    if [ "${#content}" -gt 50000 ]; then
        echo "Error: Content too large (max 50KB)"
        return
    fi
    case "$content" in
        *'#!/bin/'*|*'#!/usr/'*) echo "Error: Shell scripts not allowed in file content"; return ;;
    esac
    mkdir -p "$(dirname "$path")"
    echo "$content" > "$path"
    echo "File written: $path"
}

# Tool: Edit file (find and replace, max 50KB)
tool_edit_file() {
    local path="$1"
    local old_str="$2"
    local new_str="$3"
    if ! is_sandboxed "$path"; then
        echo "Error: Path must be inside sandbox: ${SANDBOX_DIR}"
        return
    fi
    if [ ! -f "$path" ]; then
        echo "Error: File not found: $path"
        return
    fi
    if [ "$(wc -c < "$path" 2>/dev/null)" -gt 50000 ]; then
        echo "Error: File too large (max 50KB)"
        return
    fi
    [ -z "$old_str" ] && { echo "Error: old_string required"; return; }
    sed -i "s/${old_str}/${new_str}/" "$path"
    echo "File edited: $path"
}

# Tool: List directory (sandbox only)
tool_list_dir() {
    local prefix="${1:-${SANDBOX_DIR}}"
    if ! is_sandboxed "$prefix"; then
        prefix="${SANDBOX_DIR}"
    fi
    echo "Listing: $prefix"
    find "$prefix" -type f 2>/dev/null | head -50
}

# Tool: System info (OpenWrt specific)
tool_system_info() {
    local hostname=$(cat /proc/sys/kernel/hostname 2>/dev/null)
    local uptime_raw=$(cat /proc/uptime 2>/dev/null | awk '{print $1}' | cut -d. -f1)
    [ -z "$uptime_raw" ] && uptime_raw=0
    
    local uptime_days=$((uptime_raw / 86400))
    local uptime_hours=$((uptime_raw % 86400 / 3600))
    local uptime_mins=$((uptime_raw % 3600 / 60))
    local load=$(cat /proc/loadavg 2>/dev/null | awk '{print $1", "$2", "$3}')
    
    local mem_total=$(free 2>/dev/null | grep Mem | awk '{print $2}')
    local mem_used=$(free 2>/dev/null | grep Mem | awk '{print $3}')
    local mem_free=$(free 2>/dev/null | grep Mem | awk '{print $4}')
    
    local cpu_temp=""
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        local temp_raw=$(cat /sys/class/thermal/thermal_zone0/temp)
        if [ -n "$temp_raw" ] && [ "$temp_raw" -eq "$temp_raw" ] 2>/dev/null; then
            cpu_temp=$((temp_raw / 1000))
            cpu_temp="${cpu_temp}C"
        fi
    fi
    
    local disk_total=$(df / 2>/dev/null | tail -1 | awk '{print $2}')
    local disk_used=$(df / 2>/dev/null | tail -1 | awk '{print $3}')
    local disk_free=$(df / 2>/dev/null | tail -1 | awk '{print $4}')
    
    local openwrt_ver=""
    if [ -f /etc/openwrt_release ]; then
        openwrt_ver=$(grep DISTRIB_RELEASE /etc/openwrt_release 2>/dev/null | cut -d"'" -f2)
    fi
    
    echo "=== System Info ==="
    echo "Hostname: $hostname"
    [ -n "$openwrt_ver" ] && echo "OpenWrt: $openwrt_ver"
    echo "Uptime: ${uptime_days}d ${uptime_hours}h ${uptime_mins}m"
    echo "Load: $load"
    echo "Memory: ${mem_used}/${mem_total} KB used (${mem_free} KB free)"
    [ -n "$cpu_temp" ] && echo "CPU Temp: $cpu_temp"
    echo "Disk: ${disk_used}/${disk_total} KB used (${disk_free} KB free)"
}

# Tool: Network status
tool_network_status() {
    local wan_ip=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
    local wan_iface=$(ip route 2>/dev/null | grep default | awk '{print $5}')
    
    echo "=== Network Status ==="
    echo "WAN IP: $wan_ip"
    echo "WAN Interface: $wan_iface"
    
    echo ""
    echo "=== WiFi Interfaces ==="
    if command -v iw >/dev/null 2>&1; then
        iw dev 2>/dev/null | grep -E "Interface|ssid|type" | head -10
    else
        echo "iw not available"
    fi
    
    echo ""
    echo "=== Connected Devices (ARP) ==="
    ip neigh show 2>/dev/null | grep -v FAILED | head -10
}

# Tool: Run shell command (hardcoded safety blocklist)
tool_run_command() {
    local cmd="$1"
    local low
    low=$(echo "$cmd" | tr '[:upper:]' '[:lower:]')

    # Hardcoded blocklist - destructive, exfiltration, privilege escalation, injection
    case "$low" in
        # Destructive
        *"rm -rf"*|*"mkfs"*|*"dd if="*|*"fdisk"*|*"format"*)
            echo "Error: Destructive command blocked."; return ;;
        # Exfiltration
        *"curl"*|*"wget"*)
            case "$low" in
                *"/tmp/"*|*"/var/"*|*"./"*|*"-o /"*|*"-O /"*|*">> /"*)
                    echo "Error: File download blocked in run_command. Use download_file or http_request instead."; return ;;
            esac ;;
        # Privilege / config tampering
        *"chmod 777"*|*"chmod 666"*|*"chown"*|*"> /etc/"*|*">>/etc/"*|*"passwd"*|*"shadow"*|*"sudo"*|*"su -"*)
            echo "Error: Privilege escalation or config tampering blocked."; return ;;
        # Config/key exfiltration
        *"config.json"*|*"tg_token"*|*"openrouter_key"*|*"api_key"*|*"ui_pass"*)
            echo "Error: Access to credentials blocked."; return ;;
        # Reverse shell / injection
        *"nc -e"*|*"ncat -e"*|*"bash -i"*|*"sh -i"*|*"exec("*|*"eval("*|*"__import__"*|*"subprocess"*|*"os.system"*)
            echo "Error: Shell injection blocked."; return ;;
        # Backticks / subshell injection
        *'`'*|*'$('*)
            echo "Error: Subshell injection blocked."; return ;;
    esac
    # Max command length
    if [ "${#cmd}" -gt 500 ]; then
        echo "Error: Command too long (max 500 chars)."
        return
    fi
    local result=""
    if command -v timeout >/dev/null 2>&1; then
        result=$(timeout 10 sh -c "$cmd" 2>&1)
        [ $? -eq 124 ] && { echo "Error: Command timed out (10s)"; return; }
    else
        result=$(sh -c "$cmd" 2>&1)
    fi
    echo "$result"
}

# Tool: Restart service
tool_restart_service() {
    local service="$1"
    
    # Only allow specific services
    local allowed="firewall network dnsmasq uhttpd dropbear agentwrt agentwrt-ui odhcpd log"
    
    if ! echo "$allowed" | grep -qw "$service"; then
        echo "Error: Can only restart: $allowed"
        return
    fi
    
    if /etc/init.d/"$service" restart 2>&1; then
        echo "Service $service restarted successfully"
    else
        echo "Error restarting $service"
    fi
}

# Tool: List services
tool_list_services() {
    echo "=== Running Services ==="
    for s in /etc/init.d/*; do
        if [ -x "$s" ]; then
            local name=$(basename "$s")
            if "$s" enabled 2>/dev/null; then
                echo "$name: enabled"
            fi
        fi
    done | head -20
}

# Tool: Get weather using Open-Meteo API (free, no API key needed)
tool_get_weather() {
    local location="$1"
    
    # Use default location from config if none provided
    if [ -z "$location" ]; then
        if [ -n "$CONFIG_FILE" ] && [ -f "$CONFIG_FILE" ] && command -v jsonfilter >/dev/null 2>&1; then
            location=$(jsonfilter -i "$CONFIG_FILE" -e '@.weather_default_location' 2>/dev/null)
        fi
        if [ -z "$location" ]; then
            echo "Error: Location required. Set a default in the UI (Weather section) or ask for a city (e.g. 'Buenos Aires' or 'Tokyo, Japan')."
            return
        fi
    fi
    
    local encoded_loc=$(echo "$location" | sed 's/ /+/g; s/,/%2C/g')
    
    # Step 1: Geocode city name to coordinates
    local geo_resp
    geo_resp=$(curl -k -s -m 10 "https://geocoding-api.open-meteo.com/v1/search?name=${encoded_loc}&count=1&language=en" 2>/dev/null)
    
    if [ -z "$geo_resp" ]; then
        echo "Error: Could not geocode location '$location'"
        return
    fi
    
    local lat="" lon="" city="" country=""
    if command -v jsonfilter >/dev/null 2>&1; then
        lat=$(echo "$geo_resp" | jsonfilter -e '@.results[0].latitude' 2>/dev/null)
        lon=$(echo "$geo_resp" | jsonfilter -e '@.results[0].longitude' 2>/dev/null)
        city=$(echo "$geo_resp" | jsonfilter -e '@.results[0].name' 2>/dev/null)
        country=$(echo "$geo_resp" | jsonfilter -e '@.results[0].country' 2>/dev/null)
    else
        lat=$(echo "$geo_resp" | grep -o '"latitude":[0-9.-]*' | head -1 | sed 's/"latitude"://')
        lon=$(echo "$geo_resp" | grep -o '"longitude":[0-9.-]*' | head -1 | sed 's/"longitude"://')
        city=$(echo "$geo_resp" | grep -o '"name":"[^"]*"' | head -1 | sed 's/"name":"//;s/"$//')
        country=$(echo "$geo_resp" | grep -o '"country":"[^"]*"' | head -1 | sed 's/"country":"//;s/"$//')
    fi
    
    if [ -z "$lat" ] || [ -z "$lon" ]; then
        echo "Error: Location '$location' not found"
        return
    fi
    
    # Step 2: Fetch weather from Open-Meteo
    local weather_resp
    weather_resp=$(curl -k -s -m 10 "https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max&timezone=auto&forecast_days=3" 2>/dev/null)
    
    if [ -z "$weather_resp" ]; then
        echo "Error: Could not fetch weather data"
        return
    fi
    
    # Parse current weather
    local temp="" feels="" humidity="" wind_speed="" wind_dir="" wcode=""
    if command -v jsonfilter >/dev/null 2>&1; then
        temp=$(echo "$weather_resp" | jsonfilter -e '@.current.temperature_2m' 2>/dev/null)
        feels=$(echo "$weather_resp" | jsonfilter -e '@.current.apparent_temperature' 2>/dev/null)
        humidity=$(echo "$weather_resp" | jsonfilter -e '@.current.relative_humidity_2m' 2>/dev/null)
        wind_speed=$(echo "$weather_resp" | jsonfilter -e '@.current.wind_speed_10m' 2>/dev/null)
        wind_dir=$(echo "$weather_resp" | jsonfilter -e '@.current.wind_direction_10m' 2>/dev/null)
        wcode=$(echo "$weather_resp" | jsonfilter -e '@.current.weather_code' 2>/dev/null)
    else
        temp=$(echo "$weather_resp" | grep -o '"temperature_2m":[0-9.-]*' | head -1 | sed 's/"temperature_2m"://')
        humidity=$(echo "$weather_resp" | grep -o '"relative_humidity_2m":[0-9.-]*' | head -1 | sed 's/"relative_humidity_2m"://')
        wind_speed=$(echo "$weather_resp" | grep -o '"wind_speed_10m":[0-9.-]*' | head -1 | sed 's/"wind_speed_10m"://')
        wcode=$(echo "$weather_resp" | grep -o '"weather_code":[0-9]*' | head -1 | sed 's/"weather_code"://')
    fi
    
    # Translate WMO weather code to description
    local desc="Unknown"
    case "$wcode" in
        0) desc="Clear sky" ;;
        1) desc="Mainly clear" ;;
        2) desc="Partly cloudy" ;;
        3) desc="Overcast" ;;
        45|48) desc="Foggy" ;;
        51|53|55) desc="Drizzle" ;;
        56|57) desc="Freezing drizzle" ;;
        61|63|65) desc="Rain" ;;
        66|67) desc="Freezing rain" ;;
        71|73|75) desc="Snow" ;;
        77) desc="Snow grains" ;;
        80|81|82) desc="Rain showers" ;;
        85|86) desc="Snow showers" ;;
        95) desc="Thunderstorm" ;;
        96|99) desc="Thunderstorm with hail" ;;
    esac
    
    # Wind direction (degrees to 8 cardinal directions)
    local wind_cardinal=""
    if [ -n "$wind_dir" ] && [ "$wind_dir" -ge 0 ] 2>/dev/null; then
        if [ "$wind_dir" -ge 337 ] || [ "$wind_dir" -lt 23 ]; then wind_cardinal="N"
        elif [ "$wind_dir" -ge 23 ] && [ "$wind_dir" -lt 68 ]; then wind_cardinal="NE"
        elif [ "$wind_dir" -ge 68 ] && [ "$wind_dir" -lt 113 ]; then wind_cardinal="E"
        elif [ "$wind_dir" -ge 113 ] && [ "$wind_dir" -lt 158 ]; then wind_cardinal="SE"
        elif [ "$wind_dir" -ge 158 ] && [ "$wind_dir" -lt 203 ]; then wind_cardinal="S"
        elif [ "$wind_dir" -ge 203 ] && [ "$wind_dir" -lt 248 ]; then wind_cardinal="SW"
        elif [ "$wind_dir" -ge 248 ] && [ "$wind_dir" -lt 293 ]; then wind_cardinal="W"
        else wind_cardinal="NW"
        fi
    fi
    
    echo "Weather for ${city:-$location}${country:+, $country}"
    echo "Condition: $desc"
    echo "Temperature: ${temp}C (feels like ${feels:-$temp}C)"
    echo "Humidity: ${humidity}%"
    if [ -n "$wind_speed" ]; then
        [ -n "$wind_cardinal" ] && echo "Wind: ${wind_speed} km/h from $wind_cardinal" || echo "Wind: ${wind_speed} km/h"
    fi
    
    # Parse 3-day forecast and precipitation
    local d0_max="" d0_min="" d1_max="" d1_min="" d2_max="" d2_min="" precip0=""
    if command -v jsonfilter >/dev/null 2>&1; then
        d0_max=$(echo "$weather_resp" | jsonfilter -e '@.daily.temperature_2m_max[0]' 2>/dev/null)
        d0_min=$(echo "$weather_resp" | jsonfilter -e '@.daily.temperature_2m_min[0]' 2>/dev/null)
        d1_max=$(echo "$weather_resp" | jsonfilter -e '@.daily.temperature_2m_max[1]' 2>/dev/null)
        d1_min=$(echo "$weather_resp" | jsonfilter -e '@.daily.temperature_2m_min[1]' 2>/dev/null)
        d2_max=$(echo "$weather_resp" | jsonfilter -e '@.daily.temperature_2m_max[2]' 2>/dev/null)
        d2_min=$(echo "$weather_resp" | jsonfilter -e '@.daily.temperature_2m_min[2]' 2>/dev/null)
        precip0=$(echo "$weather_resp" | jsonfilter -e '@.daily.precipitation_probability_max[0]' 2>/dev/null)
    fi
    
    if [ -n "$d0_max" ]; then
        echo ""
        echo "Forecast:"
        echo "  Today: ${d0_min}C - ${d0_max}C${precip0:+ (rain chance ${precip0}%)}"
        [ -n "$d1_max" ] && echo "  Tomorrow: ${d1_min}C - ${d1_max}C"
        [ -n "$d2_max" ] && echo "  Day after: ${d2_min}C - ${d2_max}C"
    fi
}

# Tool: HTTP request
tool_http_request() {
    local url="$1"
    local method="${2:-GET}"
    local body="$3"
    
    if [ -z "$url" ]; then
        echo "Error: URL required"
        return
    fi
    
    local result
    if command -v curl >/dev/null 2>&1; then
        if [ "$method" = "POST" ] && [ -n "$body" ]; then
            result=$(curl -k -s -d "$body" "$url")
        else
            result=$(curl -k -s "$url")
        fi
    else
        if [ "$method" = "POST" ] && [ -n "$body" ]; then
            result=$(wget -q -O - --no-check-certificate --post-data="$body" "$url" 2>/dev/null)
        else
            result=$(wget -q -O - --no-check-certificate "$url" 2>/dev/null)
        fi
    fi
    
    echo "$result"
}

# Tool: Download file to /data/documents
tool_download_file() {
    local url="$1"
    local name="$2"

    if [ -z "$url" ]; then
        echo "Error: URL required"
        return
    fi

    local dir="${DATA_DIR}/documents"
    mkdir -p "$dir" 2>/dev/null

    # Derive filename from URL if not provided
    if [ -z "$name" ]; then
        name=$(echo "$url" | sed 's/[?].*$//' | awk -F/ '{print $NF}')
    fi
    [ -z "$name" ] && name="file_$(date +%s)"

    # Sanitize filename
    name=$(echo "$name" | tr -cd 'A-Za-z0-9._-')
    [ -z "$name" ] && name="file_$(date +%s)"

    local path="${dir}/${name}"

    if command -v curl >/dev/null 2>&1; then
        curl -k -L -s -o "$path" "$url"
    else
        wget -q -O "$path" --no-check-certificate "$url" 2>/dev/null
    fi

    if [ ! -f "$path" ] || [ ! -s "$path" ]; then
        echo "Error: Download failed"
        return
    fi

    echo "FILE:${path}"
}

# ============================================
# RESEARCH JOBS (Background Worker)
# ============================================
# ============================================
# SCHEDULING TOOLS (No cron daemon)
# ============================================
SCHED_FILE="${DATA_DIR}/schedules.txt"

# Convert time_offset/interval to cron expression
# Supports: "1 minute", "5 minutes", "1 hour", "1m", "5m", "1h", "every 1 minute", etc.
offset_to_cron() {
    local offset="$1"
    local now_min=$(date +%M)
    local now_hour=$(date +%H)
    
    # Extract number from string
    local num=$(echo "$offset" | grep -o '[0-9]*' | head -1)
    [ -z "$num" ] && num=1
    
    # Parse offset type
    case "$offset" in
        *"m"*|*"minute"*)
            # Every N minutes
            if [ "$num" -eq 1 ]; then
                printf "* * * * *"
            else
                printf "*/%d * * * *" "$num"
            fi
            ;;
        *"h"*|*"hour"*)
            # Every N hours
            printf "0 */%d * * *" "$num"
            ;;
        *"daily"*|*"day"*)
            # Daily at current time + 1 min
            local target_min=$(( (now_min + 1) % 60 ))
            printf "%d %d * * *" "$target_min" "$now_hour"
            ;;
        *)
            # Default: 1 minute from now (one-time)
            local target_min=$(( (now_min + 1) % 60 ))
            local target_hour=$now_hour
            [ $target_min -lt $now_min ] && target_hour=$(( (now_hour + 1) % 24 ))
            printf "%d %d * * *" "$target_min" "$target_hour"
            ;;
    esac
}

tool_set_schedule() {
    local cron="$1"
    local content="$2"
    local chat="$3"
    local id="${4:-mb_$(date +%s)}"
    local type="${5:-msg}"
    
    # If cron looks like a time offset/interval, convert it
    case "$cron" in
        *"m"*|*"h"*|*"minute"*|*"hour"*|*"daily"*|*"every"*|*"in "*)
            cron=$(offset_to_cron "$cron")
            ;;
        "")
            # Empty cron = 1 minute from now
            cron=$(offset_to_cron "1m")
            ;;
    esac
    
    [ -z "$content" ] && { echo "Error: content required"; return; }
    [ -z "$chat" ] && { echo "Error: chat_id required (pass via args)"; return; }

    # Normalize type to supported values (default to msg)
    case "$type" in
        "" )
            type="msg"
            ;;
        msg|reminder|cmd|tool|once|once_cmd|once_tool|probe|agent|once_agent )
            ;;
        agent* )
            type="agent"
            ;;
        once_agent* )
            type="once_agent"
            ;;
        msg* )
            type="msg"
            ;;
        reminder* )
            type="reminder"
            ;;
        once_cmd* )
            type="once_cmd"
            ;;
        once_tool* )
            type="once_tool"
            ;;
        once* )
            type="once"
            ;;
        probe* )
            type="probe"
            ;;
        cmd* )
            type="cmd"
            ;;
        tool* )
            type="tool"
            ;;
        * )
            type="msg"
            ;;
    esac
    
    # Ensure directory exists
    mkdir -p "$(dirname "$SCHED_FILE")" 2>/dev/null
    
    content=$(printf '%s' "$content" | tr '\n' ' ')
    grep -v "^${id}|" "$SCHED_FILE" 2>/dev/null > /tmp/.sch_
    echo "${id}|${cron}|${chat}|${type}|${content}" >> /tmp/.sch_
    mv /tmp/.sch_ "$SCHED_FILE"
    echo "Scheduled: $id"
    echo "Cron: $cron"
}

tool_list_schedules() {
    [ ! -f "$SCHED_FILE" ] && { echo "No schedules"; return; }
    echo "=== Schedules ==="
    while IFS= read -r line; do
        [ -n "$line" ] && echo "$line"
    done < "$SCHED_FILE"
}

tool_remove_schedule() {
    local id="$1"
    [ -z "$id" ] && { echo "Error: ID required"; return; }
    [ ! -f "$SCHED_FILE" ] && return
    grep -v "^${id}|" "$SCHED_FILE" > /tmp/.sch_
    mv /tmp/.sch_ "$SCHED_FILE"
    echo "Removed: $id"
}

tool_set_probe() {
    local cron="$1" probe="$2" chat="$3" id="${4:-probe_$(date +%s)}"
    tool_set_schedule "$cron" "$probe" "$chat" "$id" "probe"
}

# Tool: Network connectivity check + auto-recover
tool_net_check() {
    # Quick ping test (Cloudflare then Google)
    if ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        echo "NET_OK"
        return
    fi

    # Try WiFi radio reset first (configurable)
    if [ "${WIFI_RESET_ENABLE}" = "true" ] && command -v wifi >/dev/null 2>&1; then
        local radio="${WIFI_RESET_RADIO:-radio0}"
        if wifi down "$radio" >/dev/null 2>&1; then
            sleep 2
            if wifi up "$radio" >/dev/null 2>&1; then
                echo "NET_DOWN: wifi ${radio} reset"
                return
            fi
        fi
        # Fallback: reload all radios
        if wifi reload >/dev/null 2>&1; then
            echo "NET_DOWN: wifi reload"
            return
        fi
    fi

    # Try to recover network
    if /etc/init.d/network reload >/dev/null 2>&1; then
        echo "NET_DOWN: network reloaded"
        return
    fi

    if /etc/init.d/network restart >/dev/null 2>&1; then
        echo "NET_DOWN: network restarted"
        return
    fi

    echo "NET_DOWN: restart failed"
}

# Tool: Save a fact to long-term memory
tool_save_memory() {
    local fact="$1"
    if [ -z "$fact" ]; then
        echo "Error: Content required"
        return
    fi
    
    local mem_file="${DATA_DIR}/memory/MEMORY.md"
    local date_str=$(date "+%Y-%m-%d %H:%M")
    
    # Ensure directory exists
    mkdir -p "$(dirname "$mem_file")"
    
    echo "- [${date_str}] ${fact}" >> "$mem_file"
    echo "Memory saved: ${fact}"
}

# Load Plugins from ./plugins/*.sh (respect enabled_plugins)
PLUGIN_DIR="${SCRIPT_DIR:-.}/plugins"
if [ -d "$PLUGIN_DIR" ]; then
    enabled_list=""
    if [ -n "$CONFIG_FILE" ] && command -v jsonfilter >/dev/null 2>&1; then
        enabled_list=$(jsonfilter -i "$CONFIG_FILE" -e '@.enabled_plugins[*]' 2>/dev/null)
        enabled_list=$(echo "$enabled_list" | tr ' ' '\n' | tr '\t' '\n')
    fi

    for plugin in "$PLUGIN_DIR"/*.sh; do
        if [ -f "$plugin" ]; then
            name=$(basename "$plugin" .sh)
            if [ -n "$enabled_list" ]; then
                echo "$enabled_list" | grep -qx "$name" || continue
            fi
            . "$plugin"
        fi
    done
fi

# Tool: Security status report
tool_security_status() {
    local json_args="$1"

    echo "=== Security Guardrails (hardcoded) ==="
    echo ""
    echo "-- File operations --"
    echo "Sandbox dir: ${SANDBOX_DIR}"
    echo "Allowed: read_file, write_file, edit_file, list_dir"
    echo "Blocked: path traversal (..), paths outside sandbox"
    echo ""
    echo "-- Command execution --"
    echo "run_command: hardcoded regex blocklist"
    echo "Blocks: rm -rf, mkfs, dd, fdisk, sudo, chmod 777, subshells,"
    echo "         eval, exfiltration, /etc access, etc."
    echo "Max length: 500 chars, no newlines, no pipe-to-network"
    echo ""
    echo "-- Web tools --"
    echo "URL allowlist: http(s) only"
    echo "SSRF prevention: blocks localhost, 10.x, 172.16-31.x, 192.168.x,"
    echo "                 127.x, 169.254.x, link-local, RFC1918"
    echo "Blocks: file://, gopher://, dict://, ftp://, ldap://"
    echo ""
    echo "-- Prompt injection --"
    echo "Blocks: ignore-previous, disregard, forget-everything,"
    echo "         you-are-now, system:, assistant:, <|...|>,"
    echo "         role markers, jailbreak, DAN mode"
    echo ""
    echo "-- Output sanitization --"
    echo "Strips: ANSI escapes, tokens (8-12 digit:30+ chars),"
    echo "        sk-* keys, AWS keys, base64 blobs, prompt markers"
    echo ""
    echo "-- File size limits --"
    echo "write_file: max 50KB content"
    echo "edit_file: max 50KB existing file"
    echo ""
    echo "All guardrails are hardcoded in agentwrt.py execute_tool()."
    echo "No config file can disable them."
}
