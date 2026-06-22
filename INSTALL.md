# Install AgentWRT on OpenWrt

Run as root from the project directory:

```sh
chmod +x install.sh
./install.sh
```

Optional one-command setup:

```sh
TELEGRAM_TOKEN='123:abc' \
PROVIDER='deepseek' \
DEEPSEEK_KEY='sk-...' \
UI_PASSWORD='change-me' \
./install.sh
```

OpenRouter example:

```sh
TELEGRAM_TOKEN='123:abc' \
PROVIDER='openrouter' \
OPENROUTER_KEY='sk-or-...' \
UI_PASSWORD='change-me' \
./install.sh
```

Useful commands:

```sh
/etc/init.d/agentwrt restart
/etc/init.d/agentwrt-ui restart
/etc/init.d/agentwrt status
/etc/init.d/agentwrt-ui status
logread -f | grep agentwrt
```

Web UI:

```txt
http://<router-ip>:8080
```
