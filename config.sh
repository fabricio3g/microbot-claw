#!/bin/sh
# MicroBot-Claw - Configuration for OpenWrt


# Determine data directory (prefer local ./data if present)
if [ -n "$SCRIPT_DIR" ] && [ -d "${SCRIPT_DIR}/data" ]; then
    DATA_DIR="${SCRIPT_DIR}/data"
elif [ -d "/data" ]; then
    DATA_DIR="/data"
else
    DATA_DIR="./data"
fi

mkdir -p "$DATA_DIR"
CONFIG_FILE="${DATA_DIR}/config.json"

WIFI_SSID=""
WIFI_PASS=""
TG_TOKEN=""
PROVIDER="openrouter"
API_KEY=""
MODEL="claude-opus-4-5"
OPENROUTER_KEY=""
OPENROUTER_MODEL="anthropic/claude-opus-4"
PROXY_HOST=""
PROXY_PORT=""
SEARCH_KEY=""
HTTP_PORT="8080"
TIMEZONE=""
MAX_TOKENS="4096"
DEEP_SEARCH_SAVE="true"
DEEP_SEARCH_KEEP="false"
DEEP_SEARCH_SAVE_DIR="${DATA_DIR}/deepsearch"
WIFI_RESET_ENABLE="true"
WIFI_RESET_RADIO="radio0"
CRAWL_ALLOW_DOMAINS=""
TOOL_ALLOWLIST=""
TOOL_RATE_LIMIT_PER_MIN="10"
TOOL_RATE_LIMIT_BURST="3"
ENABLED_PLUGINS=""
INBOX_CHECK_INTERVAL="2"
WEBHOOK_TOKEN=""
SLACK_BOT_TOKEN=""
SLACK_WEBHOOK_TOKEN=""

# JSON escape function
json_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ' | sed 's/  */ /g'
}

