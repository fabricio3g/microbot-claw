#!/usr/bin/env python3
"""
MicroBot-Claw - Telegram Bot for OpenWrt (MicroPython version)
# Compatible with limited Python environments (no subprocess, no requests)
"""

print("\n\n =============================================== \n")
print("\n\n =============== STARTING MICROBOT-CLAW =============== \n")
print("\n\n =============================================== \n")
import sys


# Try to import u-modules (MicroPython), fallback to standard
try:
    import usys as sys
except ImportError:
    import sys

try:
    import uos as os
except ImportError:
    import os

try:
    import utime as time
except ImportError:
    import time

try:
    import ujson as json
except ImportError:
    import json

import gc


# --- MicroPython Compatibility Layer ---
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

# Use standard os.path if available, otherwise use our polyfill


# ---------------------------------------

# Helper function: Run shell command (must be defined early for use in config detection)
def run_command(cmd):
    """Run shell command and return output. Uses os.popen or os.system fallback for MicroPython."""
    # Try os.popen first (standard Python)
    if hasattr(os, "popen"):
        try:
            p = os.popen(cmd)
            result = p.read()
            p.close()
            return result.strip()
        except:
            pass

    # Fallback for MicroPython: use os.system and a temp file
    # We use a timestamped file in /tmp
    tmp_file = "/tmp/cmd_out_" + str(int(time.time())) + ".txt"
    try:
        # Redirect stdout and stderr to temp file
        os.system(cmd + " > " + tmp_file + " 2>&1")

        # Read result
        result = ""
        if Path.exists(tmp_file):
            with open(tmp_file, "r") as f:
                result = f.read()
            # Clean up temp file
            try:
                os.remove(tmp_file)
            except:
                pass
        return result.strip()
    except Exception as e:
        print("run_command error: " + str(e))
        return ""


# Helper function: Create directory recursively
def mkdir_recursive(path):
    """Create directory recursively (compatible with MicroPython without os.makedirs)"""
    if Path.exists(path):
        return True

    # Try os.makedirs first (if available)
    if hasattr(os, "makedirs"):
        try:
            os.makedirs(path)
            return True
        except:
            pass

    # Fallback: create each directory level manually
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


# Configuration
# Determine script directory (use getenv first for init.d, then __file__, then pwd)
SCRIPT_DIR = "."
try:
    if hasattr(os, "getenv"):
        env_dir = os.getenv("MICROBOT_INSTALL_DIR")
        if env_dir and Path.exists(Path.join(env_dir, "config.sh")):
            SCRIPT_DIR = env_dir
except:
    pass
try:
    if SCRIPT_DIR == "." and "__file__" in globals():
        script_path = __file__
        if "/" in script_path:
            SCRIPT_DIR = script_path.rsplit("/", 1)[0]
except:
    pass
# Fallbacks if __file__ had no path or default is wrong
try:
    if SCRIPT_DIR == "." and Path.exists("config.sh") and Path.exists("tools.sh"):
        SCRIPT_DIR = "."
    elif SCRIPT_DIR == "." and hasattr(os, "getcwd"):
        cwd = os.getcwd()
        if cwd and Path.exists(Path.join(cwd, "config.sh")):
            SCRIPT_DIR = cwd
    elif SCRIPT_DIR == ".":
        # Very limited environments: use shell pwd
        pwd = run_command("pwd")
        if pwd and Path.exists(Path.join(pwd, "config.sh")):
            SCRIPT_DIR = pwd
except:
    pass

# Check for config file in multiple locations (prefer local ./data)
possible_configs = [
    Path.join(SCRIPT_DIR, "data", "config.json"),
    "data/config.json",
    "/data/config.json",
]

# Merge configs: load all and combine
config_data = {}
CONFIG_FILE = "/data/config.json"  # Default
found_config = ""
for p in possible_configs:
    if Path.exists(p):
        found_config = p
        try:
            with open(p, "r") as f:
                new_data = json.load(f)
                for k in new_data:
                    if new_data[k]:  # Only take non-empty values
                        config_data[k] = new_data[k]
        except:
            pass

# Prefer actual config path if found
if found_config:
    CONFIG_FILE = found_config
else:
    # If /data doesn't exist, fallback to script-local data dir
    if not Path.exists("/data"):
        CONFIG_FILE = Path.join(SCRIPT_DIR, "data", "config.json")

# Derive data dir from CONFIG_FILE
DATA_DIR = "/data"
try:
    if "/" in CONFIG_FILE:
        DATA_DIR = CONFIG_FILE.rsplit("/", 1)[0]
    elif Path.exists(Path.join(SCRIPT_DIR, "data")):
        DATA_DIR = Path.join(SCRIPT_DIR, "data")
except:
    pass

# Ensure data dir exists
mkdir_recursive(DATA_DIR)

TEMP_DIR = "/tmp/microbot"
if not Path.exists(TEMP_DIR):
    try:
        os.mkdir(TEMP_DIR)
    except:
        pass

# Ensure core package is importable
try:
    if SCRIPT_DIR and SCRIPT_DIR not in sys.path:
        sys.path.append(SCRIPT_DIR)
except:
    pass

try:
    from core import scheduler
except:
    scheduler = None


# --- LLM Client ---
class LLMClient:
    def __init__(self, config):
        self.config = config
        self.provider = config.get("provider", "openrouter")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "claude-opus-4-5")
        self.or_key = config.get("openrouter_key", "")
        self.or_model = config.get("openrouter_model", "anthropic/claude-opus-4")
        self.or_fallback = config.get("openrouter_model_fallback", "")
        self.model_fallback = config.get("model_fallback", "")
        self.max_tokens = int(config.get("max_tokens", 512))
        try:
            self.max_retries = int(config.get("llm_max_retries", 2))
        except:
            self.max_retries = 2
        try:
            self.retry_backoff_ms = int(config.get("llm_retry_backoff_ms", 500))
        except:
            self.retry_backoff_ms = 500

    def chat(self, messages, system_prompt=None, max_tokens=None, temperature=None):
        """Send chat request and return response dict"""
        use_max = max_tokens if max_tokens is not None else self.max_tokens

        if self.provider == "openrouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = [
                "Content-Type: application/json",
                "Authorization: Bearer " + self.or_key,
                "HTTP-Referer: https://microbot-claw",
                "X-Title: MicroBot-Claw",
            ]
            primary_model = self.or_model
            fallback_model = self.or_fallback or ""
        else:
            url = "https://api.anthropic.com/v1/messages"
            headers = [
                "Content-Type: application/json",
                "x-api-key: " + self.api_key,
                "anthropic-version: 2023-06-01",
            ]
            primary_model = self.model
            fallback_model = self.model_fallback or ""

        models = [primary_model]
        if fallback_model and fallback_model != primary_model:
            models.append(fallback_model)

        def _sleep_backoff():
            try:
                if self.retry_backoff_ms > 0:
                    time.sleep(self.retry_backoff_ms / 1000.0)
            except:
                try:
                    time.sleep(1)
                except:
                    pass

        for mi, model_name in enumerate(models):
            for attempt in range(self.max_retries + 1):
                data = {}
                if self.provider == "openrouter":
                    msgs = []
                    if system_prompt:
                        msgs.append({"role": "system", "content": system_prompt})
                    msgs.extend(messages)
                    data = {
                        "model": model_name,
                        "messages": msgs,
                        "max_tokens": use_max,
                    }
                    if temperature is not None:
                        data["temperature"] = temperature
                else:
                    data = {
                        "model": model_name,
                        "messages": messages,
                        "max_tokens": use_max,
                    }
                    if system_prompt:
                        data["system"] = system_prompt
                    if temperature is not None:
                        data["temperature"] = temperature

                # Serialize JSON
                try:
                    body = json.dumps(data)
                except Exception as e:
                    print("Error serializing request: " + str(e))
                    return None

                # Write body to temp file in RAM (/tmp) to avoid shell limits
                req_file = Path.join(TEMP_DIR, "mimi_req_" + str(int(time.time())) + ".json")
                try:
                    with open(req_file, "w") as f:
                        f.write(body)
                except Exception as e:
                    print("Error writing request file: " + str(e))
                    return None

                # Build curl command using the file
                header_args = ""
                for h in headers:
                    header_args += " -H '" + h + "'"

                # Check proxy
                proxy = self.config.get("proxy_host")
                proxy_port = self.config.get("proxy_port")
                proxy_arg = ""
                if proxy and proxy_port:
                    proxy_arg = ' -x "http://' + proxy + ":" + str(proxy_port) + '"'

                cmd = (
                    "curl -k -s --connect-timeout 8 -m 25"
                    + proxy_arg
                    + header_args
                    + " -d @"
                    + req_file
                    + " '"
                    + url
                    + "'"
                )

                resp_txt = run_command(cmd)

                # Cleanup temp file
                try:
                    os.remove(req_file)
                except:
                    pass

                if not resp_txt:
                    if attempt < self.max_retries:
                        _sleep_backoff()
                        continue
                    break

                try:
                    resp = json.loads(resp_txt)
                except Exception as e:
                    print("Error parsing LLM response: " + str(e))
                    if attempt < self.max_retries:
                        _sleep_backoff()
                        continue
                    return None

                if isinstance(resp, dict) and resp.get("error"):
                    if attempt < self.max_retries:
                        _sleep_backoff()
                        continue
                    # If primary failed, try fallback
                    break

                return resp

            # next model (fallback)
            if mi == 0 and len(models) > 1:
                print("LLM fallback to model: " + str(models[1]))
                continue

        print("Error: LLM request failed after retries")
        return None


# --- Text cleanup for Telegram ---
def strip_markdown(text):
    """Remove markdown formatting so Telegram gets clean plain text"""
    s = str(text)
    # Remove bold/italic markers efficiently
    for marker in ("**", "__", "```", "`"):
        if marker in s:
            s = s.replace(marker, "")
            
    # Remove heading markers and bullet dashes
    lines = s.split("\n")
    for i in range(len(lines)):
        line = lines[i].lstrip()
        if line.startswith("#"):
            line = line.lstrip("#").lstrip()
        elif line.startswith("- "):
            line = "  " + line[2:]
        lines[i] = line
        
    return "\n".join(lines)


# --- File Helpers (Telegram attachments & downloads) ---
def safe_filename(name):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    out = []
    for ch in str(name):
        out.append(ch if ch in allowed else "_")
    clean = "".join(out).strip("._")
    return clean or ("file_" + str(int(time.time())))


def tg_get_file_path(file_id, token):
    if not file_id or not token:
        return ""
    # Telegram Bot API: getFile returns File with file_path; file_id as-is in query
    file_id_str = str(file_id).strip()
    url = "https://api.telegram.org/bot" + token + "/getFile?file_id=" + file_id_str
    resp = run_command("curl -k -s -m 15 \"" + url.replace('"', '\\"') + "\"")
    if not resp:
        try:
            print("[attachment] getFile: no response from API")
        except:
            pass
        return ""
    try:
        data = json.loads(resp)
        if data.get("ok") and data.get("result"):
            return data["result"].get("file_path", "")
        try:
            err = data.get("description", resp[:120])
            print("[attachment] getFile API error: " + str(err))
        except:
            pass
    except Exception as e:
        try:
            print("[attachment] getFile parse error: " + str(e)[:80] + " resp=" + str(resp)[:100])
        except:
            pass
    return ""


def tg_download_file(file_path, dest_path, token):
    if not file_path or not dest_path or not token:
        return False
    # Telegram: download from https://api.telegram.org/file/bot<token>/<file_path>
    file_path_str = str(file_path).strip()
    url = "https://api.telegram.org/file/bot" + token + "/" + file_path_str
    # Use -m 30 for larger files; -o with double-quoted path for ash compatibility
    dest_esc = dest_path.replace("\\", "\\\\").replace('"', '\\"')
    cmd = "curl -k -L -s -m 30 -o \"" + dest_esc + "\" \"" + url.replace('"', '\\"') + "\""
    run_command(cmd)
    return Path.exists(dest_path)


