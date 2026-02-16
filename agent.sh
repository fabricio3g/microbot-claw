#!/bin/sh
# MicroBot AI - Agent Logic (ReAct Loop)
# Shared between Shell and Python bots

# Sourced modules MUST be available in the same directory or path
# Assuming config.sh, llm.sh, tools.sh, memory.sh are already sourced by caller
# or we source them here if variables are missing.

SESSION_DIR="${DATA_DIR}/sessions"
MAX_HISTORY=10
MAX_ITERATIONS=5
TEMP_DIR="/tmp/microbot"

# Ensure temp dir exists (in case)
if [ ! -d "$TEMP_DIR" ]; then
    mkdir -p "$TEMP_DIR" 2>/dev/null || TEMP_DIR="/tmp"
fi

mkdir -p "$SESSION_DIR"

# Session file path
session_file() {
    echo "${SESSION_DIR}/${1}.txt"
}

# Append to session
session_append() {
    local chat_id="$1"
    local role="$2"
    local content="$3"
    local file=$(session_file "$chat_id")
    echo "${role}|${content}" >> "$file"
}

# Clear session
session_clear() {
    local chat_id="$1"
    local file=$(session_file "$chat_id")
    rm -f "$file"
}

# Process message and get response
process_message() {
    local chat_id="$1"
    local user_text="$2"
    local session_file_path=$(session_file "$chat_id")
    
    # Build system prompt
    local system_prompt=$(build_system_prompt)
    
    # Build messages - start with user message
    # DEBUG: Print user text to stderr
    echo "[agent] User Text: $user_text" >&2
    
    local escaped_text=$(json_escape "$user_text")
    local messages="[{\"role\":\"user\",\"content\":\"${escaped_text}\"}]"
    
    # Add history if exists (simplified - just last few exchanges)
    if [ -f "$session_file_path" ]; then
        local history_messages=""
        
        # Use temp file to avoid subshell variable loss issues with pipe
        local hist_tmp="${TEMP_DIR}/hist_${chat_id}_$$.txt"
        tail -n 6 "$session_file_path" > "$hist_tmp"
        
        while IFS='|' read -r role content; do
            [ -z "$role" ] && continue
            
            if [ -n "$history_messages" ]; then
                history_messages="${history_messages},"
            fi
            history_messages="${history_messages}{\"role\":\"${role}\",\"content\":\"$(json_escape "$content")\"}"
        done < "$hist_tmp"
        rm -f "$hist_tmp"
        
        if [ -n "$history_messages" ]; then
            messages="[${history_messages},{\"role\":\"user\",\"content\":\"${escaped_text}\"}]"
        fi
    fi
    
    # DEBUG: Print final messages JSON (truncated)
    echo "[agent] Messages JSON: ${messages:0:200}..." >&2
    
    # Get tools
    local tools=$(get_tools_json)
    
    # ReAct loop
    local iteration=0
    local final_text=""
    
    while [ $iteration -lt $MAX_ITERATIONS ]; do
        echo "[agent] Iteration $((iteration + 1))" >&2
        
        # Call LLM
        local llm_resp=$(llm_chat "$system_prompt" "$messages" "$tools")
        
        if [ -z "$llm_resp" ]; then
            echo "[agent] ERROR: Empty response" >&2
            echo "Sorry, connection error. Please try again."
            return
        fi
        
        # Check for API errors
        if echo "$llm_resp" | grep -q '"error"'; then
            echo "[agent] RAW RESPONSE: $llm_resp" >&2
            local error=$(echo "$llm_resp" | jsonfilter -e '@.error.message' 2>/dev/null)
            [ -z "$error" ] && error=$(echo "$llm_resp" | jsonfilter -e '@.error' 2>/dev/null)
            echo "[agent] API Error: $error" >&2
            echo "API Error: ${error}"
            return
        fi
        
        # Check if tool use
        if llm_is_tool_use "$llm_resp"; then
            echo "[agent] Tool use detected" >&2
            
            # Get any response text
            local response_text=$(llm_get_text "$llm_resp")
            
            # Get tool calls
            local tool_calls_file="${TEMP_DIR}/tools_${chat_id}_$$.txt"
            llm_get_tool_calls "$llm_resp" > "$tool_calls_file"
            
            local tool_count=$(grep -c "^TOOL:" "$tool_calls_file" 2>/dev/null || echo 0)
            echo "[agent] $tool_count tool calls" >&2
            
            # Build tool results summary
            local tool_summary=""
            while IFS=':' read -r tool_type tool_id tool_name tool_args; do
                [ "$tool_type" != "TOOL" ] && continue
                [ -z "$tool_name" ] && continue
                
                echo "[agent] Executing: $tool_name" >&2
                
                local tool_output=$(tool_execute "$tool_name" "$tool_args")
                # echo "[agent] Result: ${tool_output:0:80}..." >&2
                
                tool_summary="${tool_summary}[Tool: ${tool_name}]\n${tool_output}\n\n"
            done < "$tool_calls_file"
            
            rm -f "$tool_calls_file"
            
            # Update messages for next iteration
            # Append assistant text (if any) and tool results
            if [ -n "$response_text" ]; then
                messages="${messages%]}},{\"role\":\"assistant\",\"content\":\"$(json_escape "$response_text")\"}]"
            fi
            messages="${messages%]}},{\"role\":\"user\",\"content\":\"$(json_escape "$tool_summary")\"}]"
            
            iteration=$((iteration + 1))
            continue
        fi
        
        # No tool use - final response
        final_text=$(llm_get_text "$llm_resp")
        break
    done
    
    if [ -z "$final_text" ]; then
        final_text="Done! Anything else?"
    fi
    
    # Save to session
    session_append "$chat_id" "user" "$user_text"
    session_append "$chat_id" "assistant" "$final_text"
    
    echo "$final_text"
}
