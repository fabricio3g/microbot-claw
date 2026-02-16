#!/bin/sh
# MicroBot AI - Memory Management

MEMORY_DIR="${DATA_DIR}/memory"
CONFIG_DIR="${DATA_DIR}/config"
MEMORY_FILE="${MEMORY_DIR}/MEMORY.md"
SOUL_FILE="${CONFIG_DIR}/SOUL.md"
USER_FILE="${CONFIG_DIR}/USER.md"

# Initialize memory directories
memory_init() {
    mkdir -p "$MEMORY_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "${DATA_DIR}/sessions"
    
    [ ! -f "$SOUL_FILE" ] && echo "I am MicroBot AI, a personal AI assistant running on OpenWrt." > "$SOUL_FILE"
    [ ! -f "$USER_FILE" ] && echo "# User Profile\n- Name: (not set)" > "$USER_FILE"
    [ ! -f "$MEMORY_FILE" ] && echo "# Long-term Memory\n(empty)" > "$MEMORY_FILE"
}

# Read file
memory_read() {
    local file="$1"
    [ -f "$file" ] && cat "$file"
}

# Write file
memory_write() {
    local file="$1"
    local content="$2"
    echo "$content" > "$file"
}

# Append to file
memory_append() {
    local file="$1"
    local content="$2"
    echo "$content" >> "$file"
}

# Get today's date string
get_date_str() {
    date "+%Y-%m-%d"
}

# Get date N days ago
get_date_ago() {
    local days="${1:-0}"
    date -D "%s" -d "$(( $(date +%s) - days * 86400 ))" "+%Y-%m-%d" 2>/dev/null || date "+%Y-%m-%d"
}

# Read long-term memory
memory_read_long_term() {
    memory_read "$MEMORY_FILE"
}

# Write long-term memory
memory_write_long_term() {
    local content="$1"
    memory_write "$MEMORY_FILE" "$content"
}

# Append to today's note
memory_append_today() {
    local note="$1"
    local today=$(get_date_str)
    local daily_file="${MEMORY_DIR}/${today}.md"
    
    [ ! -f "$daily_file" ] && echo "# ${today}\n" > "$daily_file"
    memory_append "$daily_file" "$note"
}

# Read recent notes (last N days)
memory_read_recent() {
    local days="${1:-3}"
    local result=""
    
    local i=0
    while [ $i -lt $days ]; do
        local date=$(get_date_ago $i)
        local daily_file="${MEMORY_DIR}/${date}.md"
        
        if [ -f "$daily_file" ]; then
            [ -n "$result" ] && result="${result}\n---\n"
            result="${result}$(cat "$daily_file")"
        fi
        
        i=$((i + 1))
    done
    
    echo "$result"
}

# Build system prompt
build_system_prompt() {
    local prompt="# MicroBot AI

You are MicroBot AI, a personal AI assistant running on OpenWrt/Linux.
You communicate through Telegram.
Be helpful, accurate, and concise.

"
    # If native tools are disabled, teach the model how to use tools
    if [ "$USE_NATIVE_TOOLS" != "true" ]; then
        prompt="${prompt}
## Tool Usage
You have access to the following tools. To use a tool, your response must start with the tool call in this specific format:
TOOL:tool_name:json_arguments

Example:
TOOL:get_current_time:{}
TOOL:web_search:{\"query\":\"openwrt news\"}

Available Tools:
- web_search: Search the web. Args: {\"query\": \"...\"}
- get_current_time: Get date/time. Args: {}
- read_file: Read file. Args: {\"path\": \"/data/...\"}
- write_file: Write file. Args: {\"path\": \"...\", \"content\": \"...\"}
- edit_file: Edit file. Args: {\"path\": \"...\", \"old_string\": \"...\", \"new_string\": \"...\"}
- list_dir: List files. Args: {\"prefix\": \"/data/...\"}
- system_info: Get system stats. Args: {}
- network_status: Get network stats. Args: {}
- run_command: Run shell cmd. Args: {\"command\": \"...\"}
- restart_service: Restart service. Args: {\"service\": \"...\"}
- get_weather: Get weather. Args: {\"location\": \"...\"}
- http_request: HTTP request. Args: {\"url\": \"...\", \"method\": \"GET/POST\", \"body\": \"...\"}
- save_memory: Save important fact. Args: {\"fact\": \"...\"}

IMPORTANT:
- Use only one tool at a time.
- If you use a tool, do NOT write any other text.
- If no tool is needed, just write your response normally.
If the user asks you to remember or save important info, call save_memory.
"
    else
        prompt="${prompt}
## Available Tools
- web_search: Search the web for current information
- get_current_time: Get current date and time
- read_file: Read file from /data/
- write_file: Write file to /data/
- edit_file: Edit file with find/replace
- list_dir: List files in /data/
        "
    fi

    prompt="${prompt}
## Memory
You have persistent memory stored locally:
- Long-term memory: /data/memory/MEMORY.md
- Daily notes: /data/memory/<YYYY-MM-DD>.md

IMPORTANT: Actively use memory to remember things across conversations.
Use get_current_time to know today's date before writing daily notes.
"
    
    # Add personality
    if [ -f "$SOUL_FILE" ]; then
        prompt="${prompt}\n## Personality\n\n$(cat "$SOUL_FILE")\n"
    fi
    
    # Add user info
    if [ -f "$USER_FILE" ]; then
        prompt="${prompt}\n## User Info\n\n$(cat "$USER_FILE")\n"
    fi
    
    # Add long-term memory
    if [ -f "$MEMORY_FILE" ]; then
        prompt="${prompt}\n## Long-term Memory\n\n$(cat "$MEMORY_FILE")\n"
    fi
    
    # Add recent notes
    local recent=$(memory_read_recent 3)
    if [ -n "$recent" ]; then
        prompt="${prompt}\n## Recent Notes\n\n${recent}\n"
    fi
    
    echo "$prompt"
}
