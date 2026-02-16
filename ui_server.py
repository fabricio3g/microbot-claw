#!/usr/bin/env python3
"""
MicroBot-Claw UI - Minimal Web Config for OpenWrt (MicroPython-friendly)
"""

print("\n\n!!! STARTING MICROBOT-CLAW UI \n")

try:
    import usocket as socket
except ImportError:
    import socket

try:
    import ujson as json
except ImportError:
    import json

try:
    import uhashlib as hashlib
except ImportError:
    import hashlib

try:
    import ubinascii as binascii
except ImportError:
    import binascii

try:
    import uos as os
except ImportError:
    import os

try:
    import utime as time
except ImportError:
    import time


# ------------------ Helpers ------------------
class OSPath:
    def join(self, *args):
        return "/".join([str(a).rstrip("/") for a in args])
    def exists(self, path):
        try:
            os.stat(path)
            return True
        except:
            return False

Path = OSPath()


def run_command(cmd):
    if hasattr(os, "popen"):
        try:
            p = os.popen(cmd)
            out = p.read()
            p.close()
            return out.strip()
        except:
            pass
    if hasattr(os, "system"):
        try:
            os.system(cmd)
            return ""
        except:
            pass
    return ""


def mkdir_recursive(path):
    if Path.exists(path):
        return True
    if hasattr(os, "makedirs"):
        try:
            os.makedirs(path)
            return True
        except:
            pass
    parts = path.split("/")
    current = ""
    for part in parts:
        if part:
            current += "/" + part
            if not Path.exists(current):
                try:
                    os.mkdir(current)
                except:
                    pass
    return Path.exists(path)


def html_escape(s):
    s = str(s)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&#39;")
    return s


def parse_qs(body):
    data = {}
    if not body:
        return data
    parts = body.split("&")
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        k = url_decode(k)
        v = url_decode(v)
        data[k] = v
    return data


def url_decode(s):
    s = s.replace("+", " ")
    out = ""
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                out += chr(int(s[i+1:i+3], 16))
                i += 3
                continue
            except:
                pass
        out += s[i]
        i += 1
    return out


def parse_query(path):
    if "?" not in path:
        return path, {}
    p, q = path.split("?", 1)
    return p, parse_qs(q)


def sha256_hex(s):
    try:
        h = hashlib.sha256()
    except:
        h = hashlib.sha256()
    if isinstance(s, str):
        s = s.encode("utf-8")
    h.update(s)
    return binascii.hexlify(h.digest()).decode()


def get_script_dir():
    script_dir = "."
    try:
        if hasattr(os, "getenv"):
            env_dir = os.getenv("MICROBOT_INSTALL_DIR")
            if env_dir and Path.exists(Path.join(env_dir, "config.sh")):
                return env_dir
    except:
        pass
    try:
        if "__file__" in globals():
            p = __file__
            if "/" in p:
                script_dir = p.rsplit("/", 1)[0]
    except:
        pass
    try:
        if Path.exists("config.sh"):
            script_dir = "."
        elif hasattr(os, "getcwd"):
            cwd = os.getcwd()
            if cwd and Path.exists(Path.join(cwd, "config.sh")):
                script_dir = cwd
        else:
            pwd = run_command("pwd")
            if pwd and Path.exists(Path.join(pwd, "config.sh")):
                script_dir = pwd
    except:
        pass
    return script_dir


def load_config():
    script_dir = get_script_dir()
    possible = [
        Path.join(script_dir, "data", "config.json"),
        "data/config.json",
        "/data/config.json",
    ]
    config = {}
    found = ""
    for p in possible:
        if Path.exists(p):
            found = p
            try:
                with open(p, "r") as f:
                    config = json.load(f)
            except:
                config = {}
            break
    if not found:
        if not Path.exists("/data"):
            found = Path.join(script_dir, "data", "config.json")
        else:
            found = "/data/config.json"
    return config, found