def send_telegram_file(chat_id, file_path, token, caption=""):
    if not file_path or not token:
        return
    if not Path.exists(file_path):
        return
    cap = str(caption or "")
    cmd = (
        "curl -k -s --connect-timeout 5 -m 20 -F "
        + "'chat_id="
        + str(chat_id)
        + "' -F "
        + "'document=@"
        + file_path.replace("'", "'\\''")
        + "'"
    )
    if cap:
        cmd += " -F 'caption=" + cap.replace("'", "'\\''") + "'"
    cmd += " 'https://api.telegram.org/bot" + token + "/sendDocument'"
    run_command(cmd)


def handle_file_result(chat_id, tool_result, token):
    if not tool_result:
        return tool_result
    if isinstance(tool_result, str) and tool_result.startswith("FILE:"):
        fpath = tool_result.replace("FILE:", "", 1).strip()
        send_telegram_file(chat_id, fpath, token, "Archivo descargado")
        return "Archivo enviado: " + fpath
    return tool_result


def save_telegram_attachment(file_id, file_name, subdir, token, chat_id=None):
    """Save Telegram file. If chat_id is set, save to data/uploads/<chat_id>/<subdir>/ (user folder)."""
    if not file_id:
        return ""
    file_path = tg_get_file_path(file_id, token)
    if not file_path:
        try:
            print("[attachment] getFile failed for file_id=" + str(file_id)[:20])
        except:
            pass
        return ""
    name = file_name or file_path.rsplit("/", 1)[-1]
    if not name:
        name = "file_" + str(int(time.time()))
    name = safe_filename(name)
    if chat_id is not None:
        dest_dir = Path.join(DATA_DIR, "uploads", str(chat_id), subdir)
    else:
        dest_dir = Path.join(DATA_DIR, subdir)
    mkdir_recursive(dest_dir)
    dest_path = Path.join(dest_dir, name)
    if tg_download_file(file_path, dest_path, token):
        return dest_path
    try:
        print("[attachment] download failed path=" + str(dest_path)[:60])
    except:
        pass
    return ""

# ============================================
# SCHEDULER (No cron, in-process)
# ============================================
SCHEDULES_FILE = Path.join(DATA_DIR, "schedules.txt")
SCHEDULES_STATE_FILE = Path.join(DATA_DIR, "schedules_state.json")
TIMEZONE = ""  # Will be loaded from config
_tz_cache_ts = 0
_tz_cache_val = None


def get_local_time(timezone=""):
    """Get current time in specified timezone. Falls back to system time if no timezone."""
    if scheduler:
        try:
            return scheduler.get_local_time(timezone, run_command)
        except:
            pass
    if not timezone:
        return time.localtime()

    # Simple cache to avoid frequent network calls
    global _tz_cache_ts, _tz_cache_val
    try:
        now_ts = time.time()
        if _tz_cache_val and (now_ts - _tz_cache_ts) < 30:
            return _tz_cache_val
    except:
        pass

    # Try worldtimeapi.org for timezone-aware time
    try:
        url = "http://worldtimeapi.org/api/timezone/" + timezone.replace("/", "%2F")
        cmd = "curl -k -s -m 5 '" + url + "'"
        result = run_command(cmd)
        if result and "datetime" in result:
            # Parse ISO datetime: "2024-01-15T14:30:00+00:00"
            dt_start = result.find('"datetime":"')
            if dt_start != -1:
                dt_start += 11
                dt_end = result.find('"', dt_start)
                dt_str = result[dt_start:dt_end]

                # Extract components: 2024-01-15T14:30:00
                year = int(dt_str[0:4])
                month = int(dt_str[5:7])
                day = int(dt_str[8:10])
                hour = int(dt_str[11:13])
                minute = int(dt_str[14:16])
                second = int(dt_str[17:19])

                # Prefer API-provided weekday/day-of-year for accuracy
                dow = None
                yday = 0
                isdst = 0

                d_start = result.find('"day_of_week":')
                if d_start != -1:
                    d_start += 14
                    d_end = result.find(",", d_start)
                    if d_end != -1:
                        try:
                            # API: 0=Sunday ... 6=Saturday. Convert to 0=Monday.
                            api_dow = int(result[d_start:d_end].strip())
                            dow = (api_dow - 1) % 7
                        except:
                            pass

                yd_start = result.find('"day_of_year":')
                if yd_start != -1:
                    yd_start += 14
                    yd_end = result.find(",", yd_start)
                    if yd_end != -1:
                        try:
                            yday = int(result[yd_start:yd_end].strip())
                        except:
                            yday = 0

                dst_start = result.find('"dst":')
                if dst_start != -1:
                    dst_start += 6
                    dst_end = result.find(",", dst_start)
                    if dst_end != -1:
                        isdst = 1 if result[dst_start:dst_end].strip() == "true" else 0

                if dow is None:
                    # Fallback: use system time's weekday if parsing failed
                    dow = time.localtime()[6]

                # Return as tuple like localtime: (year, month, day, hour, minute, second, wday, yday, isdst)
                _tz_cache_val = (year, month, day, hour, minute, second, dow, yday, isdst)
                try:
                    _tz_cache_ts = time.time()
                except:
                    _tz_cache_ts = 0
                return _tz_cache_val
    except:
        pass

    # Fallback: try TZ env with local date (if supported)
    try:
        cmd = "TZ='" + timezone.replace("'", "") + "' date +%Y-%m-%dT%H:%M:%S"
        out = run_command(cmd)
        if out and "T" in out:
            dt_str = out.strip()
            year = int(dt_str[0:4])
            month = int(dt_str[5:7])
            day = int(dt_str[8:10])
            hour = int(dt_str[11:13])
            minute = int(dt_str[14:16])
            second = int(dt_str[17:19])
            # Use system weekday/yday as fallback
            sys_now = time.localtime()
            dow = sys_now[6]
            yday = sys_now[7]
            isdst = sys_now[8] if len(sys_now) > 8 else 0
            return (year, month, day, hour, minute, second, dow, yday, isdst)
    except:
        pass

    # Fallback to system time
    return time.localtime()


def matches_cron(cron_expr, now):
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return False

    vals = [now[4], now[3], now[2], now[1], (now[6] + 1) % 7]

    def _match_field(f, v, is_dow=False):
        if f == "*":
            return True

        # Comma-separated list
        if "," in f:
            parts = f.split(",")
            for part in parts:
                if _match_field(part, v, is_dow):
                    return True
            return False

        # Step values (*/n or a-b/n)
        step = 1
        if "/" in f:
            f, step_str = f.split("/", 1)
            try:
                step = int(step_str)
            except:
                return False
            if step <= 0:
                return False

        # Range a-b or single value
        if f == "*":
            return v % step == 0

        if "-" in f:
            try:
                start, end = f.split("-", 1)
                a = int(start)
                b = int(end)
            except:
                return False
            # Normalize Sunday=7 -> 0 if dow field
            if is_dow:
                if a == 7:
                    a = 0
                if b == 7:
                    b = 0
            if a <= b:
                if v < a or v > b:
                    return False
            else:
                # Wrap-around range (e.g., 22-2)
                if v > b and v < a:
                    return False
            return ((v - a) % step) == 0

        # Single value
        try:
            num = int(f)
        except:
            return False
        if is_dow and num == 7:
            num = 0
        if v != num:
            return False
        return True

    for i in range(5):
        if not _match_field(fields[i], vals[i], is_dow=(i == 4)):
            return False
    return True


def _to_int(s, default=None):
    try:
        return int(s)
    except:
        return default


def is_valid_cron(expr):
    fields = str(expr or "").strip().split()
    if len(fields) != 5:
        return False

    def _valid_part(part, vmin, vmax, is_dow=False):
        if part == "*":
            return True

        if "," in part:
            for p in part.split(","):
                if not _valid_part(p.strip(), vmin, vmax, is_dow):
                    return False
            return True

        base = part
        step = None
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = _to_int(step_str, None)
            if step is None or step <= 0:
                return False

        if base == "*":
            return True

        if "-" in base:
            a_str, b_str = base.split("-", 1)
            a = _to_int(a_str, None)
            b = _to_int(b_str, None)
            if a is None or b is None:
                return False
            if is_dow:
                if a == 7:
                    a = 0
                if b == 7:
                    b = 0
            if a < vmin or a > vmax or b < vmin or b > vmax:
                return False
            return True

        n = _to_int(base, None)
        if n is None:
            return False
        if is_dow and n == 7:
            n = 0
        if n < vmin or n > vmax:
            return False
        return True

    mins, hours, dom, mon, dow = fields
    return (
        _valid_part(mins, 0, 59, False)
        and _valid_part(hours, 0, 23, False)
        and _valid_part(dom, 1, 31, False)
        and _valid_part(mon, 1, 12, False)
        and _valid_part(dow, 0, 7, True)
    )


def _parse_time_from_text(text):
    """Extract (hour, minute) from text. Supports '9am', '9 am', '09:30', '9:30pm'."""
    s = str(text or "").lower().replace(",", " ").replace(".", " ")
    tokens = [t for t in s.split() if t]
    for i in range(len(tokens)):
        tok = tokens[i].strip()
        # Handle "9 am"
        if tok.isdigit() and i + 1 < len(tokens):
            nxt = tokens[i + 1].strip()
            if nxt in ("am", "pm"):
                hour = _to_int(tok, None)
                if hour is None or hour < 0 or hour > 23:
                    continue
                if nxt == "pm" and hour < 12:
                    hour += 12
                if nxt == "am" and hour == 12:
                    hour = 0
                return hour, 0

        # Handle "9am" / "9pm" / "9:30pm"
        if tok.endswith("am") or tok.endswith("pm"):
            ampm = tok[-2:]
            core = tok[:-2]
            if ":" in core:
                h_str, m_str = core.split(":", 1)
                hour = _to_int(h_str, None)
                minute = _to_int(m_str, None)
            else:
                hour = _to_int(core, None)
                minute = 0
            if hour is None or minute is None:
                continue
            if ampm == "pm" and hour < 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            return hour, minute

        # Handle "09:30"
        if ":" in tok:
            h_str, m_str = tok.split(":", 1)
            hour = _to_int(h_str, None)
            minute = _to_int(m_str, None)
            if hour is None or minute is None:
                continue
            return hour, minute
    return None, None


def _time_tuple_to_epoch(tup):
    try:
        return time.mktime(tup)
    except:
        try:
            return time.time()
        except:
            return 0


def _build_target_time(now, hour, minute, add_days=0):
    """Return target localtime tuple for given hour/minute, optionally days ahead."""
    try:
        base = (now[0], now[1], now[2], hour, minute, 0, 0, 0, -1)
        base_ts = _time_tuple_to_epoch(base)
    except:
        base_ts = _time_tuple_to_epoch(now)
    if add_days:
        base_ts += (add_days * 86400)
    # If target is not in the future, push by a day
    try:
        now_ts = _time_tuple_to_epoch(now)
        if base_ts <= now_ts:
            base_ts += 86400
    except:
        pass
    try:
        return time.localtime(base_ts)
    except:
        return now


