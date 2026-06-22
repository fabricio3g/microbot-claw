# Configuration Reference

All options live in `data/config.json`. Set them via the Web UI (`http://ROUTER_IP:8080`), via env vars during install, or by editing the file directly.

## Required

| Key | Description | Example |
|-----|-------------|---------|
| `tg_token` | Telegram bot token from @BotFather | `123:abc` |
| `provider` | LLM provider | `openrouter` or `deepseek` |
| `openrouter_key` | OpenRouter API key | `sk-or-...` |
| `deepseek_key` | DeepSeek API key | `sk-...` |

Only one LLM key is needed (matching your `provider`).

## LLM

| Key | Default | Description |
|-----|---------|-------------|
| `openrouter_model` | `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter model |
| `deepseek_model` | `deepseek-v4-flash` | DeepSeek model |
| `deepseek_base_url` | `https://api.deepseek.com` | DeepSeek API base URL |
| `deepseek_thinking` | `false` | Enable DeepSeek thinking mode |
| `deepseek_reasoning_effort` | `high` | DeepSeek reasoning effort |
| `openrouter_model_fallback` | `""` | Fallback model for OpenRouter on errors |
| `deepseek_model_fallback` | `""` | Fallback model for DeepSeek on errors |
| `llm_max_retries` | `2` | Retries per model call |
| `llm_retry_backoff_ms` | `500` | Backoff between retries (ms) |
| `enable_selector` | `true` | Low-RAM fast tool selection |
| `selector_max_tokens` | `64` | Max tokens for selector response |
| `max_iterations` | `8` | Max ReAct loop iterations |
| `one_tool_only` | `false` | Force single tool call per turn |
| `allow_llm_summary` | `false` | Use LLM for history summaries |
| `send_wait_messages` | `false` | Send "typing..." messages |

## Routing

| Key | Default | Description |
|-----|---------|-------------|
| `routing_enabled` | `true` | Enable smart tiered routing |
| `routing_long_message_chars` | `500` | Length threshold for deep tier |
| `routing_deep_keywords` | `design,architecture,refactor,proposal,spec,plan,analysis` | Keywords triggering deep tier |
| `routing_fast_tokens` | `256` | Max tokens for fast tier |
| `routing_balanced_tokens` | `512` | Max tokens for balanced tier |
| `routing_deep_tokens` | `1024` | Max tokens for deep tier |
| `routing_fast_temp` | `0.2` | Temperature for fast tier |
| `routing_balanced_temp` | `0.4` | Temperature for balanced tier |
| `routing_deep_temp` | `0.7` | Temperature for deep tier |

## Delegation

| Key | Default | Description |
|-----|---------|-------------|
| `delegation_enabled` | `true` | Enable in-process role delegation |
| `delegation_max_calls` | `3` | Max delegation role calls (1-3) |
| `delegation_max_tokens_per_call` | `256` | Token cap per role call |
| `delegation_timeout_sec` | `12` | Soft timeout (seconds) |
| `delegation_keywords` | `plan,design,architecture,proposal,spec` | Trigger keywords |

## Scheduling

| Key | Default | Description |
|-----|---------|-------------|
| `schedule_catchup_minutes` | `5` | Catch up missed schedules (minutes) |
| `schedule_max_fires_per_tick` | `1` | Max fires per scheduler tick |
| `schedule_log` | `false` | Log scheduler to `/data/logs/scheduler.log` |

## Tools

| Key | Default | Description |
|-----|---------|-------------|
| `tool_allowlist` | `""` | Comma-separated allowed tools (empty = all) |
| `tool_rate_limit_per_min` | `10` | Max tool calls per minute |
| `tool_rate_limit_burst` | `3` | Burst allowance |
| `crawl_allow_domains` | `""` | Comma-separated allowed crawl domains |
| `enabled_plugins` | `[]` | Enabled plugin IDs (empty = all) |

## Web UI

| Key | Default | Description |
|-----|---------|-------------|
| `ui_enabled` | `true` | Enable web UI |
| `ui_bind` | `0.0.0.0` | UI bind address |
| `ui_port` | `8080` | UI port |
| `ui_pass_salt` | `""` | Password salt (set via UI) |
| `ui_pass_hash` | `""` | Password hash (set via UI) |

## Webhooks

| Key | Default | Description |
|-----|---------|-------------|
| `webhook_token` | `""` | Token for generic webhook |
| `slack_bot_token` | `""` | Slack bot token |
| `slack_webhook_token` | `""` | Token for Slack webhook |
| `inbox_check_interval` | `2` | Seconds between inbox checks |

## Network & Hardware

| Key | Default | Description |
|-----|---------|-------------|
| `wifi_ssid` | `""` | WiFi SSID |
| `wifi_pass` | `""` | WiFi password |
| `wifi_reset_enable` | `true` | Auto-reset WiFi on connectivity loss |
| `wifi_reset_radio` | `radio0` | Radio to reset |
| `proxy_host` | `""` | HTTP proxy host |
| `proxy_port` | `""` | HTTP proxy port |

## Other

| Key | Default | Description |
|-----|---------|-------------|
| `timezone` | `UTC` | IANA timezone (e.g. `Europe/Madrid`) |
| `weather_default_location` | `""` | Default weather location |
| `search_key` | `""` | Search API key (if needed) |
| `gmail_user` | `""` | Gmail username |
| `gmail_app_password` | `""` | Gmail app password |
| `http_port` | `8080` | HTTP server port |
| `log_level` | `quiet` | Log verbosity |
| `debug_log` | `false` | Enable debug logging |
| `verbose_log` | `false` | Enable verbose logging |