def save_config(path, config):
    mkdir_recursive(path.rsplit("/", 1)[0])
    try:
        with open(path, "w") as f:
            f.write(json.dumps(config))
        return True
    except:
        return False


def _data_dir_from_config_path(config_path):
    if "/" in config_path:
        return config_path.rsplit("/", 1)[0]
    return "./data"


def _safe_path(base, rel):
    rel = rel.strip().lstrip("/")
    return base.rstrip("/") + "/" + rel


def read_text_file(path, max_len=20000):
    try:
        with open(path, "r") as f:
            data = f.read()
        if len(data) > max_len:
            data = data[:max_len]
        return data
    except:
        return ""


def write_text_file(path, content):
    try:
        mkdir_recursive(path.rsplit("/", 1)[0])
        with open(path, "w") as f:
            f.write(content)
        return True
    except:
        return False


def list_plugins():
    script_dir = get_script_dir()
    pdir = Path.join(script_dir, "plugins")
    plugins = []
    try:
        files = os.listdir(pdir)
    except:
        files = []
    for fn in files:
        if not fn.endswith(".json"):
            continue
        path = Path.join(pdir, fn)
        base = fn[:-5]
        name = base
        desc = ""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                name = data.get("name", name) or name
                desc = data.get("description", "") or ""
        except:
            pass
        plugins.append({"id": base, "name": name, "desc": desc, "file": fn})
    plugins.sort(key=lambda x: x.get("name", ""))
    return plugins


SESSION_TOKEN = ""

def check_auth(headers, config):
    global SESSION_TOKEN
    salt = config.get("ui_pass_salt", "")
    hsh = config.get("ui_pass_hash", "")
    if not salt or not hsh:
        return False
    cookie = headers.get("cookie", "")
    if cookie and "mb_session=" in cookie:
        try:
            parts = cookie.split("mb_session=")[1].split(";", 1)
            token = parts[0].strip()
            if token and SESSION_TOKEN and token == SESSION_TOKEN:
                return True
        except:
            pass
    return False


def _input_row(k, v):
    itype = "text"
    if "pass" in k or "token" in k or k.endswith("_key"):
        itype = "password"
    return (
        '<div class="row"><label>'
        + html_escape(k)
        + '</label><input type="'
        + itype
        + '" name="'
        + html_escape(k)
        + '" value="'
        + html_escape(v)
        + '"></div>'
    )


def build_sections(config):
    sections = [
        ("Telegram", ["tg_token"]),
        (
            "LLM",
            [
                "provider",
                "openrouter_key",
                "openrouter_model",
                "openrouter_model_fallback",
                "api_key",
                "model",
                "model_fallback",
                "max_tokens",
                "llm_max_retries",
                "llm_retry_backoff_ms",
                "routing_enabled",
                "routing_long_message_chars",
                "routing_deep_keywords",
                "routing_fast_tokens",
                "routing_balanced_tokens",
                "routing_deep_tokens",
                "routing_fast_temp",
                "routing_balanced_temp",
                "routing_deep_temp",
                "delegation_enabled",
                "delegation_max_calls",
                "delegation_max_tokens_per_call",
                "delegation_timeout_sec",
                "delegation_keywords",
                "enable_selector",
                "selector_max_tokens",
            ],
        ),
        ("Email", ["gmail_user", "gmail_app_password"]),
        (
            "Scheduler",
            [
                "schedule_check_interval",
                "schedule_catchup_minutes",
                "schedule_log",
            ],
        ),
        (
            "Tools",
            [
                "tool_allowlist",
                "tool_rate_limit_per_min",
                "tool_rate_limit_burst",
            ],
        ),
        ("Weather", ["weather_default_location"]),
        ("Crawler", ["crawl_allow_domains"]),
        (
            "Channels",
            [
                "webhook_token",
                "slack_webhook_token",
                "slack_bot_token",
            ],
        ),
        (
            "Network",
            [
                "wifi_ssid",
                "wifi_pass",
                "wifi_reset_enable",
                "wifi_reset_radio",
                "proxy_host",
                "proxy_port",
                "search_key",
            ],
        ),
        (
            "UI",
            [
                "ui_enabled",
                "ui_bind",
                "ui_port",
                "http_port",
                "ui_pass_salt",
                "ui_pass_hash",
            ],
        ),
        (
            "Advanced",
            [],
        ),
    ]

    known = set()
    for _, keys in sections:
        for k in keys:
            known.add(k)

    # Fill advanced with unknown keys
    adv_keys = []
    ignore_prefixes = ("matrix_", "research_")
    for k in config.keys():
        if k not in known:
            skip = False
            for p in ignore_prefixes:
                if k.startswith(p):
                    skip = True
                    break
            if not skip:
                adv_keys.append(k)
    adv_keys.sort()

    rows = []
    for title, keys in sections:
        if title == "Advanced":
            keys = adv_keys
        if not keys:
            continue
        rows.append('<div class="section"><h2>' + html_escape(title) + "</h2>")
        for k in keys:
            v = config.get(k, "")
            rows.append(_input_row(k, v))
        rows.append("</div>")
    return "\n".join(rows)


