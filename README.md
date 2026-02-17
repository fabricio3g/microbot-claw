# MicroBot-Claw

AI-powered Telegram bot for OpenWrt routers. MicroPython implementation with Shell tool backends. REACT agent loop with tools, scheduling (including agent/planning), web crawl

## Prerequisites

Connect to your router via SSH. The installer will handle dependencies, but you can install them manually if needed:

```bash
# SSH into router
ssh root@ROUTER_IP

# Optional: install required packages manually
opkg update
opkg install curl micropython jsonfilter openssh-server
```

## Quick Start

```bash
# 1. Copy files to router (from your local machine)
scp -r microbot-ash root@ROUTER_IP:/mnt/usb/microbot-ash   # or /root/microbot-ash

# 2. SSH into router
ssh root@ROUTER_IP

# 3. Run installer (uses current directory as install dir)
cd /mnt/usb/microbot-ash
chmod +x *.sh
./install.sh

# 4. Open the web UI and set tg_token + LLM keys (restart bot needed)
http://ROUTER_IP:8080
```

The bot and UI start even without `tg_token` or LLM API keys. Set them in the Web UI; the bot will pick them up within ~15 seconds.

## Running

### Services (created by install.sh)

The installer creates four procd services and writes full paths into init.d so they work at boot from any directory:

| Service | Description |
|---------|-------------|
| microbot-claw | Main Telegram bot (polling) |
| microbot-claw-ui | Web config UI (port 8080) |



```bash
# Start / stop / restart
/etc/init.d/microbot-claw start
/etc/init.d/microbot-claw stop
/etc/init.d/microbot-claw restart

/etc/init.d/microbot-claw-ui start
/etc/init.d/microbot-claw-ui stop


# Check status (if start shows nothing)
/etc/init.d/microbot-claw status
/etc/init.d/microbot-claw-ui status

# Logs
logread -f | grep microbot
```

### Manual (foreground)

```bash
cd /mnt/usb/microbot-ash   # or your install dir
export MICROBOT_INSTALL_DIR=$(pwd)
micropython microbot.py
micropython ui_server.py
```

### Stopping

- Foreground: `Ctrl+C`
- Services: `killall micropython` (stops all micropython processes) or use `/etc/init.d/microbot-claw stop` etc.

## Configuration

