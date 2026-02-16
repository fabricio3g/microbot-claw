#!/bin/sh

# Plugin: Notion Notes
# Tool: add_notion_note
# Args: JSON string {"content": "..."}

tool_add_notion_note() {
    local json_args="$1"
    
    # Load config if not loaded
    [ -z "$CONFIG_LOADED" ] && . "${SCRIPT_DIR:-.}/config.sh"
    
    # Extract args
    local content=""
    if command -v jsonfilter >/dev/null 2>&1; then
        content=$(echo "$json_args" | jsonfilter -e '@.content')
    else
        content=$(echo "$json_args" | grep -o '"content": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
    fi
    
    # Check config
    local token="" page_id=""
    token=$(jsonfilter -i "$CONFIG_FILE" -e '@.notion_token' 2>/dev/null)
    page_id=$(jsonfilter -i "$CONFIG_FILE" -e '@.notion_page_id' 2>/dev/null)
    
    if [ -z "$token" ] || [ -z "$page_id" ]; then
        echo "Error: Notion not configured. Add 'notion_token' (integration) and 'notion_page_id' to config.json"
        return
    fi
    
    if [ -z "$content" ]; then
        echo "Error: Content required."
        return
    fi
    
    # Construct JSON payload for block append
    # Needs escaping
    local safe_content=$(echo "$content" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
    
    local payload='{
      "children": [
        {
          "object": "block",
          "type": "paragraph",
          "paragraph": {
            "rich_text": [
              {
                "type": "text",
                "text": {
                  "content": "'"$safe_content"'"
                }
              }
            ]
          }
        }
      ]
    }'
    
    echo "Adding note to Notion..."
    local result
    result=$(curl -k -s -X PATCH "https://api.notion.com/v1/blocks/${page_id}/children" \
      -H "Authorization: Bearer $token" \
      -H "Content-Type: application/json" \
      -H "Notion-Version: 2022-06-28" \
      -d "$payload")
      
    if echo "$result" | grep -q '"object": *"list"'; then
        echo "Note added successfully to Notion!"
    else
        echo "Error adding note: $result"
    fi
}
