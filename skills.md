# MicroBot-Claw Skills Reference

This document lists all available tools (skills) for the agent. Use them via the REACT loop with:

`TOOL:tool_name:{"arg": "value"}`

---

## Core Tools (built-in)

| Tool | Description | Args |
|------|-------------|------|
| **web_search** | Search the web | `query` |
| **scrape_web** | Fetch and extract text from a URL | `url` |
| **get_current_time** | Get current date/time (timezone-aware) | — |
| **read_file** | Read file contents | `path` |
| **write_file** | Write content to a file | `path`, `content` |
| **edit_file** | Replace text in a file | `path`, `old_string`, `new_string` |
| **list_dir** | List files in a directory | `prefix` (optional path) |
| **system_info** | System stats (CPU, RAM, disk) | — |
| **network_status** | Network info (IP, WiFi) | — |
| **run_command** | Run a shell command | `command` |
| **list_services** | List init.d / procd services | — |
| **restart_service** | Restart a service | `name` (e.g. microbot-claw) |
| **get_weather** | Get weather for a location | `location` |
| **http_request** | HTTP request | `url`, `method`, `body` |
| **download_file** | Download file from URL | `url`, `filename` |
| **start_research_job** | Queue background research | `query`, `chat_id`, `max_pages`, `max_depth` |
| **set_schedule** | Schedule task or reminder | `cron_expression` or natural time, `content`, `type`: reminder, once, cmd, tool, once_tool, probe, **agent**, **once_agent** |
| **list_schedules** | List active schedules | — |
| **remove_schedule** | Remove a schedule | `id` |
| **save_memory** | Save a fact to long-term memory | `fact` |

---

## Plugin Skills (plugins/*.json + plugins/*.sh)

Loaded from `plugins/` when `SCRIPT_DIR` and config are set. Empty `enabled_plugins` = all enabled.

### System / OpenWrt

| Tool | Description | Args |
|------|-------------|------|
| **ping_host** | Ping host, return latency summary | `host`, `count` (optional, default 3) |
| **disk_usage** | Show disk usage (df) | `path` (optional mount/path) |
| **get_uptime** | System uptime | — |
| **log_tail** | Last N lines of a log file | `path`, `lines` (optional, default 20). Use `path: "syslog"` for OpenWrt logread. |
| **dns_lookup** | Resolve hostname to IP | `host` |
| **wifi_scan** | Scan WiFi networks (iw/iwlist) | `interface` (optional, e.g. wlan0) |

### Web / content

| Tool | Description | Args |
|------|-------------|------|
| **web_crawl** | Crawl URLs, extract text | `url`, `max_pages`, `max_depth`, `same_domain`, etc. |
| **get_news** | Headlines from news sources | `source` (e.g. lanacion, bbc), `topic` |
| **wikipedia_summary** | Short Wikipedia summary for a topic | `query` (or `title`) |
| **hacker_news_top** | Top stories from Hacker News | `limit` (optional, default 5, max 20) |
| **world_time** | Current time by timezone or by IP (World Time API) | `timezone` (optional, e.g. Europe/London); omit for time by IP |
| **get_exchange_rate** | Convert amount between currencies (Frankfurter). LLM decides from/to/amount from user question. | `from_currency` (default USD), `to_currency` (e.g. EUR, GBP), `amount` (default 1) |

### Other plugins

- **deep_search** – Deep search (if enabled)
- **gmail**, **hass**, **notion**, **probe**, **hardware_wifi**, **hardware_health** – See `plugins/<name>.json` for args.

---

## Usage in the agent

1. **One tool per message** when calling a tool.
2. **Format**: `TOOL:tool_name:{"arg": "value"}` — no other text on that line.
3. After a `[Tool Result: tool_name]` the agent can call another tool or reply to the user.
4. Long results are truncated (~2000 chars); use **save_memory** for important facts.
5. Scheduling: use **set_schedule** with natural language or cron. Types: `reminder`/`msg` (recurring message), `once` (one-time message), `cmd` (run shell command), `tool` (run one tool; content = "tool_name args" or "tool_name|json"), `once_tool` (run tool once then remove), `probe` (run check, alert only if non-empty), **`agent`** (at schedule time run the full agent with content as the user prompt—agent can use tools and plan), **`once_agent`** (same as agent but remove after firing).

---

## Adding a new skill

1. Create `plugins/<name>.json` with `name`, `description`, and optional `args`.
2. Create `plugins/<name>.sh` with a function `tool_<name>()` that takes one argument (JSON string). Parse with `jsonfilter` or grep/sed.
3. Restart the bot or rely on next `skill_list_names` / `skill_list_descriptions` load so the tool appears in the prompt.