def has_ui_password(config):
    return bool(config.get("ui_pass_salt", "")) and bool(config.get("ui_pass_hash", ""))


def set_ui_password(config_path, config, password):
    salt = sha256_hex(str(time.time()))
    hsh = sha256_hex(salt + password)
    config["ui_pass_salt"] = salt
    config["ui_pass_hash"] = hsh
    return save_config(config_path, config)


def http_response(body, code=200, headers=None):
    if headers is None:
        headers = {}
    reason = "OK" if code == 200 else "Unauthorized"
    hdrs = [
        "HTTP/1.1 " + str(code) + " " + reason,
        "Content-Type: text/html; charset=utf-8",
        "Connection: close",
    ]
    for k in headers:
        hdrs.append(k + ": " + headers[k])
    hdrs.append("")
    hdrs.append(body)
    return "\r\n".join(hdrs)


def handle_client(conn, addr, config, config_path):
    try:
        conn.settimeout(4)
    except:
        pass
    try:
        req = conn.recv(4096)
    except:
        try:
            conn.close()
        except:
            pass
        return

    if not req:
        try:
            conn.close()
        except:
            pass
        return

    try:
        req_text = req.decode()
    except:
        req_text = str(req)

    lines = req_text.split("\r\n")
    if not lines:
        conn.close()
        return

    first = lines[0].split()
    method = first[0] if len(first) > 0 else "GET"
    raw_path = first[1] if len(first) > 1 else "/"
    path, query = parse_query(raw_path)

    headers = {}
    i = 1
    while i < len(lines) and lines[i]:
        if ":" in lines[i]:
            k, v = lines[i].split(":", 1)
            headers[k.strip().lower()] = v.strip()
        i += 1

    # Webhook handler (no UI auth; uses token)
    if path.startswith("/webhook/"):
        channel = path.split("/", 2)[2] if len(path.split("/")) >= 3 else ""
        # Token auth
        token = ""
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
        if not token:
            token = query.get("token", "")

        # Per-channel tokens
        needed = ""
        if channel == "slack":
            needed = config.get("slack_webhook_token", "")
        else:
            needed = config.get("webhook_token", "")

        if not needed or token != needed:
            conn.send(http_response("Unauthorized", code=401))
            conn.close()
            return

        content_length = 0
        try:
            content_length = int(headers.get("content-length", "0"))
        except:
            content_length = 0

        body_start = req_text.find("\r\n\r\n")
        body = ""
        if body_start != -1:
            body = req_text[body_start + 4:]
            if len(body) < content_length:
                try:
                    more = conn.recv(content_length - len(body))
                    body += more.decode()
                except:
                    pass

        payload = {}
        try:
            payload = json.loads(body) if body else {}
        except:
            payload = {}

        # Normalize
        text = payload.get("text") or payload.get("message") or ""
        user_name = payload.get("user_name") or payload.get("user") or "webhook"
        chat_id = payload.get("chat_id") or payload.get("channel") or ""
        response_url = payload.get("response_url") or ""

        # Slack events style
        if channel == "slack":
            ev = payload.get("event", {})
            if ev:
                text = ev.get("text", text)
                chat_id = ev.get("channel", chat_id)
                user_name = ev.get("user", user_name)

        if not text:
            conn.send(http_response("No text", code=200))
            conn.close()
            return

        # Write inbox job
        data_dir = config_path.rsplit("/", 1)[0] if "/" in config_path else "./data"
        inbox_dir = Path.join(data_dir, "inbox", "queue")
        mkdir_recursive(inbox_dir)
        job_id = "in_" + str(int(time.time()))
        job_path = Path.join(inbox_dir, job_id + ".json")
        job = {
            "channel": channel,
            "target": chat_id,
            "user_name": user_name,
            "text": text,
            "response_url": response_url,
        }
        try:
            with open(job_path, "w") as f:
                f.write(json.dumps(job))
        except:
            pass

        conn.send(http_response("OK", code=200))
        conn.close()
        return

    # Bootstrap flow if no password configured
    if not has_ui_password(config):
        if method == "POST" and path == "/setup":
            content_length = 0
            try:
                content_length = int(headers.get("content-length", "0"))
            except:
                content_length = 0

            body_start = req_text.find("\r\n\r\n")
            body = ""
            if body_start != -1:
                body = req_text[body_start + 4:]
                if len(body) < content_length:
                    try:
                        more = conn.recv(content_length - len(body))
                        body += more.decode()
                    except:
                        pass

            data = parse_qs(body)
            pwd = data.get("password", "")
            pwd2 = data.get("password2", "")
            if pwd and pwd == pwd2:
                if set_ui_password(config_path, config, pwd):
                    html = """
<html><head><meta charset="utf-8"><title>Saved</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}
a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body>
<div class="wrap"><div class="card">
<h1>Saved</h1>
<p>Password set. Continue to login.</p>
<a href="/">Go to login</a>
</div></div></body></html>
"""
                else:
                    html = """
<html><head><meta charset="utf-8"><title>Error</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Error</h1><p>Failed to save password.</p><a href="/">Back</a>
</div></div></body></html>
"""
            else:
                html = """
<html><head><meta charset="utf-8"><title>Error</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Error</h1><p>Passwords do not match.</p><a href="/">Back</a>
</div></div></body></html>
"""

            conn.send(http_response(html))
            conn.close()
            return

        # Show setup page
        html = """
<html><head><meta charset="utf-8"><title>Setup</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}
label{display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin:14px 0 6px;color:var(--muted)}
input{width:100%;padding:12px 14px;border:1px solid var(--border);border-radius:10px;background:#fff;color:var(--ink)}
button{width:100%;padding:12px 14px;border:0;border-radius:10px;background:var(--accent);color:#fff;margin-top:12px;font-weight:600}
.note{font-size:12px;color:var(--muted);margin-top:10px}
</style></head><body>
<div class="wrap">
  <div class="card">
    <h1>Set UI Password</h1>
    <form method="POST" action="/setup">
      <label>Password</label>
      <input type="password" name="password">
      <label>Repeat Password</label>
      <input type="password" name="password2">
      <button type="submit">Save</button>
    </form>
    <div class="note">This protects the config UI.</div>
  </div>
</div>
</body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    # Login flow (password only)
    if not check_auth(headers, config):
        if method == "POST" and path == "/login":
            content_length = 0
            try:
                content_length = int(headers.get("content-length", "0"))
            except:
                content_length = 0

            body_start = req_text.find("\r\n\r\n")
            body = ""
            if body_start != -1:
                body = req_text[body_start + 4:]
                if len(body) < content_length:
                    try:
                        more = conn.recv(content_length - len(body))
                        body += more.decode()
                    except:
                        pass

            data = parse_qs(body)
            pwd = data.get("password", "")
            salt = config.get("ui_pass_salt", "")
            hsh = config.get("ui_pass_hash", "")
            if pwd and salt and hsh and sha256_hex(salt + pwd) == hsh:
                global SESSION_TOKEN
                SESSION_TOKEN = sha256_hex(str(time.time()) + pwd)
                html = """
