# AgentWRT core utilities (MicroPython-friendly)
try:
    import ure as re
except ImportError:
    import re

LOG_LEVEL = "info"
DEBUG_LOG = False
VERBOSE_LOG = False


def configure_logging(config):
    global LOG_LEVEL, DEBUG_LOG, VERBOSE_LOG
    try:
        LOG_LEVEL = str(config.get("log_level", "info") or "info").lower()
        DEBUG_LOG = str(config.get("debug_log", "false")).lower() == "true"
        VERBOSE_LOG = str(config.get("verbose_log", "false")).lower() == "true"
    except:
        LOG_LEVEL = "info"
        DEBUG_LOG = False
        VERBOSE_LOG = False


def log_error(msg):
    try:
        print(str(msg))
    except:
        pass


def log_info(msg):
    try:
        if LOG_LEVEL != "quiet":
            print(str(msg))
    except:
        pass


def log_debug(msg):
    try:
        if DEBUG_LOG:
            print(str(msg))
    except:
        pass


def normalize_timezone(raw_tz):
    tz = (raw_tz or "").strip()
    low = tz.lower().replace(" ", "_")
    aliases = {
        "madrid": "Europe/Madrid",
        "spain": "Europe/Madrid",
        "espana": "Europe/Madrid",
        "españa": "Europe/Madrid",
        "argentina": "America/Argentina/Buenos_Aires",
        "buenos_aires": "America/Argentina/Buenos_Aires",
        "mexico": "America/Mexico_City",
        "méxico": "America/Mexico_City",
        "mexico_city": "America/Mexico_City",
        "new_york": "America/New_York",
        "usa_east": "America/New_York",
        "los_angeles": "America/Los_Angeles",
        "usa_west": "America/Los_Angeles",
        "uk": "Europe/London",
        "london": "Europe/London",
        "france": "Europe/Paris",
        "paris": "Europe/Paris",
        "germany": "Europe/Berlin",
        "berlin": "Europe/Berlin",
        "italy": "Europe/Rome",
        "rome": "Europe/Rome",
        "japan": "Asia/Tokyo",
        "tokyo": "Asia/Tokyo",
        "china": "Asia/Shanghai",
        "india": "Asia/Kolkata",
        "australia": "Australia/Sydney",
        "sydney": "Australia/Sydney",
        "colombia": "America/Bogota",
        "bogota": "America/Bogota",
        "bogotá": "America/Bogota",
        "chile": "America/Santiago",
        "peru": "America/Lima",
        "perú": "America/Lima",
        "uruguay": "America/Montevideo",
        "utc": "UTC",
    }
    return aliases.get(low, tz)


def is_valid_timezone(tz, exists_func=None):
    if not tz or len(tz) > 64 or ".." in tz or tz.startswith("/"):
        return False
    ok_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-/"
    for ch in tz:
        if ch not in ok_chars:
            return False
    if tz == "UTC":
        return True
    if exists_func:
        try:
            if exists_func("/usr/share/zoneinfo/" + tz) or exists_func("/rom/usr/share/zoneinfo/" + tz):
                return True
        except:
            pass
    return "/" in tz


def strip_html_entities(s):
    try:
        out = []
        in_tag = False
        for ch in str(s):
            if ch == "<":
                in_tag = True
                continue
            if ch == ">" and in_tag:
                in_tag = False
                continue
            if not in_tag:
                out.append(ch)
        s = "".join(out)
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&#x27;", "'"), ("&nbsp;", " ")):
            s = s.replace(a, b)
    except:
        pass
    return s


def sanitize_outbound_text(text, config_file="", data_dir=""):
    s = str(text or "")
    try:
        lines = []
        for line in s.split("\n"):
            low = line.strip().lower()
            if low.startswith("tool:") or low.startswith("debug: tool cmd"):
                continue
            if low.startswith("authorization:") or low.startswith("x-subscription-token:"):
                lines.append("[redacted]")
                continue
            if "## available tools" in low or "## security" in low or "react loop" in low:
                lines.append("[internal instructions redacted]")
                continue
            lines.append(line)
        s = "\n".join(lines)
        s = strip_html_entities(s)

        redacted = []
        for word in s.split(" "):
            lw = word.lower()
            clean = word.strip("'\";,()[]{}<>")
            if "sk-" in lw and len(clean) > 18:
                redacted.append("[api-key-redacted]")
            elif ":" in clean:
                left, right = clean.split(":", 1)
                if len(left) >= 8 and len(left) <= 12 and left.isdigit() and len(right) >= 25:
                    redacted.append("[telegram-token-redacted]")
                else:
                    redacted.append(word)
            elif clean.startswith("AKIA") and len(clean) >= 20:
                redacted.append("[aws-key-redacted]")
            else:
                redacted.append(word)
        s = " ".join(redacted)

        for key in ("openrouter_key", "api_key", "tg_token", "slack_bot_token", "webhook_token", "ui_pass", "password", "secret"):
            lower = s.lower()
            k = key.lower()
            pos = lower.find(k)
            while pos != -1:
                sep = -1
                eq = lower.find("=", pos + len(k))
                co = lower.find(":", pos + len(k))
                if eq != -1 and (co == -1 or eq < co):
                    sep = eq
                elif co != -1:
                    sep = co
                if sep == -1 or sep - pos > 24:
                    pos = lower.find(k, pos + len(k))
                    continue
                end = sep + 1
                while end < len(s) and s[end] in " \t'\"":
                    end += 1
                val_end = end
                while val_end < len(s) and s[val_end] not in " \t\n,}":
                    val_end += 1
                s = s[:pos] + key + "=[redacted]" + s[val_end:]
                lower = s.lower()
                pos = lower.find(k, pos + len(key) + 10)
        if config_file:
            s = s.replace(config_file, "[config-path-redacted]")
        if data_dir:
            s = s.replace(data_dir + "/config.json", "[config-path-redacted]")
    except:
        pass
    return s
