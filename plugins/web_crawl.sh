#!/bin/sh

# Plugin: web_crawl
# Tool: web_crawl
# Args: JSON string

tool_web_crawl() {
    local json_args="$1"
    [ -z "$CONFIG_LOADED" ] && . "${SCRIPT_DIR:-.}/config.sh"

    local url="" max_pages="" max_depth="" same_domain="" include_re="" exclude_re=""
    if command -v jsonfilter >/dev/null 2>&1; then
        url=$(echo "$json_args" | jsonfilter -e '@.url')
        max_pages=$(echo "$json_args" | jsonfilter -e '@.max_pages')
        max_depth=$(echo "$json_args" | jsonfilter -e '@.max_depth')
        same_domain=$(echo "$json_args" | jsonfilter -e '@.same_domain')
        include_re=$(echo "$json_args" | jsonfilter -e '@.include_regex')
        exclude_re=$(echo "$json_args" | jsonfilter -e '@.exclude_regex')
    else
        url=$(echo "$json_args" | grep -o '"url": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
    fi

    [ -z "$url" ] && { echo "Error: url required"; return; }
    [ -z "$max_pages" ] && max_pages=5
    [ -z "$max_depth" ] && max_depth=2
    [ -z "$same_domain" ] && same_domain="true"

    local host
    host=$(echo "$url" | sed 's#^[a-zA-Z]*://##; s#/.*##')
    [ -z "$host" ] && { echo "Error: invalid url"; return; }

    is_private_host() {
        local h="$1"
        case "$h" in
            10.*|127.*|192.168.*|localhost) return 0 ;;
        esac
        # 172.16.0.0 - 172.31.255.255
        echo "$h" | awk -F. '{
            if ($1==172 && $2>=16 && $2<=31) exit 0;
            exit 1;
        }'
        return $?
    }

    # Allowlist domains (optional)
    local allow_domains=""
    if [ -n "$CONFIG_FILE" ] && command -v jsonfilter >/dev/null 2>&1; then
        allow_domains=$(jsonfilter -i "$CONFIG_FILE" -e '@.crawl_allow_domains' 2>/dev/null)
    fi
    if [ -n "$allow_domains" ]; then
        local allowed="false"
        for d in $(echo "$allow_domains" | tr ',' ' '); do
            d=$(echo "$d" | tr -d ' ')
            [ -z "$d" ] && continue
            case "$host" in
                "$d"|*."$d") allowed="true" ;;
            esac
        done
        [ "$allowed" = "true" ] || { echo "Error: domain not allowed"; return; }
    fi

    if is_private_host "$host"; then
        echo "Error: private/local hosts blocked"
        return
    fi

    local outdir="${DATA_DIR}/crawl"
    mkdir -p "$outdir" 2>/dev/null
    local outfile="${outdir}/crawl_$(date +%s).txt"

    local qfile="/tmp/crawl_q_$$"
    local vfile="/tmp/crawl_v_$$"
    : > "$qfile"
    : > "$vfile"

    echo "0|$url" >> "$qfile"
    local count=0

    # Normalize &amp; to & for curl (fix "Error when parsing query string" on some servers)
    normalize_url() { echo "$1" | sed 's/&amp;/\&/g'; }

    while [ -s "$qfile" ] && [ "$count" -lt "$max_pages" ]; do
        local line
        line=$(head -n 1 "$qfile")
        sed -i '1d' "$qfile" 2>/dev/null

        local depth="${line%%|*}"
        local curl_url
        curl_url=$(normalize_url "${line#*|}")
        [ -z "$curl_url" ] && continue

        echo "$curl_url" >> "$vfile"
        local tmp="/tmp/crawl_page_$$.txt"
        tool_scrape_web "$curl_url" > "$tmp" 2>/dev/null

        echo "=== URL: $curl_url ===" >> "$outfile"
        cat "$tmp" >> "$outfile"
        echo "" >> "$outfile"

        local links
        links=$(awk '
            BEGIN{f=0}
            /^=== Links ===/ {f=1; next}
            f && /^http/ {print}
        ' "$tmp")

        local next_depth=$((depth + 1))
        if [ "$next_depth" -le "$max_depth" ]; then
            echo "$links" | while read l; do
                [ -z "$l" ] && continue
                l=$(normalize_url "$l")
                [ -z "$l" ] && continue
                # Skip image/asset URLs (resizer, static files) to avoid JSON errors and noise
                case "$l" in
                    *\.jfif*|*\.jpg\?*|*\.jpeg\?*|*\.png\?*|*\.gif\?*|*\.webp\?*|*\.ico\?*|*\.woff2*|*\.woff\?*|*/resizer/*) continue ;;
                esac
                if [ -n "$exclude_re" ]; then
                    echo "$l" | grep -E "$exclude_re" >/dev/null 2>&1 && continue
                fi
                if [ -n "$include_re" ]; then
                    echo "$l" | grep -E "$include_re" >/dev/null 2>&1 || continue
                fi

                local lhost
                lhost=$(echo "$l" | sed 's#^[a-zA-Z]*://##; s#/.*##')
                [ -z "$lhost" ] && continue

                if is_private_host "$lhost"; then
                    continue
                fi

                if [ "$same_domain" != "false" ]; then
                    case "$lhost" in
                        "$host"|*."$host") ;;
                        *) continue ;;
                    esac
                fi

                grep -qxF "$l" "$vfile" 2>/dev/null && continue
                echo "$next_depth|$l" >> "$qfile"
            done
        fi

        rm -f "$tmp"
        count=$((count + 1))
    done

    rm -f "$qfile" "$vfile"
    echo "FILE:$outfile"
}