**Recommended:** Set everything in the Web UI (http://ROUTER_IP:8080). The UI writes to `data/config.json`. You can also edit that file directly.

Required for Telegram + LLM:

- **tg_token** – Telegram bot token from @BotFather
- **openrouter_key** (or **api_key** for Anthropic) – LLM API key

Optional:

- **provider** – `openrouter` or `anthropic`
- **openrouter_model** / **model** – model name
- **enable_selector** – `true` for low-RAM fast tool selection
- **selector_max_tokens** – cap for selector response
- **crawl_allow_domains** – comma list for web_crawl


Config file location: under install dir `data/config.json` (e.g. `/mnt/usb/microbot-ash/data/config.json`) or `/data/config.json` if using system data dir.

## Web UI (Recommended)

After install, open:

```
http://ROUTER_IP:8080
```

- Set **tg_token** and **LLM keys** (openrouter_key or api_key); the bot picks them up without restart.
- Set a UI password on first visit (stored as salted hash: `ui_pass_salt` + `ui_pass_hash`).
- Use **Restart Bot** to restart the microbot-claw service.
- Use `/plugins` to enable/disable plugins; `/memory`, `/personality`, `/skills`, `/skills_usage` for memory, persona, and skills.
- Webhooks: `/webhook/generic?token=WEBHOOK_TOKEN`, `/webhook/slack?token=SLACK_WEBHOOK_TOKEN`.

## Uninstall

From your install directory:

```bash
cd /mnt/usb/microbot-ash   # or your install dir
./uninstall.sh
```

Keep data: `./uninstall.sh --keep-data`

## Get API Keys

- **Telegram**: @BotFather on Telegram → `/newbot`
- **OpenRouter**: https://openrouter.ai/keys (works with Claude, GPT-4, Gemini, Llama)
- **Anthropic**: https://console.anthropic.com/ (Claude only)

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start conversation |
| `/clear` | Clear history |

## Available Tools

See **skills.md** for the full reference. Summary:

**Core:** `get_current_time`, `web_search`, `scrape_web`, `read_file` / `write_file` / `edit_file` / `list_dir`, `system_info`, `network_status`, `run_command`, `get_weather`, `http_request`, `download_file`,  `list_services` / `restart_service`, `set_schedule` / `list_schedules` / `remove_schedule`, `save_memory`, `set_probe`, `set_timezone`.

**Plugins (plugins/*.json + *.sh):** e.g. `web_crawl`, `deep_search`, `get_news`, `get_exchange_rate`, `wikipedia_summary`, `hacker_news_top`, `ping_host`, `disk_usage`, `get_uptime`, `log_tail`, `dns_lookup`, `wifi_scan`, `get_sys_health`, etc.

## Example Queries

- "What's the system status?" / "Show me connected network devices"
- "Run `logread | tail -20`" / "What's the weather in Tokyo?"
- "Restart the firewall" / "Write a note to /data/notes.txt"
- "Search for latest OpenWrt news" / "When does River play?"
- "Remind me every day at 9am to check logs"
- "Every day at 8am run the agent: Summarize overnight news and weather for Buenos Aires"
- "Save that I prefer dark mode"

## Scheduling

**Natural language:** "every day at 9am", "every weekday at 18:30", "every 15 minutes", "tomorrow at 9am", "in 30 minutes", "at 14:00". Or use 5-field cron.

**Schedule types (set_schedule `type`):**

| Type | Description |
|------|-------------|
| `reminder` / `msg` | Recurring message |
| `once` | One-time message |
| `cmd` | Run shell command each time |
| `tool` | Run one tool each time (content: `tool_name args` or `tool_name|json`) |
| `once_tool` | Run tool once, then remove schedule |
| `probe` | Run check (e.g. `net_check`), alert only if non-empty |
| **`agent`** | At schedule time, run the full agent with content as the user prompt (agent can use tools and plan) |
| **`once_agent`** | Same as agent but remove after firing |

Examples:

- "Remind me every day at 9am" → type `reminder`, content = message.
- "Every day at 8am run the agent: Summarize overnight news and weather" → type `agent`, content = that prompt.
- "Every hour run net_check and alert if down" → type `probe`, content = `net_check`.


## Architecture

```
microbot.py (Python)
    │
    ├── LLMClient ────► OpenRouter / Anthropic API
    │
    ├── Agent (ReAct Loop)
    │   ├── Think  → Send to LLM
    │   ├── Act    → Detect & execute tool
    │   └── Observe → Feed result back
    │
    └── Tools ────────► Shell scripts (tools.sh)
                         │
                         ├── tool_web_search
                         ├── tool_system_info
                         ├── tool_run_command
                         └── ... (20+ tools)
```

## Files

```
<install_dir>/  (e.g. /mnt/usb/microbot-ash or /root/microbot-ash)
├── microbot.py        # Main bot (MicroPython)
├── ui_server.py       # Web UI
├── config.sh          # Config loader
├── tools.sh           # Tool functions (shell)
├── skills.sh          # Skill loader
├── install.sh         # Installer (creates init.d with full paths)
├── uninstall.sh       # Uninstaller
├── test.sh            # Test script
├── new_tool.sh        # Tool scaffolder
├── skills.md          # Full tools/skills reference
└── plugins/           # Plugin modules (*.json + *.sh)
    ├── web_crawl.sh, web_crawl.json
    ├── exchange.sh, exchange.json
    └── ...

<install_dir>/data/  (or /data/ if using system data)
├── config.json       # Configuration (editable via UI)
├── memory/           # Long-term memory (MEMORY.md, summaries)
├── config/           # Personality (SOUL.md, USER.md)
├── sessions/         # Chat history
├── uploads/          # User-uploaded files per chat (photos, docs, etc.)
│   └── <chat_id>/
│       ├── photo/
│       ├── documents/
│       └── ...
└── schedules.txt     # Scheduled tasks (cron|type|content)
```

Init scripts are written by `install.sh` into `/etc/init.d/microbot-claw`, `microbot-claw-ui`,  with full paths so they work at boot.

## Requirements

- OpenWrt 21.02+
- **curl** - `opkg install curl`
- **micropython** - `opkg install micropython`
- wget (built-in)
- jsonfilter (built-in)

## Config Options

- `wifi_reset_enable`: `"true"`/`"false"` to allow WiFi radio reset on connectivity loss.
- `wifi_reset_radio`: radio to reset (e.g., `radio0`).
- `schedule_catchup_minutes`: how many minutes to catch up missed schedules (default `5`).
- `schedule_log`: `"true"`/`"false"` to log scheduler activity to `/data/logs/scheduler.log`.
- `allow_llm_summary`: `"true"`/`"false"` to enable LLM-based history summaries.
- `openrouter_model_fallback`: fallback model for OpenRouter on errors.
- `model_fallback`: fallback model for Anthropic on errors.
- `llm_max_retries`: retry count per model.
- `llm_retry_backoff_ms`: backoff between retries.
- `tool_allowlist`: comma list of allowed tool names (empty = allow all).
- `tool_rate_limit_per_min`: max tool calls per minute.
- `tool_rate_limit_burst`: burst allowance for tool calls.
- `enabled_plugins`: list of enabled plugin IDs (plugin filenames without `.sh`/`.json`, empty = all enabled).
- `crawl_allow_domains`: optional comma list of allowed crawl domains.
- `inbox_check_interval`: seconds between inbox checks for webhooks.
- `routing_enabled`: `"true"`/`"false"` to enable smart routing tiers.
- `routing_long_message_chars`: length threshold for deep tier.
- `routing_deep_keywords`: comma list of deep-tier keywords.
- `routing_fast_tokens`, `routing_balanced_tokens`, `routing_deep_tokens`: max token budgets per tier.
- `routing_fast_temp`, `routing_balanced_temp`, `routing_deep_temp`: temperature per tier.
- `delegation_enabled`: `"true"`/`"false"` to enable in-process delegation.
- `delegation_max_calls`: max role calls (1-3).
- `delegation_max_tokens_per_call`: token cap per role call.
- `delegation_timeout_sec`: soft timeout for delegation pipeline.
- `delegation_keywords`: comma list of delegation trigger keywords.

## Troubleshooting

```bash
# Test setup
./test.sh

# Check service status (if start shows nothing)
/etc/init.d/microbot-claw status
/etc/init.d/microbot-claw-ui status

# Scheduler: use list_schedules tool; optional log: schedule_log=true, /data/logs/scheduler.log

# Test Telegram API
curl -k -s "https://api.telegram.org/botYOUR_TOKEN/getMe"

# Run manually for debugging (from install dir)
cd /mnt/usb/microbot-ash && MICROBOT_INSTALL_DIR=$(pwd) micropython microbot.py
cd /mnt/usb/microbot-ash && MICROBOT_INSTALL_DIR=$(pwd) micropython ui_server.py
```

## License

MIT

## Tool Scaffolder

Create a new plugin quickly:

```bash
./new_tool.sh
```