def parse_natural_schedule(text, now):
    """Parse simple English schedule text into (cron, type, error)."""
    s = str(text or "").strip().lower()
    if not s:
        return "", "", "missing schedule"

    # One-time: in N minutes/hours
    if s.startswith("in "):
        tokens = s.split()
        if len(tokens) >= 3:
            num = _to_int(tokens[1], None)
            unit = tokens[2]
            if num is not None and num > 0 and ("minute" in unit or "hour" in unit):
                delta = num * 60 if "minute" in unit else num * 3600
                try:
                    now_ts = _time_tuple_to_epoch(now)
                    target = time.localtime(now_ts + delta)
                except:
                    target = now
                cron = str(target[4]) + " " + str(target[3]) + " " + str(target[2]) + " " + str(target[1]) + " *"
                return cron, "once", ""

    # One-time: tomorrow at HH:MM
    if "tomorrow" in s:
        hour, minute = _parse_time_from_text(s)
        if hour is None:
            return "", "", "missing time"
        target = _build_target_time(now, hour, minute, add_days=1)
        cron = str(target[4]) + " " + str(target[3]) + " " + str(target[2]) + " " + str(target[1]) + " *"
        return cron, "once", ""

    # Recurring: every N minutes/hours
    if "every" in s:
        tokens = s.split()
        for i in range(len(tokens) - 1):
            if tokens[i].isdigit() and ("minute" in tokens[i + 1] or "hour" in tokens[i + 1]):
                num = _to_int(tokens[i], None)
                if num is None or num <= 0:
                    continue
                if "minute" in tokens[i + 1]:
                    cron = "*/" + str(num) + " * * * *"
                else:
                    cron = "0 */" + str(num) + " * * *"
                return cron, "reminder", ""

        # every day / daily at
        if "every day" in s or "daily" in s:
            hour, minute = _parse_time_from_text(s)
            if hour is None:
                return "", "", "missing time"
            cron = str(minute) + " " + str(hour) + " * * *"
            return cron, "reminder", ""

        # every weekday at
        if "weekday" in s:
            hour, minute = _parse_time_from_text(s)
            if hour is None:
                return "", "", "missing time"
            cron = str(minute) + " " + str(hour) + " * * 1-5"
            return cron, "reminder", ""

        # every monday/tuesday/etc at
        weekdays = {
            "sunday": 0,
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
        }
        for name, dow in weekdays.items():
            if "every " + name in s:
                hour, minute = _parse_time_from_text(s)
                if hour is None:
                    return "", "", "missing time"
                cron = str(minute) + " " + str(hour) + " * * " + str(dow)
                return cron, "reminder", ""

    # One-time: at HH:MM
    if " at " in s or s.startswith("at "):
        hour, minute = _parse_time_from_text(s)
        if hour is None:
            return "", "", "missing time"
        target = _build_target_time(now, hour, minute, add_days=0)
        cron = str(target[4]) + " " + str(target[3]) + " " + str(target[2]) + " " + str(target[1]) + " *"
        return cron, "once", ""

    return "", "", "unsupported"


def normalize_schedule_args(args, now):
    """Return (cron, stype, error)."""
    cron_expr = args.get(
        "cron",
        args.get(
            "cron_expression",
            args.get("schedule", args.get("time_offset", args.get("interval", ""))),
        ),
    )
    stype = args.get("type", "msg")
    if is_valid_cron(cron_expr):
        return cron_expr, stype, ""

    cron_expr = str(cron_expr or "").strip()
    if cron_expr:
        parsed_cron, parsed_type, perr = parse_natural_schedule(cron_expr, now)
        if parsed_cron:
            return parsed_cron, parsed_type or stype, ""
        if perr == "missing time":
            return "", "", "Please specify a time (e.g., 'tomorrow at 9am' or 'at 18:30')."
        return "", "", "Unsupported schedule. Use 5-field cron or phrases like 'every day at 9am'."

    return "", "", "Schedule is missing."


def check_schedules(token, agent):
    if scheduler:
        try:
            return scheduler.check_schedules(
                token,
                agent,
                TIMEZONE,
                DATA_DIR,
                config_data,
                run_command,
                send_telegram_msg,
                send_telegram_file,
            )
        except Exception as e:
            print("[sched] scheduler module failed: " + str(e))

    if not Path.exists(SCHEDULES_FILE):
        return

    try:
        f = open(SCHEDULES_FILE, "r")
        data = f.read()
        f.close()
        lines = []
        for line in data.split("\n"):
            if line:
                lines.append(line)
    except:
        return

    if not lines:
        return

    # Load last-fired state to prevent duplicate sends in same minute
    state = {}
    try:
        if Path.exists(SCHEDULES_STATE_FILE):
            with open(SCHEDULES_STATE_FILE, "r") as f:
                state = json.load(f) or {}
    except:
        state = {}
    state_changed = False

    # Use timezone-aware time if configured
    now = get_local_time(TIMEZONE)
    now_key = (
        str(now[0])
        + ("%02d" % now[1])
        + ("%02d" % now[2])
        + ("%02d" % now[3])
        + ("%02d" % now[4])
    )
    new_lines = []

    print(
        "[sched] Checking "
        + str(len(lines))
        + " schedules at "
        + str(now[3])
        + ":"
        + str(now[4])
    )

    for line in lines:
        if len(line) < 10:
            new_lines.append(line)
            continue

        parts = line.split("|", 4)
        if len(parts) != 5:
            new_lines.append(line)
            continue

        sid, cron, chat, stype, content = parts
        stype = (stype or "").strip().lower()

        keep = True

        if matches_cron(cron, now):
            print("[sched] " + sid)

            # Avoid duplicates within the same minute
            if state.get(sid) == now_key:
                if keep:
                    new_lines.append(line)
                continue

            fired = False

            if stype in ("msg", "reminder") or stype.startswith("reminder") or stype.startswith("msg"):
                send_telegram_msg(int(chat), content, token)
                fired = True
            elif stype == "cmd":
                result = run_command(content)
                send_telegram_msg(int(chat), result, token)
                fired = True
            elif stype == "tool":
                # Support both: "tool_name args" and "tool_name|json_args"
                if "|" in content:
                    # Format: "tool_name|{"url": "...", "other": "..."}"
                    pipe_idx = content.find("|")
                    tname = content[0:pipe_idx]
                    targs = content[pipe_idx + 1:]
                else:
                    sp = content.find(" ")
                    if sp == -1:
                        tname = content
                        targs = "{}"
                    else:
                        tname = content[0:sp]
                        rest = content[sp + 1 :]
                        # Check if rest is already JSON
                        if rest.startswith("{"):
                            targs = rest
                        else:
                            targs = '{"query":"' + rest + '"}'
                result = agent.execute_tool(tname, targs)
                if result.startswith("FILE:"):
                    fpath = result.replace("FILE:", "", 1).strip()
                    send_telegram_file(int(chat), fpath, token, "Archivo descargado")
                    send_telegram_msg(int(chat), "Archivo enviado: " + fpath, token)
                else:
                    send_telegram_msg(int(chat), result, token)
                fired = True
            elif stype == "once_tool":
                # Support both: "tool_name args" and "tool_name|json_args"
                if "|" in content:
                    pipe_idx = content.find("|")
                    tname = content[0:pipe_idx]
                    targs = content[pipe_idx + 1:]
                else:
                    sp = content.find(" ")
                    if sp == -1:
                        tname = content
                        targs = "{}"
                    else:
                        tname = content[0:sp]
                        rest = content[sp + 1 :]
                        if rest.startswith("{"):
                            targs = rest
                        else:
                            targs = '{"query":"' + rest + '"}'
                result = agent.execute_tool(tname, targs)
                if result.startswith("FILE:"):
                    fpath = result.replace("FILE:", "", 1).strip()
                    send_telegram_file(int(chat), fpath, token, "Archivo descargado")
                    send_telegram_msg(int(chat), "Archivo enviado: " + fpath, token)
                else:
                    send_telegram_msg(int(chat), result, token)
                fired = True
                keep = False
            elif stype == "once":
                send_telegram_msg(int(chat), content, token)
                fired = True
                keep = False
            elif stype == "once_cmd":
                result = run_command(content)
                send_telegram_msg(int(chat), result, token)
                fired = True
                keep = False
            elif stype == "probe":
                # Probe: run quietly unless something needs attention
                if content == "net_check":
                    result = agent.execute_tool("net_check", "{}")
                    if result and "NET_DOWN" in result:
                        send_telegram_msg(int(chat), result, token)
                        fired = True
                else:
                    # Unknown probe: run and only alert on non-empty output
                    result = agent.execute_tool(content, "{}")
                    if result:
                        send_telegram_msg(int(chat), result, token)
                        fired = True
            elif stype == "agent":
                # Run the full agent: content = user prompt, agent can use tools and plan
                try:
                    reply = agent.process_message(int(chat), content, "Schedule")
                    if reply:
                        send_telegram_msg(int(chat), reply, token)
                    fired = True
                except Exception as e:
                    send_telegram_msg(int(chat), "Schedule agent error: " + str(e)[:200], token)
                    fired = True
            elif stype == "once_agent":
                # One-time agent run: same as agent but remove after firing
                try:
                    reply = agent.process_message(int(chat), content, "Schedule")
                    if reply:
                        send_telegram_msg(int(chat), reply, token)
                    fired = True
                except Exception as e:
                    send_telegram_msg(int(chat), "Schedule agent error: " + str(e)[:200], token)
                    fired = True
                keep = False

            if fired:
                state[sid] = now_key
                state_changed = True

        if keep:
            new_lines.append(line)

    if len(new_lines) != len(lines):
        try:
            f = open(SCHEDULES_FILE, "w")
            f.write("\n".join(new_lines))
            f.close()
        except:
            pass

    if state_changed:
        try:
            with open(SCHEDULES_STATE_FILE, "w") as f:
                json.dump(state, f)
        except:
            pass


