#!/bin/sh
# MicroBot AI - Skill System
# Pure shell skill loader. Reads JSON metadata from plugins/*.json
# and generates tool lists + prompt fragments for the LLM.
#
# Dependencies: jsonfilter (OpenWrt built-in), sh

# Find script directory
SKILL_DIR="${SCRIPT_DIR:-$(cd "$(dirname "$0")" && pwd)}/plugins"

# List all available skill names (one per line)
# Reads from plugins/*.json + hardcoded core tools
skill_list_names() {
    # Core tools (built into tools.sh)
    echo "web_search"
    echo "scrape_web"
    echo "get_current_time"
    echo "read_file"
    echo "write_file"
    echo "edit_file"
    echo "list_dir"
    echo "system_info"
    echo "network_status"
    echo "run_command"
    echo "list_services"
    echo "restart_service"
    echo "get_weather"
    echo "http_request"
    echo "download_file"
    echo "start_research_job"
    echo "set_schedule"
    echo "list_schedules"
    echo "remove_schedule"
    echo "save_memory"

    # Plugin tools (from *.json metadata)
    if [ -d "$SKILL_DIR" ]; then
        local enabled_list=""
        if [ -n "$CONFIG_FILE" ] && command -v jsonfilter >/dev/null 2>&1; then
            enabled_list=$(jsonfilter -i "$CONFIG_FILE" -e '@.enabled_plugins[*]' 2>/dev/null)
            enabled_list=$(echo "$enabled_list" | tr ' ' '\n' | tr '\t' '\n')
        fi
        for jf in "$SKILL_DIR"/*.json; do
            [ -f "$jf" ] || continue
            local base
            base=$(basename "$jf" .json)
            if [ -n "$enabled_list" ]; then
                echo "$enabled_list" | grep -qx "$base" || continue
            fi
            local name=""
            name=$(jsonfilter -i "$jf" -e '@.name' 2>/dev/null)
            [ -n "$name" ] && echo "$name"
        done
    fi
}

# Generate comma-separated tool names for system prompt
skill_list_csv() {
    skill_list_names | tr '\n' ',' | sed 's/,$//'
}

# Generate tool descriptions block for system prompt
# Format: "tool_name - description"
skill_list_descriptions() {
    # Core tools (compact descriptions)
    cat <<'CORE'
web_search - Search web (args: query)
scrape_web - Fetch URL text (args: url)
get_current_time - Get date/time
read_file - Read file (args: path)
write_file - Write file (args: path, content)
edit_file - Edit file (args: path, old_string, new_string)
list_dir - List files (args: prefix)
system_info - Get system stats (CPU, RAM, Disk)
network_status - Get network info (IP, WiFi)
run_command - Run shell command (args: command)
list_services - List services
restart_service - Restart service (args: name)
get_weather - Get weather (args: location)
http_request - HTTP request (args: url, method, body)
download_file - Download file (args: url, filename)
start_research_job - Queue background research job (args: query, chat_id, max_pages, max_depth)
set_schedule - Schedule task (args: cron_expression or simple English, content, type=reminder|once)
list_schedules - List active schedules
remove_schedule - Remove schedule (args: id)
save_memory - Save fact (args: fact)
CORE

    # Plugin tools (from JSON metadata)
    if [ -d "$SKILL_DIR" ]; then
        local enabled_list=""
        if [ -n "$CONFIG_FILE" ] && command -v jsonfilter >/dev/null 2>&1; then
            enabled_list=$(jsonfilter -i "$CONFIG_FILE" -e '@.enabled_plugins[*]' 2>/dev/null)
            enabled_list=$(echo "$enabled_list" | tr ' ' '\n' | tr '\t' '\n')
        fi
        for jf in "$SKILL_DIR"/*.json; do
            [ -f "$jf" ] || continue
            local base
            base=$(basename "$jf" .json)
            if [ -n "$enabled_list" ]; then
                echo "$enabled_list" | grep -qx "$base" || continue
            fi
            local name="" desc="" args=""
            name=$(jsonfilter -i "$jf" -e '@.name' 2>/dev/null)
            desc=$(jsonfilter -i "$jf" -e '@.description' 2>/dev/null)
            args=$(jsonfilter -i "$jf" -e '@.args' 2>/dev/null)
            if [ -n "$args" ]; then
                echo "${name} - ${desc:-No description} (args: ${args})"
            else
                [ -n "$name" ] && echo "${name} - ${desc:-No description}"
            fi
        done
    fi
}

# Count total available tools
skill_count() {
    skill_list_names | wc -l | tr -d ' '
}

# Check if a tool name is a known skill
skill_exists() {
    local check="$1"
    skill_list_names | grep -qx "$check"
}
