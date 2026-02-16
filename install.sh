#!/bin/sh
# MicroBot-Claw (Ash Shell) - OpenWrt Installer

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
[ -z "$SCRIPT_DIR" ] && SCRIPT_DIR="$(pwd)"
INSTALL_DIR="$SCRIPT_DIR"
if [ -d "${INSTALL_DIR}/data" ]; then
    DATA_DIR="${INSTALL_DIR}/data"
else
    DATA_DIR="/data"
fi
CONFIG_FILE="${DATA_DIR}/config.json"

echo "=========================================="
echo "  MicroBot-Claw (Shell) - OpenWrt Installer"
echo "=========================================="

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Install dependencies (full)
echo "[1/6] Installing dependencies..."

need_pkg=0
for bin in curl micropython wget jsonfilter sshd; do
    if ! command -v "$bin" >/dev/null 2>&1; then
        need_pkg=1
        break
    fi
done

if [ "$need_pkg" -eq 1 ]; then
    opkg update

    ensure_pkg() {
        if ! command -v "$1" >/dev/null 2>&1; then
            opkg install "$2"
        fi
    }

    ensure_pkg curl curl
    ensure_pkg micropython micropython
    ensure_pkg wget wget
    ensure_pkg jsonfilter jsonfilter

    # scp server is provided by openssh-server
    if ! command -v sshd >/dev/null 2>&1; then
        opkg install openssh-server
    fi
else
    echo "Dependencies already installed. Skipping."
fi

# Enable/start sshd if available
if [ -x /etc/init.d/sshd ]; then
    /etc/init.d/sshd enable
    /etc/init.d/sshd start
fi

# Create directories
echo "[2/6] Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/config"
mkdir -p "$DATA_DIR/memory"
mkdir -p "$DATA_DIR/sessions"

