#!/bin/sh
# MicroBot AI - Setup Test

echo "========================================"
echo "  MicroBot AI Setup Test"
echo "========================================"
echo ""

# Check commands
echo "[1] Checking required commands..."
commands_ok=1

for cmd in wget jsonfilter; do
    if command -v $cmd >/dev/null 2>&1; then
        echo "  ✓ $cmd: OK"
    else
        echo "  ✗ $cmd: MISSING"
        commands_ok=0
    fi
done

echo ""

# Check config file
echo "[2] Checking configuration..."
config_file="/data/config.json"

if [ -f "$config_file" ]; then
    echo "  ✓ Config file: $config_file"
    echo ""
    
    # Check TG token
    tg_token=$(jsonfilter -i "$config_file" -e '@.tg_token' 2>/dev/null)
    if [ -n "$tg_token" ] && [ "$tg_token" != "" ]; then
        echo "  ✓ Telegram token: ${tg_token:0:10}..."
    else
        echo "  ✗ Telegram token: NOT SET"
        echo "    Get from @BotFather on Telegram"
    fi
    
    # Check API keys
    api_key=$(jsonfilter -i "$config_file" -e '@.api_key' 2>/dev/null)
    or_key=$(jsonfilter -i "$config_file" -e '@.openrouter_key' 2>/dev/null)
    provider=$(jsonfilter -i "$config_file" -e '@.provider' 2>/dev/null)
    
    echo "  Provider: ${provider:-anthropic}"
    
    if [ -n "$api_key" ]; then
        echo "  ✓ Anthropic key: ${api_key:0:10}..."
    fi
    if [ -n "$or_key" ]; then
        echo "  ✓ OpenRouter key: ${or_key:0:10}..."
    fi
    
    if [ -z "$api_key" ] && [ -z "$or_key" ]; then
        echo "  ✗ API key: NOT SET"
        echo "    Get from https://openrouter.ai/keys"
    fi
else
    echo "  ✗ Config file not found: $config_file"
    echo ""
    echo "  Create it with:"
    echo "  mkdir -p /data"
    echo '  echo '\''{"tg_token":"","openrouter_key":"","provider":"openrouter","openrouter_model":"anthropic/claude-opus-4"}'\'' > /data/config.json'
fi

echo ""

# Check directories
echo "[3] Checking directories..."
for dir in /data/config /data/memory /data/sessions; do
    if [ -d "$dir" ]; then
        echo "  ✓ $dir"
    else
        echo "  ○ $dir (will be created on first run)"
    fi
done

echo ""

# Test Telegram API
echo "[4] Testing Telegram API..."
if [ -n "$tg_token" ]; then
    api_url="https://api.telegram.org/bot${tg_token}/getMe"
    resp=$(wget -q -O - --no-check-certificate "$api_url" 2>/dev/null)
    
    if echo "$resp" | grep -q '"ok":true'; then
        bot_name=$(echo "$resp" | jsonfilter -e '@.result.username' 2>/dev/null)
        echo "  ✓ Bot connected: @$bot_name"
    else
        echo "  ✗ API error or invalid token"
    fi
else
    echo "  - Skipped (no token)"
fi

echo ""

# Test LLM API
echo "[5] Testing LLM API..."
if [ -n "$or_key" ]; then
    models_url="https://openrouter.ai/api/v1/models"
    resp=$(wget -q -O - --no-check-certificate \
        --header="Authorization: Bearer ${or_key}" \
        "$models_url" 2>/dev/null)
    
    if echo "$resp" | grep -q '"data"'; then
        echo "  ✓ OpenRouter connected"
    else
        echo "  ✗ OpenRouter error or invalid key"
    fi
else
    echo "  - Skipped (no API key)"
fi

echo ""
echo "========================================"
echo "  Test Complete"
echo "========================================"
echo ""

# Summary
if [ $commands_ok -eq 1 ] && [ -n "$tg_token" ] && [ -n "$or_key" ]; then
    echo "✓ All checks passed! Run: ./microbot.sh"
else
    echo "✗ Fix the issues above before starting"
fi