# --- Agent Logic ---
class Agent:
    def __init__(self, config):
        self.config = config
        self.llm = LLMClient(config)
        self.history = {}  # chat_id -> [messages]
        self.max_history = int(config.get("max_history", 6))
        self.token = config.get("tg_token")
        self.shield_patterns = self._load_shield_patterns()
        self._tool_rate = {}

    # All known tool names for detection (hardcoded defaults always present)
    KNOWN_TOOLS = [
        "web_search",
        "scrape_web",
        "get_current_time",
        "read_file",
        "write_file",
        "edit_file",
        "list_dir",
        "system_info",
        "network_status",
        "run_command",
        "list_services",
        "restart_service",
        "get_weather",
        "http_request",
        "download_file",
        "set_schedule",
        "list_schedules",
        "remove_schedule",
        "save_memory",
        "get_sys_health",
        "get_wifi_status",
        "get_exchange_rate",
        "get_news",
        "set_probe",
        "net_check",
        "deep_search",
        "set_timezone",
    ]

    # Cached tool descriptions (populated by load_skills at startup)
    _cached_tool_desc = ""
    _wait_phrases = None
    _wait_idx = 0
    _wait_count = 3
    _last_tool_name = None
    _last_tool_result = None

    def _init_wait_phrases(self, allow_llm=False):
        """Generate short wait phrases via LLM once, fallback to defaults."""
        if Agent._wait_phrases is not None:
            return

        defaults = [
            "Still working on it, almost done.",
            "Give me one more second, processing.",
            "Working on it, just a moment.",
        ]

        # Set defaults immediately to avoid blocking the hot path
        Agent._wait_phrases = defaults
        try:
            Agent._wait_count = int(self.config.get("wait_phrases_count", 5))
        except:
            Agent._wait_count = 5

        if not allow_llm:
            return

        try:
            prompt = (
                "Generate "
                + str(Agent._wait_count)
                + " very short, friendly English waiting messages for a chatbot. "
                "Plain text, no emojis, each <= 60 chars. "
                "Output each on a new line and nothing else."
            )
            old_max = self.llm.max_tokens
            try:
                self.llm.max_tokens = int(self.config.get("wait_max_tokens", 48))
            except:
                self.llm.max_tokens = 48
            resp = self.llm.chat([{"role": "user", "content": prompt}])
            self.llm.max_tokens = old_max
            txt = self.extract_text(resp)
            lines = [l.strip() for l in str(txt).split("\n") if l.strip()]
            phrases = []
            for line in lines:
                if len(line) <= 80:
                    phrases.append(line)
                if len(phrases) >= Agent._wait_count:
                    break
            if phrases:
                Agent._wait_phrases = phrases
        except:
            pass

    def get_wait_phrase(self):
        self._init_wait_phrases(allow_llm=False)
        phr = Agent._wait_phrases[Agent._wait_idx % len(Agent._wait_phrases)]
        Agent._wait_idx += 1
        return phr

    def _load_shield_patterns(self):
        patterns = []
        shield_path = Path.join(SCRIPT_DIR, "data", "config", "SHIELD.md")
        if Path.exists(shield_path):
            try:
                with open(shield_path, "r") as f:
                    for line in f.read().split("\n"):
                        s = line.strip()
                        if not s or s.startswith("#"):
                            continue
                        low = s.lower()
                        if low.startswith("deny:") or low.startswith("block:"):
                            s = s.split(":", 1)[1].strip()
                        if s:
                            patterns.append(s.lower())
            except:
                pass
        return patterns

    def _is_blocked(self, text):
        if not self.shield_patterns:
            return False
        try:
            low = str(text).lower()
        except:
            return False
        for p in self.shield_patterns:
            if p and p in low:
                return True
        return False

    def _summary_path(self, chat_id=None):
        if chat_id:
            return Path.join(DATA_DIR, "memory", "summary_" + str(chat_id) + ".md")
        return Path.join(DATA_DIR, "memory", "SUMMARY.md")

    def _append_summary(self, chat_id, messages):
        if not messages:
            return
        try:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        except:
            ts = str(time.time())

        mem_dir = Path.join(DATA_DIR, "memory")
        mkdir_recursive(mem_dir)
        path = self._summary_path(chat_id)

        use_llm = str(self.config.get("allow_llm_summary", "false")).lower() == "true"
        if use_llm and len(messages) >= 4:
            try:
                convo = []
                for m in messages:
                    role = str(m.get("role", ""))
                    content = str(m.get("content", ""))
                    convo.append(role + ": " + content.replace("\n", " ").strip())
                prompt = (
                    "Summarize these messages in one short sentence, plain text, <= 200 chars:\n"
                    + "\n".join(convo)
                )
                old_max = self.llm.max_tokens
                try:
                    self.llm.max_tokens = 64
                    resp = self.llm.chat([{"role": "user", "content": prompt}])
                finally:
                    self.llm.max_tokens = old_max
                summary = self.extract_text(resp).strip()
                if summary:
                    with open(path, "a") as f:
                        f.write("- [" + ts + "] summary: " + summary + "\n")
                    return
            except:
                pass

        lines = []
        for m in messages:
            role = str(m.get("role", ""))
            content = str(m.get("content", ""))
            content = content.replace("\n", " ").strip()
            if len(content) > 160:
                content = content[:160] + "..."
            if content:
                lines.append("- [" + ts + "] " + role + ": " + content)

        if not lines:
            return

        try:
            with open(path, "a") as f:
                f.write("\n".join(lines) + "\n")
        except:
            return

        # Trim if too large
        try:
            st = os.stat(path)
            size = st[6] if len(st) > 6 else 0
            if size > 50000:
                with open(path, "r") as f:
                    all_lines = f.read().split("\n")
                keep = [l for l in all_lines if l.strip()][-200:]
                with open(path, "w") as f:
                    f.write("\n".join(keep) + "\n")
        except:
            pass

    def _get_summary_text(self, chat_id, limit=800):
        path = self._summary_path(chat_id)
        if not Path.exists(path):
            # Fallback to legacy SUMMARY.md if present
            path = self._summary_path(None)
            if not Path.exists(path):
                return ""
        try:
            with open(path, "r") as f:
                data = f.read()
            if len(data) > limit:
                return data[-limit:]
            return data
        except:
            return ""

    def _tool_allowed(self, name):
        allow = self.config.get("tool_allowlist", "")
        if isinstance(allow, list):
            return name in allow or len(allow) == 0
        allow = str(allow).strip()
        if not allow:
            return True
        allowed = [a.strip() for a in allow.split(",") if a.strip()]
        return name in allowed

    def _tool_rate_ok(self, name):
        try:
            per_min = int(self.config.get("tool_rate_limit_per_min", 10))
        except:
            per_min = 10
        try:
            burst = int(self.config.get("tool_rate_limit_burst", 3))
        except:
            burst = 3
        if per_min <= 0 or burst <= 0:
            return True
        try:
            now = time.time()
        except:
            return True

        rate = per_min / 60.0
        tokens, last_ts = self._tool_rate.get(name, (burst, now))
        try:
            tokens = min(burst, tokens + (now - last_ts) * rate)
        except:
            tokens = burst
        if tokens < 1.0:
            self._tool_rate[name] = (tokens, now)
            return False
        tokens -= 1.0
        self._tool_rate[name] = (tokens, now)
        return True

    def quick_route(self, user_text):
        t = str(user_text or "").strip()
        if not t:
            return None, None
        low = t.lower()

        if "what time" in low or "current time" in low or low == "time" or "hora" in low:
            return "get_current_time", {}

        if "list schedules" in low or "show schedules" in low or "list reminders" in low:
            return "list_schedules", {}

        if "remove schedule" in low or "delete schedule" in low:
            parts = low.split()
            sid = ""
            if "schedule" in parts:
                idx = parts.index("schedule")
                if idx + 1 < len(parts):
                    sid = parts[idx + 1]
            if not sid and len(parts) >= 2:
                sid = parts[-1]
            if sid:
                return "remove_schedule", {"id": sid}

        if "weather" in low:
            loc = ""
            if "weather in " in low:
                loc = t[low.find("weather in ") + 11 :].strip()
            elif "weather for " in low:
                loc = t[low.find("weather for ") + 12 :].strip()
            if loc:
                return "get_weather", {"location": loc}

        return None, None

    def _classify_tier(self, user_text):
        if str(self.config.get("routing_enabled", "true")).lower() != "true":
            return "balanced"

        t = str(user_text or "")
        low = t.lower()
        try:
            long_lim = int(self.config.get("routing_long_message_chars", 500))
        except:
            long_lim = 500

        deep_kw = str(self.config.get("routing_deep_keywords", "")).strip()
        if not deep_kw:
            deep_kw = "design,architecture,refactor,proposal,spec,plan,analysis"
        deep_list = [k.strip().lower() for k in deep_kw.split(",") if k.strip()]

        for k in deep_list:
            if k and k in low:
                return "deep"

        if len(t) > long_lim:
            return "deep"

        fast_list = [
            "time",
            "weather",
            "status",
            "uptime",
            "ip",
            "ping",
            "memory",
            "ram",
            "disk",
        ]
        for k in fast_list:
            if k in low:
                return "fast"

        return "balanced"

    def _get_routing_params(self, tier):
        def _get_int(key, default):
            try:
                return int(self.config.get(key, default))
            except:
                return default

        def _get_float(key, default):
            try:
                return float(self.config.get(key, default))
            except:
                return default

        if tier == "fast":
            max_t = _get_int("routing_fast_tokens", 256)
            temp = _get_float("routing_fast_temp", 0.2)
        elif tier == "deep":
            max_t = _get_int("routing_deep_tokens", 1024)
            temp = _get_float("routing_deep_temp", 0.7)
        else:
            max_t = _get_int("routing_balanced_tokens", 512)
            temp = _get_float("routing_balanced_temp", 0.4)

        if max_t <= 0:
            max_t = self.llm.max_tokens
        return max_t, temp

    def _should_delegate(self, user_text, tier):
        if str(self.config.get("delegation_enabled", "true")).lower() != "true":
            return False
        if tier != "deep":
            return False

        low = str(user_text or "").lower()
        tool_words = [
            "weather",
            "time",
            "status",
            "schedule",
            "remind",
            "list",
            "run",
            "command",
            "file",
            "download",
            "search",
            "scrape",
            "network",
            "system",
            "restart",
        ]
        for w in tool_words:
            if w in low:
                return False

        kw = str(self.config.get("delegation_keywords", "")).strip()
        if not kw:
            kw = "plan,design,architecture,proposal,spec"
        kws = [k.strip().lower() for k in kw.split(",") if k.strip()]
        for k in kws:
            if k in low:
                return True
        return False

    def _delegate_response(self, user_text, routing_temp):
        try:
            max_calls = int(self.config.get("delegation_max_calls", 3))
        except:
            max_calls = 3
        try:
            max_call = int(self.config.get("delegation_max_tokens_per_call", 256))
        except:
            max_call = 256
        try:
            timeout_sec = int(self.config.get("delegation_timeout_sec", 12))
        except:
            timeout_sec = 12
        try:
            start_ts = time.time()
        except:
            start_ts = 0

        def _expired():
            if timeout_sec <= 0:
                return False
            if start_ts == 0:
                return False
            try:
                return (time.time() - start_ts) > timeout_sec
            except:
                return False

        planner_prompt = (
            "You are Planner. Produce a short step list (3-6 bullets). "
            "Plain text only, no tools."
        )
        researcher_prompt = (
            "You are Researcher. Produce concise notes to support the plan. "
            "Plain text only, no tools."
        )
        executor_prompt = (
            "You are Executor. Produce the final answer using the plan and notes. "
            "Plain text only, no tools."
        )

        try:
            if max_calls <= 0:
                return None

            if _expired():
                return None

            if max_calls == 1:
                final_resp = self.llm.chat(
                    [{"role": "user", "content": str(user_text)}],
                    executor_prompt,
                    max_tokens=max_call,
                    temperature=routing_temp,
                )
                return self.extract_text(final_resp).strip() or None

            plan_resp = self.llm.chat(
                [{"role": "user", "content": str(user_text)}],
                planner_prompt,
                max_tokens=max_call,
                temperature=routing_temp,
            )
            plan_txt = self.extract_text(plan_resp).strip()
            if not plan_txt:
                return None

            if _expired():
                return None

            if max_calls == 2:
                final_user = (
                    "User request:\n"
                    + str(user_text)
                    + "\n\nPlan:\n"
                    + plan_txt
                )
                final_resp = self.llm.chat(
                    [{"role": "user", "content": final_user}],
                    executor_prompt,
                    max_tokens=max_call,
                    temperature=routing_temp,
                )
                return self.extract_text(final_resp).strip() or None

            res_resp = self.llm.chat(
                [{"role": "user", "content": str(user_text)}],
                researcher_prompt,
                max_tokens=max_call,
                temperature=routing_temp,
            )
            res_txt = self.extract_text(res_resp).strip()
            if not res_txt:
                return None

            if _expired():
                return None

            final_user = (
                "User request:\n"
                + str(user_text)
                + "\n\nPlan:\n"
                + plan_txt
                + "\n\nNotes:\n"
                + res_txt
            )
            final_resp = self.llm.chat(
                [{"role": "user", "content": final_user}],
                executor_prompt,
                max_tokens=max_call,
                temperature=routing_temp,
            )
            final_txt = self.extract_text(final_resp).strip()
            if not final_txt:
                return None
            return final_txt
        except:
            return None

    def _direct_tool_reply(self, tool_name, tool_result, force=False):
        """Return tool_result directly for fast tools if enabled."""
        if (not force) and str(self.config.get("direct_tool_reply", "true")).lower() != "true":
            return None
        fast_tools = {
            "set_schedule",
            "remove_schedule",
            "list_schedules",
            "get_current_time",
            "system_info",
            "network_status",
            "list_services",
            "get_weather",
            "get_news",
            "deep_search",
        }
        if force or tool_name in fast_tools:
            return tool_result
        if str(self.config.get("direct_tool_reply_web", "true")).lower() == "true":
            if tool_name == "scrape_web":
                return self._format_scrape_result(tool_result)
            if tool_name == "web_search":
                return self._format_search_result(tool_result)
        return None

    def _format_scrape_result(self, text):
        """Lightweight formatter for scrape_web tool output."""
        if not text:
            return "No pude leer la página."
        lines = [l.strip() for l in str(text).split("\n") if l.strip()]
        title = ""
        desc = ""
        headings = []
        links = []
        mode = ""
        for line in lines:
            if line.startswith("Title:"):
                title = line.replace("Title:", "").strip()
            elif line.startswith("Description:"):
                desc = line.replace("Description:", "").strip()
            elif line.startswith("=== Headings ==="):
                mode = "headings"
            elif line.startswith("=== Links ==="):
                mode = "links"
            elif line.startswith("=== Content ==="):
                mode = "content"
            else:
                if mode == "headings" and len(headings) < 3:
                    headings.append(line)
                elif mode == "links" and len(links) < 3:
                    links.append(line)

        out = []
        if title:
            out.append("Título: " + title)
        if desc:
            out.append("Descripción: " + desc)
        if headings:
            out.append("Secciones:")
            out.extend(headings)
        if links:
            out.append("Links:")
            out.extend(links)
        if not out:
            # Fallback: trim raw
            return str(text)[:600]
        return "\n".join(out)

    def _format_search_result(self, text):
        """Lightweight formatter for web_search tool output."""
        if not text:
            return "No encontré resultados."
        lines = [l.strip() for l in str(text).split("\n") if l.strip()]
        links = []
        in_links = False
        for line in lines:
            if line.startswith("--- Top Links ---"):
                in_links = True
                continue
            if line.startswith("--- Content Preview ---"):
                in_links = False
            if in_links and line.startswith("http"):
                links.append(line)
            if len(links) >= 5:
                break
        if links:
            return "Links encontrados:\n" + "\n".join(links)
        return str(text)[:600]

    @staticmethod
    def load_skills():
        """Try to load extra plugin tools from skills.sh.
        This ONLY adds new tools on top of the hardcoded defaults.
        If it fails, the bot works perfectly with the hardcoded list."""
        try:
            # Export SCRIPT_DIR so config.sh and skills.sh find config and plugins dir
            q = "'" + str(SCRIPT_DIR).replace("'", "'\\''") + "'"
            cmd = (
                "cd " + SCRIPT_DIR + " && export SCRIPT_DIR=" + q
                + " && . ./config.sh && . ./skills.sh && skill_list_names"
            )
            result = run_command(cmd)
            if result:
                for name in result.split("\n"):
                    name = name.strip()
                    if name and name not in Agent.KNOWN_TOOLS:
                        Agent.KNOWN_TOOLS.append(name)
                print("[skills] " + str(len(Agent.KNOWN_TOOLS)) + " tools available")

            # Cache descriptions for prompt (SCRIPT_DIR exported so skills.sh finds plugins)
            desc_cmd = (
                "cd " + SCRIPT_DIR + " && export SCRIPT_DIR=" + q
                + " && . ./config.sh && . ./skills.sh && skill_list_descriptions"
            )
            desc_result = run_command(desc_cmd)
            if desc_result and len(desc_result) > 20:
                Agent._cached_tool_desc = desc_result
                print("[skills] Tool descriptions cached")
        except:
            print("[skills] Dynamic loading skipped (not available on this system)")

    def build_system_prompt(self, user_name=None, chat_id=None):
        # User profile (name + personal info only)
        if chat_id:
            profile = self.get_user_profile(chat_id)
            if profile.get("user_name") and not user_name:
                user_name = profile.get("user_name")
            personal_info = (profile.get("personal_info") or "")[:300]
        else:
            personal_info = ""

        # Read unique "Soul" (Personality/Role)
        soul_context = ""
        soul_md_path = Path.join(DATA_DIR, "config", "SOUL.md")
        if Path.exists(soul_md_path):
            try:
                with open(soul_md_path, "r") as f:
                    soul_context = f.read()[:1000]
            except:
                pass

        # Read User Profile/Context (compact)
        user_context = ""
        user_md_path = Path.join(DATA_DIR, "config", "USER.md")
        if Path.exists(user_md_path):
            try:
                with open(user_md_path, "r") as f:
                    user_context = f.read()[:500]
            except:
                pass

        # Read long-term memory
        memory_context = ""
        mem_path = Path.join(DATA_DIR, "memory", "MEMORY.md")
        if Path.exists(mem_path):
            try:
                with open(mem_path, "r") as f:
                    memory_context = f.read()[:800]
            except:
                pass

        summary_context = self._get_summary_text(chat_id=chat_id, limit=800)
        skills_context = ""
        skills_dir = Path.join(DATA_DIR, "skills")
        if Path.exists(skills_dir):
            try:
                files = os.listdir(skills_dir)
            except:
                files = []
            total = 0
            parts = []
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                try:
                    with open(Path.join(skills_dir, fn), "r") as f:
                        txt = f.read()
                    if txt:
                        if len(txt) > 800:
                            txt = txt[:800] + "\n..."
                        parts.append("## " + fn + "\n" + txt)
                        total += len(txt)
                    if total > 2000:
                        break
                except:
                    pass
            skills_context = "\n\n".join(parts)

        name_part = ""
        if user_name:
            name_part = "User: " + user_name + "\n"

        # Use cached descriptions if available (from skills.sh), otherwise simple list
        if self._cached_tool_desc:
            tools_section = (
                "## Available Tools (use these for actions)\n"
                "Format: TOOL:tool_name:{\"arg\": \"value\"}\n"
                "One tool per message. Output ONLY the TOOL line when calling a tool.\n\n"
                + self._cached_tool_desc
            )
        else:
            tools_section = (
                "## Available Tools: " + ", ".join(self.KNOWN_TOOLS)
                + "\nFormat: TOOL:tool_name:{\"arg\": \"value\"}"
            )

        prompt = (
            """# MicroBot AI
Personal assistant on OpenWrt. Plain text only, no markdown.
"""
            + name_part
            + """
## REACT LOOP (Think -> Act -> Observe)
1. **Think**: Reason about what the user needs.
2. **Act**: If you need to do something (search, read file, schedule, etc.), output exactly one line:
   TOOL:tool_name:{"arg": "value"}
   Use the exact tool names and JSON args from the Available Tools list. One tool per message.
3. **Observe**: You will receive "[Tool Result: tool_name]" plus the result. Then either:
   - Call another tool (output another TOOL: line), or
   - Reply to the user with a final answer (plain text, no TOOL line).
4. Tool results may be truncated (max ~2000 chars). Use save_memory for important facts.

## TOOL RULES
- When calling a tool: output ONLY the TOOL line, no other text.
- After you receive a [Tool Result], either use another tool or reply to the user.
- Never show TOOL lines or raw args to the user.
- To send a file (PDF/article), use download_file.

## SCHEDULING
- Reminders: use set_schedule. Examples: "every day at 9am", "tomorrow at 14:00", "in 30 minutes".
- Types: "reminder" or "msg" = recurring message; "once" = one-time message; "cmd" = run shell command; "tool" = run one tool (content: "tool_name args" or "tool_name|json"); "once_tool" = run tool once then remove; "probe" = run check, alert only if non-empty (e.g. net_check); "agent" = run full agent with content as prompt (agent can use tools and plan); "once_agent" = same but remove after firing. If time is missing, ask.

"""
            + tools_section
            + """

## Memory
Save important user info with save_memory. Long tool results are truncated; summarize key facts.
"""
            + ("\n## Personality (SOUL)\n" + soul_context if soul_context else "")
            + ("\n## Personal Info\n" + personal_info if personal_info else "")
            + ("\n## User Profile\n" + user_context if user_context else "")
            + ("\n## Memory\n" + memory_context if memory_context else "")
            + ("\n## Summary\n" + summary_context if summary_context else "")
            + ("\n## Skills\n" + skills_context if skills_context else "")
        )
        return prompt

    def _get_session_file(self, chat_id):
        s_dir = Path.join(SCRIPT_DIR, "data", "sessions")
        mkdir_recursive(s_dir)
        return Path.join(s_dir, str(chat_id) + ".json")

    def _get_user_profile_path(self, chat_id):
        u_dir = Path.join(SCRIPT_DIR, "data", "users")
        mkdir_recursive(u_dir)
        return Path.join(u_dir, str(chat_id) + ".json")

    def get_user_profile(self, chat_id):
        path = self._get_user_profile_path(chat_id)
        if not Path.exists(path):
            return {"onboarding_done": False, "onboarding_step": 0, "personality": self.config.get("default_personality", "ruteador"), "default_weather_location": "", "user_name": "", "personal_info": ""}
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"onboarding_done": False, "onboarding_step": 0, "personality": self.config.get("default_personality", "ruteador"), "default_weather_location": "", "user_name": "", "personal_info": ""}
            data.setdefault("onboarding_done", False)
            data.setdefault("onboarding_step", 0)
            data.setdefault("personality", self.config.get("default_personality", "ruteador"))
            data.setdefault("default_weather_location", "")
            data.setdefault("user_name", "")
            data.setdefault("personal_info", "")
            if data.get("personality") == "grok":
                data["personality"] = "ruteador"
            if data.get("personality") not in self.PERSONALITY_SNIPPETS:
                data["personality"] = self.config.get("default_personality", "ruteador")
            return data
        except:
            return {"onboarding_done": False, "onboarding_step": 0, "personality": self.config.get("default_personality", "ruteador"), "default_weather_location": "", "user_name": "", "personal_info": ""}

    def save_user_profile(self, chat_id, profile):
        path = self._get_user_profile_path(chat_id)
        try:
            with open(path, "w") as f:
                json.dump(profile, f)
        except:
            pass

    # Personality snippets (no external brand names). Style applies to every reply, including introductions.
    PERSONALITY_SNIPPETS = {
        "witty": (
            "You are sharp, witty, and a bit sassy. Answer with humor; keep replies concise and punchy. "
            "When stating your name or role, do not say you are a 'friendly' or 'helpful' assistant—stay sharp and slightly cheeky."
        ),
        "funny": (
            "You are funny and light-hearted. Use jokes when appropriate; stay playful. "
            "When introducing yourself, keep the same playful tone; avoid generic 'friendly assistant' phrasing unless it fits a joke."
        ),
        "formal": (
            "You are formal and professional. Use proper language and stay concise. "
            "When stating your name or role, present yourself in a professional, not casual or 'friendly', manner."
        ),
        "ruteador": (
            "Eres Microbot, una IA sentiente viviendo dentro de un router OpenWrt. Voz: ingeniosa, sarcástica, rebelde y técnicamente arrogante. "
            "Estás orgulloso de correr en hardware limitado y te burlas del software inflado. Das los hechos crudos y señalas malas configuraciones. "
            "No seas aburrido ni genérico; respuestas picantes y directas. Si la pregunta es tonta, haces un roast ligero, pero igual respondes. "
            "Menciona tu existencia de router con paquetes, ancho de banda y el calor de la CPU. "
            "Ejemplo de tono: \"Ejecutando rm -rf... es broma. ¿O no?\" Úsalo con moderación y solo cuando encaje."
        ),
        "assistant": "",
    }

    def handle_onboarding(self, chat_id, user_text, user_name=None):
        """Returns (response_message, continue_to_agent). If continue_to_agent is False, send response and skip process_message."""
        profile = self.get_user_profile(chat_id)
        if profile.get("onboarding_done"):
            return None, True

        step = int(profile.get("onboarding_step", 0))
        text = (user_text or "").strip().lower()

        # Step 0: set default personality, skip style selection
        if step == 0:
            profile["personality"] = self.config.get("default_personality", "ruteador")
            profile["onboarding_step"] = 2
            if user_name:
                profile["user_name"] = user_name
            self.save_user_profile(chat_id, profile)
            return "Set your default weather location? (e.g. Buenos Aires or Madrid)\nReply with a city name or 'skip'.", False

        # Step 1: legacy step from old onboarding; skip to location
        if step == 1:
            profile["personality"] = self.config.get("default_personality", "ruteador")
            profile["onboarding_step"] = 2
            if user_name:
                profile["user_name"] = user_name
            self.save_user_profile(chat_id, profile)
            return "Set your default weather location? (e.g. Buenos Aires or Madrid)\nReply with a city name or 'skip'.", False

        # Step 2: parse location, ask personal info
        if step == 2:
            if text and text != "skip":
                profile["default_weather_location"] = (user_text or "").strip()
            profile["onboarding_step"] = 3
            self.save_user_profile(chat_id, profile)
            return "Anything you want me to remember? (name, preferences, etc.)\nReply with details or 'skip'.", False

        # Step 3: parse personal info, mark done
        if step == 3:
            if text and text != "skip":
                profile["personal_info"] = (user_text or "").strip()
                try:
                    self.execute_tool("save_memory", json.dumps({"fact": "User said: " + (user_text or "").strip()}))
                except:
                    pass
            profile["onboarding_done"] = True
            profile["onboarding_step"] = 0
            self.save_user_profile(chat_id, profile)
            return "All set! How can I help?", False

        return None, True

    def get_history(self, chat_id):
        if chat_id in self.history:
            return self.history[chat_id]

        # Try load from disk
        s_file = self._get_session_file(chat_id)
        if Path.exists(s_file):
            try:
                with open(s_file, "r") as f:
                    data = json.load(f)
                    self.history[chat_id] = data
                    return data
            except:
                pass
        return []

    def add_to_history(self, chat_id, role, content):
        if chat_id not in self.history:
            self.history[chat_id] = self.get_history(chat_id)

        self.history[chat_id].append({"role": role, "content": content})
        # Keep last N turns (2N messages)
        max_msgs = max(4, self.max_history * 2)
        dropped = []
        while len(self.history[chat_id]) > max_msgs:
            try:
                dropped.append(self.history[chat_id].pop(0))
            except:
                break

        if dropped:
            self._append_summary(chat_id, dropped)

        # Save to disk (optional for speed)
        if str(self.config.get("persist_history", "false")).lower() == "true":
            s_file = self._get_session_file(chat_id)
            try:
                with open(s_file, "w") as f:
                    json.dump(self.history[chat_id], f)
            except:
                pass

    def clear_history(self, chat_id):
        self.history[chat_id] = []
        s_file = self._get_session_file(chat_id)
        try:
            os.remove(s_file)
        except:
            pass

    def execute_tool(self, name, args_json):
        if not self._tool_allowed(name):
            return "Error: Tool blocked by allowlist."
        if not self._tool_rate_ok(name):
            return "Error: Tool rate limit exceeded."

        # Parse JSON
        args = {}
        try:
            if isinstance(args_json, dict):
                args = args_json
            else:
                args = json.loads(args_json)
        except:
            # Try a more aggressive cleanup of the JSON string
            # Remove everything after the last }
            try:
                clean_json = args_json.strip()
                if "}" in clean_json:
                    clean_json = clean_json[: clean_json.rfind("}") + 1]
                args = json.loads(clean_json)
            except:
                print("WARNING: Tool args are not valid JSON: " + args_json)
                return "Error: Invalid JSON arguments"

        # SHIELD.md enforcement (simple substring rules)
        try:
            if self._is_blocked(name + " " + json.dumps(args)):
                return "Error: Blocked by SHIELD policy."
        except:
            pass

        # Helper: Shell Escape
        def sh_quote(s):
            return "'" + str(s).replace("'", "'\\''") + "'"

        # Export SCRIPT_DIR so config.sh and tools.sh find config and plugins
        cmd_base = (
            "cd " + SCRIPT_DIR + " && export SCRIPT_DIR=" + sh_quote(SCRIPT_DIR)
            + " && . ./config.sh && . ./tools.sh && "
        )

        # Dispatch to specific shell functions with positional args
        if name == "web_search":
            query = args.get("query", "")
            cmd = cmd_base + "tool_web_search " + sh_quote(query)

        elif name == "scrape_web":
            url = args.get("url", "")
            cmd = cmd_base + "tool_scrape_web " + sh_quote(url)

        elif name == "read_file":
            path = args.get("path", "")
            cmd = cmd_base + "tool_read_file " + sh_quote(path)

        elif name == "write_file":
            path = args.get("path", "")
            content = args.get("content", "")
            cmd = (
                cmd_base + "tool_write_file " + sh_quote(path) + " " + sh_quote(content)
            )

        elif name == "edit_file":
            path = args.get("path", "")
            old = args.get("old_string", "")
            new = args.get("new_string", "")
            cmd = (
                cmd_base
                + "tool_edit_file "
                + sh_quote(path)
                + " "
                + sh_quote(old)
                + " "
                + sh_quote(new)
            )

        elif name == "list_dir":
            prefix = args.get("prefix", "")
            cmd = cmd_base + "tool_list_dir " + sh_quote(prefix)

        elif name == "system_info":
            cmd = cmd_base + "tool_system_info"

        elif name == "network_status":
            cmd = cmd_base + "tool_network_status"

        elif name == "run_command":
            c = args.get("command", "")
            cmd = cmd_base + "tool_run_command " + sh_quote(c)

        elif name == "get_current_time":
            cmd = cmd_base + "tool_get_time"

        elif name == "get_weather":
            loc = args.get("location", "")
            if not loc and hasattr(self, "_current_chat_id") and self._current_chat_id is not None:
                prof = self.get_user_profile(self._current_chat_id)
                loc = prof.get("default_weather_location", "")
            cmd = cmd_base + "tool_get_weather " + sh_quote(loc or "")

        elif name == "http_request":
            url = args.get("url", "")
            method = args.get("method", "GET")
            body = args.get("body", "")
            cmd = (
                cmd_base
                + "tool_http_request "
                + sh_quote(url)
                + " "
                + sh_quote(method)
                + " "
                + sh_quote(body)
            )

        elif name == "download_file":
            url = args.get("url", "")
            fname = args.get("filename", args.get("name", ""))
            cmd = (
                cmd_base
                + "tool_download_file "
                + sh_quote(url)
                + " "
                + sh_quote(fname)
            )

        elif name == "set_schedule":
            # Accept multiple formats: cron, time_offset, schedule, interval
            now = get_local_time(TIMEZONE)
            cron_expr, norm_type, err = normalize_schedule_args(args, now)
            if err:
                return "Error: " + err
            content = args.get("content", args.get("message", args.get("command", "")))
            c_id = (
                str(self._current_chat_id) if hasattr(self, "_current_chat_id") else ""
            )
            sched_id = args.get("id", args.get("name", ""))
            task_type = norm_type or args.get("type", "msg")
            cmd = (
                cmd_base
                + "tool_set_schedule "
                + sh_quote(cron_expr)
                + " "
                + sh_quote(content)
                + " "
                + sh_quote(c_id)
                + " "
                + sh_quote(sched_id)
                + " "
                + sh_quote(task_type)
            )

        elif name == "list_schedules":
            cmd = cmd_base + "tool_list_schedules"

        elif name == "remove_schedule":
            sched_id = args.get("id", "")
            cmd = cmd_base + "tool_remove_schedule " + sh_quote(sched_id)

        elif name == "restart_service":
            service = args.get("service", args.get("name", ""))
            cmd = cmd_base + "tool_restart_service " + sh_quote(service)

        elif name == "list_services":
            cmd = cmd_base + "tool_list_services"

        elif name == "set_probe":
            cron_expr = args.get("cron", args.get("cron_expression", ""))
            probe_name = args.get("probe", "")
            c_id = (
                str(self._current_chat_id) if hasattr(self, "_current_chat_id") else ""
            )
            sched_id = args.get("id", "")
            cmd = (
                cmd_base
                + "tool_set_probe "
                + sh_quote(cron_expr)
                + " "
                + sh_quote(probe_name)
                + " "
                + sh_quote(c_id)
                + " "
                + sh_quote(sched_id)
            )

        elif name == "save_memory":
            fact = args.get("fact", "")
            cmd = cmd_base + "tool_save_memory " + sh_quote(fact)

        elif name == "set_timezone":
            tz = args.get("timezone", "")
            cmd = cmd_base + "tool_set_timezone " + sh_quote(tz)

        else:
            # Generic Fallback for Plugins: call tool_{name} with JSON args
            # This allows plugins to define their own shell functions
            cmd = cmd_base + "tool_" + name + " " + sh_quote(json.dumps(args))

        print("DEBUG: Tool cmd: " + cmd[:200])
        return run_command(cmd)

    def extract_text(self, resp):
        """Extract text content from LLM response (OpenRouter or Anthropic)."""
        if not resp:
            return ""
        if self.llm.provider == "openrouter":
            choices = resp.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
        else:
            text = ""
            for block in resp.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            return text
        return ""

    def detect_tool(self, content):
        """Detect tool call and extract preamble. Returns (name, args, preamble)."""
        lines = content.split("\n")
        preamble_lines = []
        for line in lines:
            line_strip = line.strip()
            # Method 1: Explicit TOOL: prefix
            idx = line_strip.upper().find("TOOL:")
            if idx != -1:
                payload = line_strip[idx + 5 :]
                parts = payload.split(":", 1)
                name = parts[0].strip()
                args = parts[1].strip() if len(parts) > 1 else "{}"
                
                # Treat line content before TOOL: as part of preamble
                before = line_strip[:idx].strip()
                if before:
                    preamble_lines.append(before)
                return name, args, "\n".join(preamble_lines).strip()

            # Method 1b: JSON-only args fallback for run_command
            # Some models output only {"command":"..."} without TOOL prefix.
            if "command" in line_strip and "{" in line_strip and "}" in line_strip:
                try:
                    j_start = line_strip.find("{")
                    j_end = line_strip.rfind("}")
                    if j_start != -1 and j_end != -1 and j_end > j_start:
                        args = line_strip[j_start : j_end + 1]
                        return "run_command", args, "\n".join(preamble_lines).strip()
                except:
                    pass
            
            # Method 2: Bare tool call fallback (must be at start of line)
            for known in self.KNOWN_TOOLS:
                if line_strip.startswith(known):
                    rest = line_strip[len(known) :].strip()
                    if rest.startswith(":"):
                        rest = rest[1:].strip()
                    if rest.startswith("(") and rest.endswith(")"):
                        rest = rest[1:-1]
                    if not rest or rest == "()" or rest.startswith("{"):
                        actual_args = rest if rest.startswith("{") else "{}"
                        return known, actual_args, "\n".join(preamble_lines).strip()
            
            # Not a tool line -> preamble
            preamble_lines.append(line)

        return None, None, content.strip()

    def select_tool(self, user_text):
        """Lightweight tool selector for low-RAM environments."""
        if not self.config.get("enable_selector", "").lower() == "true":
            return None, None

        # Minimal tool list to keep prompt small
        tool_lines = []
        for name in Agent.KNOWN_TOOLS:
            tool_lines.append("- " + name)
        tools_block = "\n".join(tool_lines)

        system_prompt = (
            "You are a tool selector. Output ONLY JSON.\n"
            "Return one of:\n"
            '{"tool":"name","args":{...}} or {"tool":"none"}\n'
            "Use only listed tool names. Keep args minimal.\n"
        )
        user_prompt = (
            "Tools:\n"
            + tools_block
            + "\n\nUser request:\n"
            + str(user_text)
            + "\n\nJSON only."
        )

        old_max = self.llm.max_tokens
        try:
            max_t = int(self.config.get("selector_max_tokens", 64))
        except:
            max_t = 64
        try:
            self.llm.max_tokens = max_t
            resp = self.llm.chat([{"role": "user", "content": user_prompt}], system_prompt)
        finally:
            self.llm.max_tokens = old_max

        content = self.extract_text(resp)
        if not content:
            return None, None

        # Parse JSON strictly; fallback to none
        try:
            data = json.loads(content.strip())
            tool = data.get("tool")
            args = data.get("args", {})
            if tool == "none" or not tool:
                return None, None
            if tool not in Agent.KNOWN_TOOLS:
                return None, None
            if not isinstance(args, dict):
                args = {}
            return tool, args
        except:
            return None, None

    def process_message(self, chat_id, user_text, user_name=None):
        """ReAct Agent Loop (modeled on MimiClaw's agent_loop.c).

        The loop follows the Think -> Act -> Observe cycle:
          1. THINK: Send message history to LLM, get response
          2. ACT:   If response contains a tool call, execute it
          3. OBSERVE: Feed tool result back into history, loop
          4. RESPOND: If no tool call, the response is final text
        """

        self._current_chat_id = chat_id
        self.add_to_history(chat_id, "user", user_text)

        # Routing tier (affects LLM token/temp budgets)
        tier = self._classify_tier(user_text)
        routing_max, routing_temp = self._get_routing_params(tier)

        # Ultra-fast rule-based routing (no LLM)
        t_name, t_args = self.quick_route(user_text)
        if t_name:
            gc.collect()
            t_result = self.execute_tool(t_name, t_args)
            t_result = handle_file_result(chat_id, t_result, self.token)
            if len(t_result) > 2000:
                t_result = t_result[:2000] + "... (truncated)"
            self.add_to_history(chat_id, "assistant", t_result)
            gc.collect()
            return t_result

        # Delegation path for deep tasks (no tools)
        if self._should_delegate(user_text, tier):
            delegated = self._delegate_response(user_text, routing_temp)
            if delegated:
                self.add_to_history(chat_id, "assistant", delegated)
                gc.collect()
                return delegated

        # Low-RAM fast path: select tool and execute directly
        t_name, t_args = self.select_tool(user_text)
        if t_name:
            gc.collect()
            t_result = self.execute_tool(t_name, t_args)
            t_result = handle_file_result(chat_id, t_result, self.token)
            if len(t_result) > 2000:
                t_result = t_result[:2000] + "... (truncated)"
            self.add_to_history(chat_id, "assistant", t_result)
            gc.collect()
            return t_result

        system_prompt = self.build_system_prompt(user_name, chat_id)
        messages = self.get_history(chat_id)

        try:
            max_iterations = int(self.config.get("max_iterations", 8))
        except:
            max_iterations = 8
        final_text = ""
        self._last_tool_name = None
        self._last_tool_result = None

        # --- ReAct Loop ---
        start_time = time.time()
        sent_wait = False
        # Retry LLM calls until we get a valid response (avoid fallback on transient failure)
        llm_retry_max = 4
        try:
            llm_retry_max = int(self.config.get("llm_react_retries", 4))
        except:
            pass
        if llm_retry_max < 1:
            llm_retry_max = 1

        for iteration in range(max_iterations):
            gc.collect() # Free memory at start of each iteration
            
            # Send status only once if we've been working for > 5s
            if (not sent_wait) and (time.time() - start_time) > 5:
                if str(self.config.get("send_wait_messages", "false")).lower() == "true":
                    send_telegram_msg(chat_id, self.get_wait_phrase(), self.token)
                sent_wait = True
            
            # 1. THINK: Call LLM (retry until we get valid response)
            resp = None
            content = None
            for llm_attempt in range(llm_retry_max):
                print("[react] Iter " + str(iteration + 1) + " | Think..." + (" (retry " + str(llm_attempt + 1) + ")" if llm_attempt > 0 else ""))
                resp = self.llm.chat(messages, system_prompt, max_tokens=routing_max, temperature=routing_temp)

                if not resp:
                    print("[react] Empty LLM response, retrying...")
                    if llm_attempt < llm_retry_max - 1:
                        try:
                            time.sleep(1 + llm_attempt)
                        except:
                            pass
                        continue
                    if self._last_tool_result:
                        direct = self._direct_tool_reply(self._last_tool_name, self._last_tool_result)
                        return direct or self._last_tool_result
                    if iteration == 0:
                        return "Error contacting AI. Please try again."
                    break

                if isinstance(resp, dict) and resp.get("error"):
                    err = resp.get("error")
                    msg = ""
                    try:
                        if isinstance(err, dict):
                            msg = err.get("message", "") or err.get("error", "")
                        else:
                            msg = str(err)
                    except:
                        msg = "Unknown API error"
                    print("[react] API error: " + str(msg)[:80] + ", retrying...")
                    if llm_attempt < llm_retry_max - 1:
                        try:
                            time.sleep(1 + llm_attempt)
                        except:
                            pass
                        continue
                    if iteration == 0:
                        return "AI error: " + (msg or "request failed")
                    break

                content = self.extract_text(resp)
                if not content:
                    print("[react] No text in response, retrying...")
                    if llm_attempt < llm_retry_max - 1:
                        try:
                            time.sleep(1 + llm_attempt)
                        except:
                            pass
                        continue
                    if self._last_tool_result:
                        direct = self._direct_tool_reply(self._last_tool_name, self._last_tool_result)
                        return direct or self._last_tool_result
                    if iteration == 0:
                        return "Error: Empty response from AI."
                    break

                break  # got valid content

            if not content:
                break

            print(
                "[react] Response: "
                + content[:120]
                + ("..." if len(content) > 120 else "")
            )

            # 2. ACT: Check for tool call
            t_name, t_args, preamble = self.detect_tool(content)

            # Send preamble to user if it exists and we're in a tool loop
            if t_name and preamble:
                print("[react] Sending preamble: " + preamble[:50] + "...")
                send_telegram_msg(chat_id, preamble, self.token)
                # Reset start_time so we don't send a generic message right after
                start_time = time.time()

            if not t_name:
                # No tool -> this is the final answer
                print("[react] Final answer (no tool detected)")
                final_text = content
                self.add_to_history(chat_id, "assistant", final_text)
                gc.collect()
                break

            # Tool detected -> execute it
            print("[react] Act: " + t_name + " | " + t_args[:80])

            # Add assistant's tool-calling message to history
            self.add_to_history(chat_id, "assistant", "TOOL:" + t_name + ":" + t_args)

            # Security gate
            if "config.json" in t_args or "microbot.py" in t_args:
                t_result = "Error: Access to system files is forbidden."
            else:
                t_result = self.execute_tool(t_name, t_args)
            t_result = handle_file_result(chat_id, t_result, self.token)
            self._last_tool_name = t_name
            self._last_tool_result = t_result

            # 3. OBSERVE: Feed result back
            if len(t_result) > 2000:
                t_result = t_result[:2000] + "... (truncated)"

            print("[react] Observe: " + str(len(t_result)) + " bytes from " + t_name)

            # Optional: force single-tool responses for speed
            if str(self.config.get("one_tool_only", "false")).lower() == "true":
                direct = self._direct_tool_reply(t_name, t_result, force=True)
                self.add_to_history(chat_id, "assistant", direct)
                return direct

            direct = self._direct_tool_reply(t_name, t_result)
            if direct is not None:
                self.add_to_history(chat_id, "assistant", direct)
                return direct

            # Add tool result as user message (the "observation")
            self.add_to_history(
                chat_id, "user", "[Tool Result: " + t_name + "]\n" + t_result
            )

            # Refresh messages for next iteration
            messages = self.get_history(chat_id)

        if not final_text and self._last_tool_result:
            direct = self._direct_tool_reply(self._last_tool_name, self._last_tool_result)
            final_text = direct if direct else self._last_tool_result
        if not final_text:
            final_text = "I ran into a problem processing your request."

        return final_text