# Use current working directory as install dir
echo "[3/6] Using install dir: $INSTALL_DIR"
chmod +x "$INSTALL_DIR"/*.sh 2>/dev/null || true

# Copy config template if exists (only when using /data)
if [ "$DATA_DIR" = "/data" ] && [ -f "$INSTALL_DIR/data/config.json" ]; then
    cp "$INSTALL_DIR/data/config.json" "$DATA_DIR/config.json.template"
fi

# Create default config if not exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[4/6] Creating default configuration..."
    cat > "$CONFIG_FILE" << 'EOF'
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
    "http_port": "8080",
    "ui_enabled": "true",
    "ui_bind": "0.0.0.0",
    "ui_port": "8080",
    "ui_pass_salt": "",
    "ui_pass_hash": "",
    "weather_default_location": ""
}
EOF
    echo "Created $CONFIG_FILE"
else
    echo "[4/6] Config file already exists, keeping it"
fi

# UI password (set in Web UI on first visit)
echo "[5/6] UI password..."
UI_SALT="$(jsonfilter -i "$CONFIG_FILE" -e '@.ui_pass_salt' 2>/dev/null)"
UI_HASH="$(jsonfilter -i "$CONFIG_FILE" -e '@.ui_pass_hash' 2>/dev/null)"

if [ -z "$UI_SALT" ] || [ -z "$UI_HASH" ]; then
    echo "UI password not set. Open the Web UI and set it there."
else
    chmod 600 "$CONFIG_FILE"
fi

# Create init.d services (INSTALL_DIR expanded at install so procd gets full paths)
echo "[6/6] Creating startup services..."
INSTALL_DIR_ESC="$(echo "$INSTALL_DIR" | sed "s/'/'\\\\''/g")"
CMD_CLAW="cd '$INSTALL_DIR_ESC' && export MICROBOT_INSTALL_DIR='$INSTALL_DIR_ESC' && exec /usr/bin/micropython '$INSTALL_DIR_ESC/microbot.py'"
CMD_UI="cd '$INSTALL_DIR_ESC' && export MICROBOT_INSTALL_DIR='$INSTALL_DIR_ESC' && exec /usr/bin/micropython '$INSTALL_DIR_ESC/ui_server.py'"
CMD_RESEARCH="cd '$INSTALL_DIR_ESC' && export MICROBOT_INSTALL_DIR='$INSTALL_DIR_ESC' && exec /usr/bin/micropython '$INSTALL_DIR_ESC/research_worker.py'"
CMD_MATRIX="cd '$INSTALL_DIR_ESC' && export MICROBOT_INSTALL_DIR='$INSTALL_DIR_ESC' && exec /usr/bin/micropython '$INSTALL_DIR_ESC/matrix_worker.py'"

cat > /etc/init.d/microbot-claw << SVCEOF
#!/bin/sh /etc/rc.common

START=99
STOP=10

USE_PROCD=1

start_service() {
    procd_open_instance
    procd_set_param command /bin/sh -c "$CMD_CLAW"
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param respawn \${respawn_threshold:-3600} \${respawn_timeout:-5} \${respawn_retry:-5}
    procd_close_instance
}

stop_service() {
    killall -9 micropython 2>/dev/null
}
SVCEOF

cat > /etc/init.d/microbot-claw-ui << SVCEOF
#!/bin/sh /etc/rc.common

START=98
STOP=10

USE_PROCD=1

start_service() {
    procd_open_instance
    procd_set_param command /bin/sh -c "$CMD_UI"
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param respawn \${respawn_threshold:-3600} \${respawn_timeout:-5} \${respawn_retry:-5}
    procd_close_instance
}

stop_service() {
    killall -9 micropython 2>/dev/null
}
SVCEOF

cat > /etc/init.d/microbot-claw-research << SVCEOF
#!/bin/sh /etc/rc.common

START=97
STOP=10

USE_PROCD=1

start_service() {
    procd_open_instance
    procd_set_param command /bin/sh -c "$CMD_RESEARCH"
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param respawn \${respawn_threshold:-3600} \${respawn_timeout:-5} \${respawn_retry:-5}
    procd_close_instance
}

stop_service() {
    killall -9 micropython 2>/dev/null
}
SVCEOF

cat > /etc/init.d/microbot-claw-matrix << SVCEOF
#!/bin/sh /etc/rc.common

START=96
STOP=10

USE_PROCD=1

start_service() {
    procd_open_instance
    procd_set_param command /bin/sh -c "$CMD_MATRIX"
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param respawn \${respawn_threshold:-3600} \${respawn_timeout:-5} \${respawn_retry:-5}
    procd_close_instance
}

stop_service() {
    killall -9 micropython 2>/dev/null
}
SVCEOF

chmod +x /etc/init.d/microbot-claw /etc/init.d/microbot-claw-ui /etc/init.d/microbot-claw-research /etc/init.d/microbot-claw-matrix
/etc/init.d/microbot-claw enable
/etc/init.d/microbot-claw-ui enable
/etc/init.d/microbot-claw-research enable
/etc/init.d/microbot-claw-matrix enable

echo "Starting services..."
/etc/init.d/microbot-claw start
/etc/init.d/microbot-claw-ui start
/etc/init.d/microbot-claw-research start
/etc/init.d/microbot-claw-matrix start

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "Config file: $CONFIG_FILE"
echo ""
echo "Edit with:"
echo "  vi $DATA_DIR/config.json"
echo ""
echo "Required fields:"
echo "  tg_token        - Telegram bot token from @BotFather"
echo "  openrouter_key  - OpenRouter API key (or api_key for Anthropic)"
echo ""
echo "Commands:"
echo "  Bot Start:   /etc/init.d/microbot-claw start"
echo "  Bot Stop:    /etc/init.d/microbot-claw stop"
echo "  Bot Restart: /etc/init.d/microbot-claw restart"
echo "  UI Start:    /etc/init.d/microbot-claw-ui start"
echo "  UI Stop:     /etc/init.d/microbot-claw-ui stop"
echo "  Research Worker Start: /etc/init.d/microbot-claw-research start"
echo "  Research Worker Stop:  /etc/init.d/microbot-claw-research stop"
echo "  Check status: /etc/init.d/microbot-claw status  (or microbot-claw-ui, etc.)"
echo "  Logs:        logread -f | grep microbot"
echo ""
echo "If start shows nothing, check: /etc/init.d/microbot-claw status"
echo "Or run directly: cd ${INSTALL_DIR} && MICROBOT_INSTALL_DIR=${INSTALL_DIR} micropython microbot.py"
echo "  UI directly:  cd ${INSTALL_DIR} && MICROBOT_INSTALL_DIR=${INSTALL_DIR} micropython ui_server.py"
echo ""
