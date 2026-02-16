"""
Scheduler utilities for MicroBot-Claw (MicroPython friendly).
Implements catch-up scheduling without external cron.
"""

try:
    import utime as time
except ImportError:
    import time

try:
    import ujson as json
except ImportError:
    import json

try:
    import uos as os
except ImportError:
    import os


_CACHE_TZ = {"tz": "", "ts": 0, "val": None}


def _is_leap(year):
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _days_in_month(year, month):
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    return 29 if _is_leap(year) else 28


def _dow_monday0(year, month, day):
    # Zeller's congruence adapted to Monday=0
    if month < 3:
        month += 12
        year -= 1
    k = year % 100
    j = year // 100
    h = (day + (13 * (month + 1)) // 5 + k + (k // 4) + (j // 4) + (5 * j)) % 7
    # Zeller: 0=Saturday. Convert to Monday=0
    # Saturday(0)->5, Sunday(1)->6, Monday(2)->0, Tuesday(3)->1, ...
    return (h + 5) % 7


def _tuple_key(t):
    return (
        str(t[0])
        + ("%02d" % t[1])
        + ("%02d" % t[2])
        + ("%02d" % t[3])
        + ("%02d" % t[4])
    )


def _key_to_tuple(key):
    try:
        y = int(key[0:4])
        m = int(key[4:6])
        d = int(key[6:8])
        h = int(key[8:10])
        mi = int(key[10:12])
        dow = _dow_monday0(y, m, d)
        return (y, m, d, h, mi, 0, dow, 0, 0)
    except:
        return None


def _compare_tuple(a, b):
    if a is None or b is None:
        return 0
    for i in range(5):
        if a[i] < b[i]:
            return -1
        if a[i] > b[i]:
            return 1
    return 0


def _add_minutes(t, delta):
    if t is None or delta == 0:
        return t
    y, m, d, h, mi, sec, dow, yday, isdst = t
    step = 1 if delta > 0 else -1
    count = delta if delta > 0 else -delta
    for _ in range(count):
        mi += step
        if mi >= 60:
            mi = 0
            h += 1
        elif mi < 0:
            mi = 59
            h -= 1

        if h >= 24:
            h = 0
            d += 1
            dow = (dow + 1) % 7
        elif h < 0:
            h = 23
            d -= 1
            dow = (dow - 1) % 7

        if d > _days_in_month(y, m):
            d = 1
            m += 1
            if m > 12:
                m = 1
                y += 1
        elif d < 1:
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            d = _days_in_month(y, m)

    return (y, m, d, h, mi, sec, dow, yday, isdst)


def get_local_time(timezone, run_command):
    if not timezone:
        return time.localtime()

    # cache to avoid frequent HTTP
    try:
        now_ts = time.time()
        if (
            _CACHE_TZ["val"] is not None
            and _CACHE_TZ["tz"] == timezone
            and (now_ts - _CACHE_TZ["ts"]) < 30
        ):
            return _CACHE_TZ["val"]
    except:
        pass

    try:
        url = "http://worldtimeapi.org/api/timezone/" + timezone.replace("/", "%2F")
        cmd = "curl -k -s -m 5 '" + url + "'"
        result = run_command(cmd)
        if result and "datetime" in result:
            dt_start = result.find('"datetime":"')
            if dt_start != -1:
                dt_start += 11
                dt_end = result.find('"', dt_start)
                dt_str = result[dt_start:dt_end]

                year = int(dt_str[0:4])
                month = int(dt_str[5:7])
                day = int(dt_str[8:10])
                hour = int(dt_str[11:13])
                minute = int(dt_str[14:16])
                second = int(dt_str[17:19])

                dow = None
                yday = 0
                isdst = 0

                d_start = result.find('"day_of_week":')
                if d_start != -1:
                    d_start += 14
                    d_end = result.find(",", d_start)
                    if d_end != -1:
                        try:
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
                    dow = _dow_monday0(year, month, day)

                _CACHE_TZ["tz"] = timezone
                _CACHE_TZ["ts"] = time.time() if hasattr(time, "time") else 0
                _CACHE_TZ["val"] = (
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    second,
                    dow,
                    yday,
                    isdst,
                )
                return _CACHE_TZ["val"]
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

        if "," in f:
            parts = f.split(",")
            for part in parts:
                if _match_field(part, v, is_dow):
                    return True
            return False

        step = 1
        if "/" in f:
            f, step_str = f.split("/", 1)
            try:
                step = int(step_str)
            except:
                return False
            if step <= 0:
                return False

        if f == "*":
            return v % step == 0

        if "-" in f:
            try:
                start, end = f.split("-", 1)
                a = int(start)
                b = int(end)
            except:
                return False
            if is_dow:
                if a == 7:
                    a = 0
                if b == 7:
                    b = 0
            if a <= b:
                if v < a or v > b:
                    return False
            else:
                if v > b and v < a:
                    return False
            return ((v - a) % step) == 0

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


def _load_state(path):
    try:
        if _path_exists(path):
            with open(path, "r") as f:
                return json.load(f) or {}
    except:
        pass
    return {}


def _save_state(path, state):
    try:
        with open(path, "w") as f:
            json.dump(state, f)
    except:
        pass


def _path_exists(path):
    try:
        os.stat(path)
        return True
    except:
        return False


def _ensure_dir(path):
    try:
        d = path.rsplit("/", 1)[0]
        if d:
            os.mkdir(d)
    except:
        pass


def check_schedules(
    token,
    agent,
    timezone,
    data_dir,
    config,
    run_command,
    send_msg,
    send_file,
):
    schedules_file = data_dir + "/schedules.txt"
    state_file = data_dir + "/schedules_state.json"

    if not _path_exists(schedules_file):
        return

    try:
        with open(schedules_file, "r") as f:
            data = f.read()
    except:
        return

    lines = [line for line in data.split("\n") if line]
    if not lines:
        return

    state = _load_state(state_file)
    last_check_key = state.get("last_check_key")
    last_fire = state.get("last_fire", {}) if isinstance(state.get("last_fire"), dict) else {}

    now = get_local_time(timezone, run_command)
    now_key = _tuple_key(now)

    # Build catch-up tick list
    try:
        catchup = int(config.get("schedule_catchup_minutes", 5))
    except:
        catchup = 5
    if catchup < 1:
        catchup = 1

    if last_check_key:
        start = _key_to_tuple(last_check_key)
        if start is None or _compare_tuple(start, now) > 0:
            start = _add_minutes(now, -1)
        else:
            start = _add_minutes(start, 1)
    else:
        start = _add_minutes(now, -1)

    min_start = _add_minutes(now, -catchup)
    if _compare_tuple(start, min_start) < 0:
        start = min_start

    ticks = []
    t = start
    while _compare_tuple(t, now) <= 0:
        ticks.append(t)
        t = _add_minutes(t, 1)

    new_lines = []
    state_changed = False

    # Optional log
    log_enabled = str(config.get("schedule_log", "false")).lower() == "true"
    log_path = data_dir + "/logs/scheduler.log"
    if log_enabled:
        _ensure_dir(log_path)

    def _log(msg):
        if not log_enabled:
            return
        try:
            with open(log_path, "a") as f:
                f.write(msg + "\n")
        except:
            pass

    _log("[sched] check " + str(len(lines)) + " at " + now_key + " ticks=" + str(len(ticks)))

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

        for tick in ticks:
            if not matches_cron(cron, tick):
                continue

            tick_key = _tuple_key(tick)
            if last_fire.get(sid) == tick_key:
                continue

            fired = False
            try:
                if stype in ("msg", "reminder") or stype.startswith("reminder") or stype.startswith("msg"):
                    send_msg(int(chat), content, token)
                    fired = True
                elif stype == "cmd":
                    result = run_command(content)
                    send_msg(int(chat), result, token)
                    fired = True
                elif stype == "tool":
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
                    if isinstance(result, str) and result.startswith("FILE:"):
                        fpath = result.replace("FILE:", "", 1).strip()
                        send_file(int(chat), fpath, token, "Archivo descargado")
                        send_msg(int(chat), "Archivo enviado: " + fpath, token)
                    else:
                        send_msg(int(chat), result, token)
                    fired = True
                elif stype == "once_tool":
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
                    if isinstance(result, str) and result.startswith("FILE:"):
                        fpath = result.replace("FILE:", "", 1).strip()
                        send_file(int(chat), fpath, token, "Archivo descargado")
                        send_msg(int(chat), "Archivo enviado: " + fpath, token)
                    else:
                        send_msg(int(chat), result, token)
                    fired = True
                    keep = False
                elif stype == "once":
                    send_msg(int(chat), content, token)
                    fired = True
                    keep = False
                elif stype == "once_cmd":
                    result = run_command(content)
                    send_msg(int(chat), result, token)
                    fired = True
                    keep = False
                elif stype == "probe":
                    if content == "net_check":
                        result = agent.execute_tool("net_check", "{}")
                        if result and "NET_DOWN" in result:
                            send_msg(int(chat), result, token)
                            fired = True
                    else:
                        result = agent.execute_tool(content, "{}")
                        if result:
                            send_msg(int(chat), result, token)
                            fired = True
            except Exception as e:
                _log("[sched] error " + sid + ": " + str(e))

            if fired:
                last_fire[sid] = tick_key
                state_changed = True
                _log("[sched] fired " + sid + " " + tick_key)
                if not keep:
                    break

        if keep:
            new_lines.append(line)

    if len(new_lines) != len(lines):
        try:
            with open(schedules_file, "w") as f:
                f.write("\n".join(new_lines))
        except:
            pass

    state["last_check_key"] = now_key
    state["last_fire"] = last_fire
    _save_state(state_file, state)