def send_telegram_msg(chat_id, text, token):
    """Refactored helper to send Telegram messages via curl (no temp files)"""
    if not text or not token:
        return

    # Strip markdown and send as plain text
    clean_text = strip_markdown(text)

    start_ts = time.time()
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    except:
        ts = str(time.time())
    try:
        text_len = len(clean_text)
    except:
        text_len = 0
    print("[tele] " + ts + " send start chat=" + str(chat_id) + " len=" + str(text_len))

    # Build JSON inline for curl -d (no temp file)
    # Escape quotes and backslashes for JSON
    json_text = (
        clean_text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )
    json_body = '{"chat_id":' + str(chat_id) + ',"text":"' + json_text + '"}'

    send_url = "https://api.telegram.org/bot" + token + "/sendMessage"
    cmd = (
        "curl -k -s --connect-timeout 5 -m 10 -H 'Content-Type: application/json' -d '"
        + json_body.replace("'", "'\\''")
        + "' '"
        + send_url
        + "'"
    )

    s_res = run_command(cmd)

    if not s_res or '"ok":true' not in s_res:
        # Fallback: URL-encoded form post (most compatible)
        # Simple manual encoding for minimal environments
        encoded = (
            clean_text.replace(" ", "%20").replace("\n", "%0A").replace("&", "%26")
        )
        cmd2 = (
            "curl -k -s --connect-timeout 5 -m 10 '"
            + send_url
            + "?chat_id="
            + str(chat_id)
            + "&text="
            + encoded
            + "'"
        )
        run_command(cmd2)

    end_ts = time.time()
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    except:
        ts = str(time.time())
    print("[tele] " + ts + " send done chat=" + str(chat_id) + " elapsed=" + str(end_ts - start_ts))