<html><head><meta charset="utf-8"><title>OK</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Logged in</h1><p>Session created.</p><a href="/">Continue</a>
</div></div></body></html>
"""
                resp = http_response(html, headers={"Set-Cookie": "mb_session=" + SESSION_TOKEN + "; Path=/"})
                conn.send(resp)
                conn.close()
                return
            html = """
<html><head><meta charset="utf-8"><title>Error</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Error</h1><p>Wrong password.</p><a href="/">Back</a>
</div></div></body></html>
"""
            conn.send(http_response(html))
            conn.close()
            return

        html = """
<html><head><meta charset="utf-8"><title>Login</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}
label{display:block;font-size:12px;letter-spacing:.08em;text-transform:uppercase;margin:14px 0 6px;color:var(--muted)}
input{width:100%;padding:12px 14px;border:1px solid var(--border);border-radius:10px;background:#fff;color:var(--ink)}
button{width:100%;padding:12px 14px;border:0;border-radius:10px;background:var(--accent);color:#fff;margin-top:12px;font-weight:600}
.note{font-size:12px;color:var(--muted);margin-top:10px}
</style></head><body>
<div class="wrap">
  <div class="card">
    <h1>MicroBot-Claw</h1>
    <form method="POST" action="/login">
      <label>Password</label>
      <input type="password" name="password" placeholder="Enter password">
      <button type="submit">Login</button>
    </form>
    <div class="note">Secure access, no username required.</div>
  </div>
</div></body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    # Memory editor
    if path == "/memory":
        data_dir = _data_dir_from_config_path(config_path)
        mem_path = _safe_path(data_dir, "memory/MEMORY.md")
        sum_path = _safe_path(data_dir, "memory/SUMMARY.md")
        if method == "POST":
            content_length = 0
            try:
                content_length = int(headers.get("content-length", "0"))
            except:
                content_length = 0
            body_start = req_text.find("\r\n\r\n")
            body = ""
            if body_start != -1:
                body = req_text[body_start + 4:]
                if len(body) < content_length:
                    try:
                        more = conn.recv(content_length - len(body))
                        body += more.decode()
                    except:
                        pass
            data = parse_qs(body)
            mem_txt = data.get("memory", "")
            sum_txt = data.get("summary", "")
            ok1 = write_text_file(mem_path, mem_txt)
            ok2 = write_text_file(sum_path, sum_txt)
            msg = "Saved" if (ok1 or ok2) else "Error"
            conn.send(http_response("<html><body>Memory " + msg + ". <a href='/memory'>Back</a></body></html>"))
            conn.close()
            return

        mem_txt = html_escape(read_text_file(mem_path))
        sum_txt = html_escape(read_text_file(sum_path))
        html = """
<html><head><meta charset="utf-8"><title>Memory</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:900px;margin:30px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
textarea{width:100%;min-height:220px;border:1px solid var(--border);border-radius:12px;padding:12px}
button{padding:10px 14px;margin-top:12px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:600}
a{color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body>
<div class="wrap"><div class="card">
<h1>Memory</h1>
<form method="POST" action="/memory">
<label>MEMORY.md</label>
<textarea name="memory">""" + mem_txt + """</textarea>
<label>SUMMARY.md</label>
<textarea name="summary">""" + sum_txt + """</textarea>
<button type="submit">Save</button>
</form>
<a href="/">Back</a>
</div></div></body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    # Personality editor
    if path == "/personality":
        data_dir = _data_dir_from_config_path(config_path)
        soul_path = _safe_path(data_dir, "config/SOUL.md")
        if method == "POST":
            content_length = 0
            try:
                content_length = int(headers.get("content-length", "0"))
            except:
                content_length = 0
            body_start = req_text.find("\r\n\r\n")
            body = ""
            if body_start != -1:
                body = req_text[body_start + 4:]
                if len(body) < content_length:
                    try:
                        more = conn.recv(content_length - len(body))
                        body += more.decode()
                    except:
                        pass
            data = parse_qs(body)
            ok1 = write_text_file(soul_path, data.get("soul", ""))
            msg = "Saved" if ok1 else "Error"
            conn.send(http_response("<html><body>Personality " + msg + ". <a href='/personality'>Back</a></body></html>"))
            conn.close()
            return
        soul_txt = html_escape(read_text_file(soul_path))
        html = """
<html><head><meta charset="utf-8"><title>SOUL Editor</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:900px;margin:30px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
textarea{width:100%;min-height:200px;border:1px solid var(--border);border-radius:12px;padding:12px}
button{padding:10px 14px;margin-top:12px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:600}
a{color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body>
<div class="wrap"><div class="card">
<h1>SOUL.md Editor</h1>
<form method="POST" action="/personality">
<label>SOUL.md</label>
<textarea name="soul">""" + soul_txt + """</textarea>
<button type="submit">Save</button>
</form>
<a href="/">Back</a>
</div></div></body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    # Skills editor
    if path == "/skills":
        data_dir = _data_dir_from_config_path(config_path)
        skills_dir = _safe_path(data_dir, "skills")
        mkdir_recursive(skills_dir)
        if method == "POST":
            content_length = 0
            try:
                content_length = int(headers.get("content-length", "0"))
            except:
                content_length = 0
            body_start = req_text.find("\r\n\r\n")
            body = ""
            if body_start != -1:
                body = req_text[body_start + 4:]
                if len(body) < content_length:
                    try:
                        more = conn.recv(content_length - len(body))
                        body += more.decode()
                    except:
                        pass
            data = parse_qs(body)
            name = data.get("name", "").strip().replace(" ", "_")
            content = data.get("content", "")
            if name:
                path2 = _safe_path(skills_dir, name + ".md")
                ok = write_text_file(path2, content)
                msg = "Saved" if ok else "Error"
            else:
                msg = "Error"
            conn.send(http_response("<html><body>Skill " + msg + ". <a href='/skills'>Back</a></body></html>"))
            conn.close()
            return
        files = []
        try:
            files = os.listdir(skills_dir)
        except:
            files = []
        items = []
        for f in files:
            if f.endswith(".md"):
                items.append(f)
        items.sort()
        list_html = "<ul>"
        for f in items:
            list_html += "<li>" + html_escape(f) + "</li>"
        list_html += "</ul>"
        html = """
<html><head><meta charset="utf-8"><title>Skills</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:900px;margin:30px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
textarea{width:100%;min-height:200px;border:1px solid var(--border);border-radius:12px;padding:12px}
input{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:10px}
button{padding:10px 14px;margin-top:12px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:600}
a{color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body>
<div class="wrap"><div class="card">
<h1>Skills</h1>
""" + list_html + """
<form method="POST" action="/skills">
<label>Skill Name</label>
<input name="name" placeholder="example_skill">
<label>Skill Content</label>
<textarea name="content"># Skill: example
Description: ...
Steps:
- ...
</textarea>
<button type="submit">Save</button>
</form>
<a href="/">Back</a>
</div></div></body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    # Skills usage panel
    if path == "/skills_usage":
        pdir = Path.join(get_script_dir(), "plugins")
        try:
            files = os.listdir(pdir)
        except:
            files = []
        rows = []
        for fn in files:
            if not fn.endswith(".json"):
                continue
            pathj = Path.join(pdir, fn)
            try:
                with open(pathj, "r") as f:
                    data = json.load(f)
            except:
                data = {}
            name = data.get("name", fn[:-5])
            desc = data.get("description", "")
            args = data.get("args", "")
            rows.append("<div class='prow'><b>" + html_escape(name) + "</b><div class='pdesc'>" + html_escape(desc) + "</div><div class='pdesc'>args: " + html_escape(str(args)) + "</div></div>")
        html = """
<html><head><meta charset="utf-8"><title>Skill Usage</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:900px;margin:30px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
.prow{padding:12px 0;border-bottom:1px solid var(--border)}
.pdesc{font-size:12px;color:var(--muted);margin-top:4px}
a{color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body>
<div class="wrap"><div class="card">
<h1>Skill Usage</h1>
""" + "\n".join(rows) + """
<a href="/">Back</a>
</div></div></body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    # Plugin manager
    if path.startswith("/plugins"):
        if method == "POST":
            content_length = 0
            try:
                content_length = int(headers.get("content-length", "0"))
            except:
                content_length = 0

            body_start = req_text.find("\r\n\r\n")
            body = ""
            if body_start != -1:
                body = req_text[body_start + 4:]
                if len(body) < content_length:
                    try:
                        more = conn.recv(content_length - len(body))
                        body += more.decode()
                    except:
                        pass

            data = parse_qs(body)
            plugins = list_plugins()
            enabled = []
            for p in plugins:
                pid = p.get("id", "")
                if data.get("plg_" + pid, ""):
                    enabled.append(pid)
            config["enabled_plugins"] = enabled
            ok = save_config(config_path, config)
            if ok:
                msg = "Plugins updated."
            else:
                msg = "Failed to save plugin config."
            html = """
<html><head><meta charset="utf-8"><title>Plugins</title>
<style>*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#fff;color:#111}
.wrap{max-width:720px;margin:40px auto;padding:0 16px}.card{border:1px solid #111;border-radius:12px;padding:20px}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:#111}
</style></head><body><div class="wrap"><div class="card">
<h1>Plugins</h1><p>""" + html_escape(msg) + """</p><a href="/plugins">Back</a>
</div></div></body></html>
"""
            conn.send(http_response(html))
            conn.close()
            return

        plugins = list_plugins()
        enabled = config.get("enabled_plugins", [])
        enabled_all = not (isinstance(enabled, list) and len(enabled) > 0)
        rows = []
        for p in plugins:
            pid = p.get("id", "")
            name = p.get("name", pid)
            desc = p.get("desc", "")
            checked = "checked" if (enabled_all or pid in enabled) else ""
            rows.append(
                '<div class="prow"><label><input type="checkbox" name="plg_'
                + html_escape(pid)
                + '" '
                + checked
                + '> '
                + html_escape(name)
                + '</label><div class="pdesc">'
                + html_escape(desc)
                + "</div></div>"
            )
        html = """
<html><head><meta charset="utf-8"><title>Plugins</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:760px;margin:30px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}
.prow{padding:12px 0;border-bottom:1px solid var(--border)}
.pdesc{font-size:12px;color:var(--muted);margin-left:22px}
button{padding:10px 14px;margin-top:12px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:600}
a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body>
<div class="wrap"><div class="card">
<h1>Plugin Manager</h1>
<form method="POST" action="/plugins">
%s
<button type="submit">Save</button>
</form>
<a href="/">Back to config</a>
</div></div></body></html>
""" % "\n".join(rows)
        conn.send(http_response(html))
        conn.close()
        return

    if method == "POST":
        content_length = 0
        try:
            content_length = int(headers.get("content-length", "0"))
        except:
            content_length = 0

        body_start = req_text.find("\r\n\r\n")
        body = ""
        if body_start != -1:
            body = req_text[body_start + 4:]
            if len(body) < content_length:
                try:
                    more = conn.recv(content_length - len(body))
                    body += more.decode()
                except:
                    pass

        if path == "/restart":
            run_command("/etc/init.d/microbot-claw restart >/dev/null 2>&1")
            html = """
<html><head><meta charset="utf-8"><title>Restarted</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Restarted</h1><p>Service restart requested.</p><a href="/">Back</a>
</div></div></body></html>
"""
            conn.send(http_response(html))
            conn.close()
            return

        data = parse_qs(body)
        for k in data:
            config[k] = data[k]
        ok = save_config(config_path, config)
        if ok:
            html = """
<html><head><meta charset="utf-8"><title>Saved</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Saved</h1><p>Config updated.</p><a href="/">Back</a>
</div></div></body></html>
"""
        else:
            html = """
<html><head><meta charset="utf-8"><title>Error</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:520px;margin:60px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 12px}a{display:inline-block;margin-top:12px;color:var(--accent);text-decoration:none;font-weight:600}
</style></head><body><div class="wrap"><div class="card">
<h1>Error</h1><p>Failed to save config.</p><a href="/">Back</a>
</div></div></body></html>
"""
        conn.send(http_response(html))
        conn.close()
        return

    form = build_sections(config)
    html = """
<html>
<head>
<meta charset="utf-8">
<title>MicroBot-Claw Config</title>
<style>
:root{--bg:#f4f6fb;--card:#ffffff;--ink:#101326;--muted:#58607a;--accent:#2f6bff;--border:#e6e9f2}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
.wrap{max-width:1100px;margin:30px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 10px 30px rgba(16,19,38,.08)}
h1{font-size:22px;margin:0 0 8px}
.row{margin:10px 0;display:flex;gap:12px;align-items:center}
label{width:260px;font-weight:600;color:var(--muted)}
input,select{flex:1;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:#fff;color:var(--ink)}
button{padding:10px 14px;margin-top:12px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:600}
.actions{display:flex;gap:10px;flex-wrap:wrap}
.subtle{font-size:12px;color:var(--muted);margin:6px 0 14px}
.section{padding:16px 0;border-top:1px solid var(--border)}
.section h2{font-size:14px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:2px 0 12px}
.linkrow{margin-top:10px}
a{color:var(--accent);text-decoration:none;font-weight:600}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>MicroBot-Claw Configuration</h1>
    <div class="subtle">Modern configuration console. Changes are applied on save.</div>
    <form method="POST" action="/save">
      %s
      <div class="actions">
        <button type="submit">Save Changes</button>
      </div>
    </form>
    <div class="linkrow">
      <a href="/plugins">Manage Plugins</a> | 
      <a href="/memory">Memory</a> | 
      <a href="/personality">Personality</a> | 
      <a href="/skills">Skills</a> | 
      <a href="/skills_usage">Skill Usage</a>
    </div>
    <form method="POST" action="/restart">
      <button type="submit">Restart Bot</button>
    </form>
  </div>
</div>
</body>
</html>
""" % form
    conn.send(http_response(html))
    conn.close()


def main():
    config, config_path = load_config()
    if not config:
        print("ERROR: config not found or invalid")
        return

    ui_enabled = str(config.get("ui_enabled", "true")).lower() == "true"
    if not ui_enabled:
        print("UI disabled in config")
        return

    bind = config.get("ui_bind", "0.0.0.0")
    if not bind:
        bind = "0.0.0.0"
    port = int(config.get("ui_port", config.get("http_port", "8080")))

    s = socket.socket()
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except:
        pass
    try:
        addr = socket.getaddrinfo(bind, port)[0][-1]
        s.bind(addr)
    except:
        s.bind((bind, port))
    s.listen(2)
    print("UI listening on %s:%d" % (bind, port))

    while True:
        try:
            conn, addr = s.accept()
            handle_client(conn, addr, config, config_path)
        except KeyboardInterrupt:
            break
        except Exception as e:
            try:
                time.sleep(0.1)
            except:
                pass


if __name__ == "__main__":
    main()
