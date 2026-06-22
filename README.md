<p align="center"><img src="logo.svg" alt="AgentWRT" width="400"></p>

# AgentWRT

AI-powered Telegram bot that runs on your OpenWrt router. Think, schedule, crawl, and control your network — all from chat.

- **Telegram bot** with a ReAct agent loop (Think → Act → Observe)
- **20+ tools** backed by shell scripts: web search, file I/O, system info, weather, HTTP, cron scheduling, network status
- **Web UI** on port 8080 for config, plugins, memory, and persona
- **18 plugins**: news, exchange rates, Wikipedia, web crawl, deep search, Gmail, Notion, Home Assistant, hardware health, WiFi scan, DNS lookup, ping, disk usage, log tail, uptime, hacker news, world time, router capabilities
- **Webhooks**: Slack and generic HTTP webhooks for external triggers
- **Smart routing**: 3-tier (fast/balanced/deep) with automatic keyword detection
- **Delegation**: in-process role delegation pipeline

## Prerequisites

Connect to your router via SSH. The installer handles dependencies, but you can install them manually if needed:

```bash
ssh root@ROUTER_IP

# Optional: install packages manually
opkg update
opkg install curl micropython jsonfilter openssh-server
```

## Quick Start

One command on the router:

```bash
ssh root@ROUTER_IP
cd /mnt/usb/agentwrt-ash && chmod +x *.sh

# All-in-one install with keys:
TELEGRAM_TOKEN='123:abc' \
PROVIDER='deepseek' \
DEEPSEEK_KEY='sk-...' \
UI_PASSWORD='change-me' \
./install.sh
```

Or with OpenRouter:

```bash
TELEGRAM_TOKEN='123:abc' \
PROVIDER='openrouter' \
OPENROUTER_KEY='sk-or-...' \
UI_PASSWORD='change-me' \
./install.sh
```

After install, open `http://ROUTER_IP:8080` to fine-tune. The bot starts automatically.

Get tokens: [@BotFather](https://t.me/BotFather) for Telegram · [OpenRouter](https://openrouter.ai/keys) · [DeepSeek](https://platform.deepseek.com/api_keys)

## What `install.sh` Does

1. Installs dependencies: `curl`, `micropython`, `wget`, `jsonfilter`, `openssh-server`
2. Creates data directories: `data/config/`, `data/memory/`, `data/sessions/`
3. Generates `data/config.json` from defaults + any env vars passed
4. Writes two procd services (`agentwrt`, `agentwrt-ui`) into `/etc/init.d/`
5. Enables and starts both services

Env vars accepted: `TELEGRAM_TOKEN`, `PROVIDER`, `OPENROUTER_KEY`, `DEEPSEEK_KEY`, `DEEPSEEK_MODEL`, `TIMEZONE`, `UI_PASSWORD`

## Configuration

Only 3 things are required. Set them via env vars (above) or in `data/config.json`:

| Key | Description |
|-----|-------------|
| `tg_token` | Telegram bot token |
| `provider` | `openrouter` or `deepseek` |
| `openrouter_key` / `deepseek_key` | API key for your provider |

Everything else has sensible defaults. [Full config reference →](CONFIG.md)

## Features

### Tools (20+ built-in)
`web_search`, `web_crawl`, `scrape_web`, `read_file`, `write_file`, `edit_file`, `list_dir`, `system_info`, `network_status`, `run_command`, `http_request`, `download_file`, `get_weather`, `list_services`, `restart_service`, `save_memory`, `get_current_time`, `set_timezone`, `set_schedule`, `list_schedules`, `remove_schedule`, `set_probe`

### Plugins (18 modules in `plugins/`)
`deep_search`, `disk_usage`, `dns_lookup`, `exchange`, `get_uptime`, `gmail`, `hacker_news`, `hardware` (health + WiFi), `hass` (Home Assistant), `log_tail`, `news`, `notion`, `ping_host`, `probe`, `router_capabilities`, `web_crawl`, `wifi_scan`, `wikipedia`, `world_time`

Enable/disable from the Web UI at `/plugins`. Scaffold new ones with `./new_tool.sh`.

### Scheduling
Natural language: *"every day at 9am"*, *"every 15 minutes"*, *"tomorrow at 14:00"*. Supports reminders, one-shot messages, shell commands, tool runs, probes (alert on condition), and full agent invocations (*"every morning summarize news and weather"*).

### Webhooks
- **Slack**: `/webhook/slack?token=SLACK_WEBHOOK_TOKEN`
- **Generic**: `/webhook/generic?token=WEBHOOK_TOKEN`

### Smart Routing
Messages auto-classified into 3 tiers by keyword + length:
- **Fast** (256 tokens, temp 0.2) — simple queries
- **Balanced** (512 tokens, temp 0.4) — typical requests
- **Deep** (1024 tokens, temp 0.7) — complex, design, planning

Configurable: `routing_enabled`, `routing_deep_keywords`, `routing_long_message_chars`, token/temp per tier.

### Delegation
In-process role delegation for complex tasks. Configurable: `delegation_enabled`, `delegation_max_calls`, `delegation_keywords`.

## Running

```bash
/etc/init.d/agentwrt start|stop|restart|status
/etc/init.d/agentwrt-ui start|stop|restart|status

# Logs
logread -f | grep agentwrt

# Test setup
./test.sh
```

## Project Structure

```
agentwrt-ash/
├── agentwrt.py           # Main bot (MicroPython, ~3700 lines)
├── ui_server.py          # Web config UI (port 8080)
├── config.sh             # Config loader (jsonfilter-based)
├── tools.sh              # 20+ shell tool backends
├── skills.sh             # Skill loader
├── install.sh            # Installer
├── uninstall.sh          # Uninstaller
├── test.sh               # Self-test
├── new_tool.sh           # Plugin scaffolder
├── cron_dispatch.sh      # Cron job dispatcher
├── skills.md             # Full tools/skills reference
├── INSTALL.md            # Detailed install guide
├── core/
│   ├── __init__.py
│   ├── telegram.py       # Telegram bot module
│   └── util.py           # Utilities
├── plugins/              # 18 plugin pairs (*.json + *.sh)
│   ├── _template.json    # Scaffold templates
│   ├── _template.sh
│   └── ...
├── data/                 # Runtime data (created by install.sh)
│   ├── config.json
│   ├── config/
│   ├── memory/
│   ├── sessions/
│   └── schedules.txt
└── test/
    └── test_compatibility.py
```

## Uninstall

```bash
cd /mnt/usb/agentwrt-ash && ./uninstall.sh
# Keep your data:
./uninstall.sh --keep-data
```

## Requirements

- OpenWrt 21.02+
- `curl`, `micropython`, `wget`, `jsonfilter` (installed automatically by `install.sh`)

## License

MIT