# Load config using jsonfilter
load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "[config] Config file not found: $CONFIG_FILE"
        echo "[config] Creating default config..."
        mkdir -p /data
        cat > "$CONFIG_FILE" << 'DEFCONF'
{
    "wifi_ssid": "",
    "wifi_pass": "",
    "tg_token": "",
    "provider": "openrouter",
    "api_key": "",
    "model": "claude-opus-4-5",
    "openrouter_key": "",
    "openrouter_model": "anthropic/claude-opus-4",
    "proxy_host": "",
    "proxy_port": "",
    "search_key": "",
    "gmail_user": "",
    "gmail_app_password": "",
    "http_port": "8080",
    "timezone": "UTC",
    "schedule_catchup_minutes": "5",
    "schedule_max_fires_per_tick": "1",
    "schedule_log": "false",
    "allow_llm_summary": "false",
    "routing_enabled": "true",
    "routing_long_message_chars": "500",
    "routing_deep_keywords": "design,architecture,refactor,proposal,spec,plan,analysis",
    "routing_fast_tokens": "256",
    "routing_balanced_tokens": "512",
    "routing_deep_tokens": "1024",
    "routing_fast_temp": "0.2",
    "routing_balanced_temp": "0.4",
    "routing_deep_temp": "0.7",
    "delegation_enabled": "true",
    "delegation_max_calls": "3",
    "delegation_max_tokens_per_call": "256",
    "delegation_timeout_sec": "12",
    "delegation_keywords": "plan,design,architecture,proposal,spec",
    "openrouter_model_fallback": "",
    "model_fallback": "",
    "llm_max_retries": "2",
    "llm_retry_backoff_ms": "500",
    "tool_allowlist": "",
    "tool_rate_limit_per_min": "10",
    "tool_rate_limit_burst": "3",
    "enabled_plugins": [],
    "crawl_allow_domains": "",
    "inbox_check_interval": "2",
    "webhook_token": "",
    "slack_bot_token": "",
    "slack_webhook_token": "",
    "enable_selector": "true",
    "selector_max_tokens": "64",
    "max_iterations": "8",
    "one_tool_only": "false",
    "send_wait_messages": "false",
    "ui_enabled": "true",
    "ui_bind": "0.0.0.0",
    "ui_port": "8080",
    "ui_pass_salt": "",
    "ui_pass_hash": ""
}
DEFCONF
        echo "[config] Created $CONFIG_FILE - please edit with your keys"
        return 1
    fi
    
    # echo "[config] Loading from $CONFIG_FILE"
    
    local val
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.wifi_ssid' 2>/dev/null) && [ -n "$val" ] && WIFI_SSID="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.wifi_pass' 2>/dev/null) && [ -n "$val" ] && WIFI_PASS="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.tg_token' 2>/dev/null) && [ -n "$val" ] && TG_TOKEN="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.provider' 2>/dev/null) && [ -n "$val" ] && PROVIDER="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.api_key' 2>/dev/null) && [ -n "$val" ] && API_KEY="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.model' 2>/dev/null) && [ -n "$val" ] && MODEL="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.openrouter_key' 2>/dev/null) && [ -n "$val" ] && OPENROUTER_KEY="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.openrouter_model' 2>/dev/null) && [ -n "$val" ] && OPENROUTER_MODEL="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.proxy_host' 2>/dev/null) && [ -n "$val" ] && PROXY_HOST="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.proxy_port' 2>/dev/null) && [ -n "$val" ] && PROXY_PORT="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.search_key' 2>/dev/null) && [ -n "$val" ] && SEARCH_KEY="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.http_port' 2>/dev/null) && [ -n "$val" ] && HTTP_PORT="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.timezone' 2>/dev/null) && [ -n "$val" ] && TIMEZONE="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.deep_search_save' 2>/dev/null) && [ -n "$val" ] && DEEP_SEARCH_SAVE="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.deep_search_keep' 2>/dev/null) && [ -n "$val" ] && DEEP_SEARCH_KEEP="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.deep_search_save_dir' 2>/dev/null) && [ -n "$val" ] && DEEP_SEARCH_SAVE_DIR="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.wifi_reset_enable' 2>/dev/null) && [ -n "$val" ] && WIFI_RESET_ENABLE="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.wifi_reset_radio' 2>/dev/null) && [ -n "$val" ] && WIFI_RESET_RADIO="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.crawl_allow_domains' 2>/dev/null) && [ -n "$val" ] && CRAWL_ALLOW_DOMAINS="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.tool_allowlist' 2>/dev/null) && [ -n "$val" ] && TOOL_ALLOWLIST="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.tool_rate_limit_per_min' 2>/dev/null) && [ -n "$val" ] && TOOL_RATE_LIMIT_PER_MIN="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.tool_rate_limit_burst' 2>/dev/null) && [ -n "$val" ] && TOOL_RATE_LIMIT_BURST="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.enabled_plugins[*]' 2>/dev/null) && [ -n "$val" ] && ENABLED_PLUGINS="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.inbox_check_interval' 2>/dev/null) && [ -n "$val" ] && INBOX_CHECK_INTERVAL="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.webhook_token' 2>/dev/null) && [ -n "$val" ] && WEBHOOK_TOKEN="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.slack_bot_token' 2>/dev/null) && [ -n "$val" ] && SLACK_BOT_TOKEN="$val"
    val=$(jsonfilter -i "$CONFIG_FILE" -e '@.slack_webhook_token' 2>/dev/null) && [ -n "$val" ] && SLACK_WEBHOOK_TOKEN="$val"
    
    [ -z "$PROVIDER" ] && PROVIDER="openrouter"
    [ -z "$MODEL" ] && MODEL="claude-opus-4-5"
    [ -z "$OPENROUTER_MODEL" ] && OPENROUTER_MODEL="anthropic/claude-opus-4"
    [ -z "$HTTP_PORT" ] && HTTP_PORT="8080"
    
    # echo "[config] Provider: $PROVIDER" >&2
    # echo "[config] Model: $(get_current_model)" >&2
    if [ -n "$TG_TOKEN" ]; then
        # echo "[config] Telegram: ${TG_TOKEN:0:10}..." >&2
        :
    fi
    if [ -n "$OPENROUTER_KEY" ]; then
        # echo "[config] OpenRouter: ${OPENROUTER_KEY:0:10}..." >&2
        :
    fi
    if [ -n "$API_KEY" ]; then
        # echo "[config] Anthropic: ${API_KEY:0:10}..." >&2
        :
    fi
}

get_current_model() {
    if [ "$PROVIDER" = "openrouter" ]; then
        echo "$OPENROUTER_MODEL"
    else
        echo "$MODEL"
    fi
}

get_api_key() {
    if [ "$PROVIDER" = "openrouter" ]; then
        echo "$OPENROUTER_KEY"
    else
        echo "$API_KEY"
    fi
}

# Load config on source
if [ -z "$CONFIG_LOADED" ]; then
    load_config >&2
    CONFIG_LOADED=1
fi
