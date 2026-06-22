# Telegram helpers (MicroPython-friendly)


def strip_markdown(text, sanitize_func=None):
    s = str(text or "")
    if sanitize_func:
        try:
            s = sanitize_func(s)
        except:
            pass
    for marker in ("**", "__", "```", "`"):
        if marker in s:
            s = s.replace(marker, "")
    lines = s.split("\n")
    for i in range(len(lines)):
        line = lines[i].lstrip()
        if line.startswith("#"):
            line = line.lstrip("#").lstrip()
        elif line.startswith("- "):
            line = "  " + line[2:]
        lines[i] = line
    return "\n".join(lines)


def _json_escape(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _url_encode_minimal(s):
    return str(s).replace("%", "%25").replace(" ", "%20").replace("\n", "%0A").replace("&", "%26").replace("#", "%23").replace("?", "%3F")


def split_text(text, limit=3800, max_total=12000):
    s = str(text or "")
    if len(s) > max_total:
        s = s[: max_total - 20] + "\n\n[truncated]"
    chunks = []
    while s:
        chunks.append(s[:limit])
        s = s[limit:]
    return chunks or [""]


def send_message(chat_id, text, token, run_command, sanitize_func=None, log_debug=None, log_error=None):
    if not text or not token:
        return False
    clean = strip_markdown(text, sanitize_func)
    chunks = split_text(clean)
    if log_debug:
        try:
            total = 0
            for c in chunks:
                total += len(c)
            log_debug("[tele] send parts=" + str(len(chunks)) + " len=" + str(total))
        except:
            pass

    send_url = "https://api.telegram.org/bot" + str(token) + "/sendMessage"
    ok_all = True
    idx = 0
    total_parts = len(chunks)
    for chunk in chunks:
        idx += 1
        out_text = chunk
        if total_parts > 1:
            out_text = "[" + str(idx) + "/" + str(total_parts) + "]\n" + out_text

        json_body = '{"chat_id":' + str(chat_id) + ',"text":"' + _json_escape(out_text) + '"}'
        cmd = (
            "curl -k -s --connect-timeout 5 -m 10 -H 'Content-Type: application/json' -d '"
            + json_body.replace("'", "'\\''")
            + "' '"
            + send_url
            + "'"
        )
        res = run_command(cmd)
        if not res or '"ok":true' not in res:
            encoded = _url_encode_minimal(out_text)
            cmd2 = (
                "curl -k -s --connect-timeout 5 -m 10 '"
                + send_url
                + "?chat_id="
                + str(chat_id)
                + "&text="
                + encoded
                + "'"
            )
            res2 = run_command(cmd2)
            if not res2 or '"ok":true' not in res2:
                ok_all = False
                if log_error:
                    try:
                        log_error("[tele] send failed part=" + str(idx))
                    except:
                        pass
    return ok_all
