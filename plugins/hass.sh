#!/bin/sh

# Plugin: Home Assistant Control
# Tools: ha_call_service, ha_get_state, ha_camera_snapshot
# Args: JSON string

# Helper: Get config
_ha_get_config() {
    [ -z "$CONFIG_LOADED" ] && . "${SCRIPT_DIR:-.}/config.sh"
    
    HASS_URL=$(jsonfilter -i "$CONFIG_FILE" -e '@.hass_url' 2>/dev/null)
    HASS_TOKEN=$(jsonfilter -i "$CONFIG_FILE" -e '@.hass_token' 2>/dev/null)
    
    if [ -z "$HASS_URL" ] || [ -z "$HASS_TOKEN" ]; then
        echo "Error: Home Assistant not configured. Add 'hass_url' and 'hass_token' to config.json"
        return 1
    fi
    return 0
}

tool_ha_call_service() {
    local json_args="$1"
    _ha_get_config || return
    
    local domain="" service="" entity_id=""
    if command -v jsonfilter >/dev/null 2>&1; then
        domain=$(echo "$json_args" | jsonfilter -e '@.domain')
        service=$(echo "$json_args" | jsonfilter -e '@.service')
        entity_id=$(echo "$json_args" | jsonfilter -e '@.entity_id')
    else
        # Fallback
        domain=$(echo "$json_args" | grep -o '"domain": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
        service=$(echo "$json_args" | grep -o '"service": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
        entity_id=$(echo "$json_args" | grep -o '"entity_id": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
    fi
    
    if [ -z "$domain" ] || [ -z "$service" ] || [ -z "$entity_id" ]; then
        echo "Error: Required args: domain, service, entity_id"
        return
    fi
    
    echo "Calling service ${domain}.${service} on ${entity_id}..."
    local result
    result=$(curl -k -s -X POST "${HASS_URL}/api/services/${domain}/${service}" \
        -H "Authorization: Bearer $HASS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"entity_id\": \"${entity_id}\"}")
        
    echo "Result: $result"
}

tool_ha_get_state() {
    local json_args="$1"
    _ha_get_config || return
    
    local entity_id=""
    if command -v jsonfilter >/dev/null 2>&1; then
        entity_id=$(echo "$json_args" | jsonfilter -e '@.entity_id')
    else
        entity_id=$(echo "$json_args" | grep -o '"entity_id": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
    fi
    
    if [ -z "$entity_id" ]; then
        echo "Error: entity_id required"
        return
    fi
    
    local result
    result=$(curl -k -s -X GET "${HASS_URL}/api/states/${entity_id}" \
        -H "Authorization: Bearer $HASS_TOKEN" \
        -H "Content-Type: application/json")
        
    local state=$(echo "$result" | jsonfilter -e '@.state' 2>/dev/null)
    local attr=$(echo "$result" | jsonfilter -e '@.attributes' 2>/dev/null)
    
    if [ -z "$state" ]; then
        # Fallback grep
        state=$(echo "$result" | grep -o '"state": *"[^"]*"' | head -1 | sed 's/.*: *"//;s/"$//')
    fi
    
    echo "Entity: $entity_id | State: $state"
    # echo "Attributes: $attr" # Too verbose?
}

tool_ha_camera_snapshot() {
    local json_args="$1"
    _ha_get_config || return
    
    local entity_id=""
    if command -v jsonfilter >/dev/null 2>&1; then
        entity_id=$(echo "$json_args" | jsonfilter -e '@.entity_id')
    else
        entity_id=$(echo "$json_args" | grep -o '"entity_id": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
    fi
    
    if [ -z "$entity_id" ]; then
        echo "Error: entity_id required"
        return
    fi
    
    local filename="snapshot_$(date +%s).jpg"
    local filepath="${DATA_DIR}/${filename}"
    
    echo "Taking snapshot from ${entity_id}..."
    # Use camera_proxy to get raw image
    curl -k -s -X GET "${HASS_URL}/api/camera_proxy/${entity_id}" \
        -H "Authorization: Bearer $HASS_TOKEN" \
        -o "$filepath"
        
    if [ -f "$filepath" ]; then
        echo "Snapshot saved to ${filepath}"
        # Ideally, we would send this photo to Telegram.
        # But for now, we just save it.
        # TODO: Implement send_photo tool or integrate here?
        # Microbot currently only sends text. 
        # But we can return the path and maybe user can scp it.
    else
        echo "Error: Failed to save snapshot."
    fi
}