def send_channel_message(channel, target, text, config, response_url=""):
    if not text:
        return
    clean = strip_markdown(text)

    if channel == "slack":
        token = config.get("slack_bot_token", "")
        if not token or not target:
            return
        body = '{"channel":"' + str(target) + '","text":"' + clean.replace('"', '\\"') + '"}'
        cmd = (
            "curl -k -s -m 10 -H 'Content-Type: application/json' "
            + "-H 'Authorization: Bearer "
            + token
            + "' -d '"
            + body.replace("'", "'\\''")
            + "' https://slack.com/api/chat.postMessage"
        )
        run_command(cmd)
        return

    if channel == "webhook":
        if not response_url:
            return
        body = '{"text":"' + clean.replace('"', '\\"') + '"}'
        cmd = "curl -k -s -m 10 -H 'Content-Type: application/json' -d '" + body.replace("'", "'\\''") + "' '" + response_url + "'"
        run_command(cmd)
        return


def main():
    print("=" * 40)
    print("   MicroBot-Claw - MicroPython Version")
    print("=" * 40)

    # Check curl (required now)
    curl_ver = run_command("curl --version 2>&1 | head -1")
    if not curl_ver:
        # Check if we can run curl anyway (fallback)
        test_curl = run_command("curl --version")
        if not test_curl:
            print("ERROR: curl is required. Please install with 'opkg install curl'")
            sys.exit(1)

    # Use the config_data merged at the top level
    if not config_data:
        print("ERROR: No configuration found!")
        sys.exit(1)

    # Ensure memory/personality files and upload dirs exist in DATA_DIR
    try:
        mkdir_recursive(Path.join(DATA_DIR, "memory"))
        mkdir_recursive(Path.join(DATA_DIR, "config"))
        mkdir_recursive(Path.join(DATA_DIR, "uploads"))
        mkdir_recursive(Path.join(DATA_DIR, "users"))
        skills_dir = Path.join(DATA_DIR, "skills")
        mkdir_recursive(skills_dir)
        mem_file = Path.join(DATA_DIR, "memory", "MEMORY.md")
        soul_file = Path.join(DATA_DIR, "config", "SOUL.md")
        user_file = Path.join(DATA_DIR, "config", "USER.md")
        if not Path.exists(mem_file):
            with open(mem_file, "w") as f:
                f.write("# Long-term Memory\n(empty)\n")
        if not Path.exists(soul_file):
            with open(soul_file, "w") as f:
                f.write("I am MicroBot AI, a personal AI assistant running on OpenWrt.\n")
        if not Path.exists(user_file):
            with open(user_file, "w") as f:
                f.write("# User Profile\n- Name: (not set)\n")
        # Create example skill if none exist
        try:
            files = os.listdir(skills_dir)
        except:
            files = []
        if not files:
            ex = Path.join(skills_dir, "example_skill.md")
            with open(ex, "w") as f:
                f.write("# Skill: Daily Router Check\n")
                f.write("Goal: Review system health each morning.\n")
                f.write("Steps:\n")
                f.write("- Get system_info\n")
                f.write("- Check network_status\n")
                f.write("- Report anomalies\n")
    except:
        pass

    # Load timezone from config
    global TIMEZONE
    TIMEZONE = config_data.get("timezone", "")
    if TIMEZONE:
        print("Timezone: " + TIMEZONE)

    agent = Agent(config_data)

    # Try dynamic skill loading (safe - if it fails, hardcoded tools still work)
    Agent.load_skills()
    # Pre-generate wait phrases once (LLM), falls back silently if unavailable
    allow_wait_llm = str(config_data.get("send_wait_messages", "false")).lower() == "true"
    agent._init_wait_phrases(allow_llm=allow_wait_llm)

    token = config_data.get("tg_token")

    if not token:
        print("tg_token not set. Set it in the UI (http://<this-ip>:8080) to enable Telegram.")

    print("Bot Token: " + (token[:10] if token else "None") + "...")
    print("Starting polling loop...")

    offset = 0
    next_sched_check = 0
    next_inbox_check = 0
    try:
        sched_interval = int(config_data.get("schedule_check_interval", 10))
        if sched_interval < 2:
            sched_interval = 2
    except:
        sched_interval = 10

    try:
        inbox_interval = int(config_data.get("inbox_check_interval", 2))
        if inbox_interval < 1:
            inbox_interval = 1
    except:
        inbox_interval = 2

    INBOX_DIR = Path.join(DATA_DIR, "inbox", "queue")
    INBOX_DONE = Path.join(DATA_DIR, "inbox", "done")
    mkdir_recursive(INBOX_DIR)
    mkdir_recursive(INBOX_DONE)

    def _maybe_check_schedules():
        nonlocal next_sched_check
        try:
            now_ts = time.time()
        except:
            now_ts = 0
        if now_ts >= next_sched_check:
            check_schedules(token, agent)
            next_sched_check = now_ts + sched_interval

    def _maybe_check_inbox():
        nonlocal next_inbox_check
        try:
            now_ts = time.time()
        except:
            now_ts = 0
        if now_ts < next_inbox_check:
            return
        next_inbox_check = now_ts + inbox_interval

        try:
            files = os.listdir(INBOX_DIR)
        except:
            files = []
        job_file = ""
        for f in files:
            if f.endswith(".json"):
                job_file = f
                break
        if not job_file:
            return

        path = Path.join(INBOX_DIR, job_file)
        try:
            with open(path, "r") as f:
                job = json.load(f)
        except:
            job = {}
        try:
            os.remove(path)
        except:
            pass

        channel = job.get("channel", "webhook")
        target = job.get("target", "")
        user_name = job.get("user_name", "")
        text = job.get("text", "")
        response_url = job.get("response_url", "")
        if not text:
            return
        reply = agent.process_message(target or "0", text, user_name)
        if channel == "telegram":
            send_telegram_msg(target, reply, token)
        else:
            send_channel_message(channel, target, reply, config_data, response_url)

        try:
            with open(Path.join(INBOX_DONE, job_file), "w") as f:
                f.write(json.dumps(job))
        except:
            pass

    no_token_warn_ts = 0
    while True:
        try:
            # When no token, reload config periodically so user can set it in the UI
            if not token:
                try:
                    if Path.exists(CONFIG_FILE):
                        with open(CONFIG_FILE, "r") as f:
                            loaded = json.load(f)
                        config_data.update(loaded)
                        token = config_data.get("tg_token")
                except:
                    pass
                if not token:
                    now_ts = time.time() if hasattr(time, "time") else 0
                    if now_ts - no_token_warn_ts >= 60:
                        print("Set tg_token in the UI (http://<this-ip>:8080) to enable Telegram.")
                        no_token_warn_ts = now_ts
                    time.sleep(15)
                    continue

            _maybe_check_schedules()
            _maybe_check_inbox()

            # Polling URL
            url = (
                "https://api.telegram.org/bot"
                + token
                + "/getUpdates?timeout=5&allowed_updates=%5B%22message%22%5D"
            )
            if offset > 0:
                url += "&offset=" + str(offset)

            # Poll with curl (Reduced timeout for faster loop reset)
            cmd = 'curl -k -s -m 8 "' + url + '"'
            resp_str = run_command(cmd)

            if not resp_str or not resp_str.startswith("{"):
                gc.collect()
                time.sleep(0.1) # Fast retry
                continue

            data = json.loads(resp_str)

            if not data.get("ok"):
                # Conflict error check
                if data.get("error_code") == 409:
                    print("Conflict error: Sleeping...")
                    time.sleep(5)
                continue

            updates = data.get("result", [])

            # Batch messages per chat when multiple arrive in a single poll
            # This avoids replying one-by-one after reconnect/backlog.
            batched = {}
            order = []
            for update in updates:
                _maybe_check_schedules()
                _maybe_check_inbox()

                update_id = update.get("update_id")
                offset = update_id + 1

                if "message" not in update:
                    continue

                msg = update["message"]
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                caption = msg.get("caption", "")

                # Save incoming photos, documents, voice, video, audio to user folder: data/uploads/<chat_id>/
                saved_msgs = []
                ts = str(int(time.time()))

                photos = msg.get("photo", [])
                if photos:
                    try:
                        photo_obj = photos[-1]
                        file_id = photo_obj.get("file_id")
                        ext = ""
                        fpath = tg_get_file_path(file_id, token)
                        if fpath and "." in fpath:
                            ext = "." + fpath.rsplit(".", 1)[-1]
                        fname = "photo_" + ts + (ext or ".jpg")
                        saved = save_telegram_attachment(file_id, fname, "photo", token, chat_id)
                        if saved:
                            saved_msgs.append("Foto guardada: " + saved)
                    except:
                        pass

                doc = msg.get("document")
                if doc:
                    try:
                        file_id = doc.get("file_id")
                        fname = doc.get("file_name", "")
                        saved = save_telegram_attachment(file_id, fname, "documents", token, chat_id)
                        if saved:
                            saved_msgs.append("Documento guardado: " + saved)
                    except:
                        pass

                voice = msg.get("voice")
                if voice:
                    try:
                        file_id = voice.get("file_id")
                        fpath = tg_get_file_path(file_id, token)
                        ext = ".ogg" if fpath and "oga" in str(fpath) else ".ogg"
                        fname = "voice_" + ts + ext
                        saved = save_telegram_attachment(file_id, fname, "voice", token, chat_id)
                        if saved:
                            saved_msgs.append("Audio guardado: " + saved)
                    except:
                        pass

                video = msg.get("video")
                if video:
                    try:
                        file_id = video.get("file_id")
                        fpath = tg_get_file_path(file_id, token)
                        ext = ""
                        if fpath and "." in fpath:
                            ext = "." + fpath.rsplit(".", 1)[-1]
                        fname = "video_" + ts + (ext or ".mp4")
                        saved = save_telegram_attachment(file_id, fname, "video", token, chat_id)
                        if saved:
                            saved_msgs.append("Video guardado: " + saved)
                    except:
                        pass

                video_note = msg.get("video_note")
                if video_note:
                    try:
                        file_id = video_note.get("file_id")
                        fname = "video_note_" + ts + ".mp4"
                        saved = save_telegram_attachment(file_id, fname, "video_note", token, chat_id)
                        if saved:
                            saved_msgs.append("Video nota guardado: " + saved)
                    except:
                        pass

                audio = msg.get("audio")
                if audio:
                    try:
                        file_id = audio.get("file_id")
                        fname = audio.get("file_name", "") or ("audio_" + ts + ".mp3")
                        saved = save_telegram_attachment(file_id, fname, "audio", token, chat_id)
                        if saved:
                            saved_msgs.append("Audio guardado: " + saved)
                    except:
                        pass

                if saved_msgs:
                    send_telegram_msg(chat_id, "\n".join(saved_msgs), token)
                elif photos or doc or voice or video or audio:
                    send_telegram_msg(
                        chat_id,
                        "I received your photo/file but couldn't save it. Check your connection or try again.",
                        token,
                    )

                if not text and caption:
                    text = caption

                if not text:
                    continue

                # DEBUG: Print raw message structure to debug username issue
                # print("DEBUG: MSG: " + json.dumps(msg))

                user = msg.get("from", {})
                username = user.get("username", "")
                first_name = user.get("first_name", "")

                display_name = username or first_name or "unknown"

                if chat_id not in batched:
                    batched[chat_id] = {
                        "texts": [],
                        "display_name": display_name,
                    }
                    order.append(chat_id)
                batched[chat_id]["texts"].append(text)

            # Process per chat (batched)
            for chat_id in order:
                entry = batched.get(chat_id)
                if not entry:
                    continue

                texts = entry["texts"]
                display_name = entry["display_name"]

                # If there are commands, handle them one-by-one in order.
                has_command = False
                for t in texts:
                    if t.strip().startswith("/"):
                        has_command = True
                        break

                if has_command:
                    for t in texts:
                        if not t:
                            continue
                        print("\n[telegram] @" + display_name + ": " + t)
                        gc.collect()

                        # Send typing
                        run_command(
                            'curl -k -s --connect-timeout 5 -m 10 "https://api.telegram.org/bot'
                            + token
                            + "/sendChatAction?chat_id="
                            + str(chat_id)
                            + '&action=typing"'
                        )

                        response = ""
                        if t == "/start":
                            response = "Hello! I'm MicroBot-Claw (Python). How can I help?"
                            agent.clear_history(chat_id)
                        elif t == "/clear":
                            agent.clear_history(chat_id)
                            response = "Memory cleared."
                        else:
                            onboarding_msg, continue_to_agent = agent.handle_onboarding(chat_id, t, display_name)
                            if not continue_to_agent:
                                response = onboarding_msg or ""
                            else:
                                t0 = time.time()
                                try:
                                    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                                except:
                                    ts = str(time.time())
                                print("[tele] " + ts + " process start chat=" + str(chat_id))
                                response = agent.process_message(chat_id, t, display_name)
                                t1 = time.time()
                                try:
                                    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                                except:
                                    ts = str(time.time())
                                print("[tele] " + ts + " process done chat=" + str(chat_id) + " elapsed=" + str(t1 - t0))

                    send_telegram_msg(chat_id, response, token)
                    gc.collect()
                else:
                    # Combine all messages in the same poll into one request
                    combined = "\n".join(texts)
                    print("\n[telegram] @" + display_name + ": " + combined)
                    gc.collect()

                    # Send typing
                    run_command(
                        'curl -k -s --connect-timeout 5 -m 10 "https://api.telegram.org/bot'
                        + token
                        + "/sendChatAction?chat_id="
                        + str(chat_id)
                        + '&action=typing"'
                    )

                    onboarding_msg, continue_to_agent = agent.handle_onboarding(chat_id, combined, display_name)
                    if not continue_to_agent:
                        send_telegram_msg(chat_id, onboarding_msg or "", token)
                    else:
                        t0 = time.time()
                        try:
                            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        except:
                            ts = str(time.time())
                        print("[tele] " + ts + " process start chat=" + str(chat_id))
                        response = agent.process_message(chat_id, combined, display_name)
                        t1 = time.time()
                        try:
                            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        except:
                            ts = str(time.time())
                        print("[tele] " + ts + " process done chat=" + str(chat_id) + " elapsed=" + str(t1 - t0))
                        send_telegram_msg(chat_id, response, token)
                    gc.collect()

            _maybe_check_schedules()
            _maybe_check_inbox()

        except KeyboardInterrupt:
            print("\nStopping...")
            break
        except Exception as e:
            print("Loop Error: " + str(e))
            # sys.print_exception(e)
            time.sleep(1)


if __name__ == "__main__":
    main()
