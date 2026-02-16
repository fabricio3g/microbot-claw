#!/bin/sh
# MicroBot Plugin: Deep Search
# Chains: web_search -> scrape top results -> combine into summary
# All streaming via curl | awk pipelines. No temp files on disk.

# Tool: Deep web search (search + scrape + combine)
tool_deep_search() {
    local args="$1"
    local query=""
    local max_pages=3
    local save_enabled="${DEEP_SEARCH_SAVE:-true}"
    local save_keep="${DEEP_SEARCH_KEEP:-false}"
    local save_dir="${DEEP_SEARCH_SAVE_DIR:-/tmp/microbot}"
    local out_file=""

    # Parse JSON args
    if [ -n "$args" ]; then
        if command -v jsonfilter >/dev/null 2>&1; then
            query=$(echo "$args" | jsonfilter -e '@.query' 2>/dev/null)
            local mp=$(echo "$args" | jsonfilter -e '@.max_pages' 2>/dev/null)
            [ -n "$mp" ] && max_pages="$mp"
        else
            query=$(echo "$args" | grep -o '"query"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"query"[[:space:]]*:[[:space:]]*"//;s/"$//')
        fi
    fi

    if [ -z "$query" ]; then
        echo "Error: Search query required"
        return
    fi

    local ua="Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
    local encoded_q=$(echo "$query" | sed 's/ /+/g; s/&/%26/g; s/?/%3F/g; s/#/%23/g')

    if [ "$save_enabled" = "true" ]; then
        mkdir -p "$save_dir" 2>/dev/null
        out_file="${save_dir%/}/deep_search_$(date +%s).txt"
        : > "$out_file" 2>/dev/null
    fi

    log_line() {
        echo "$1"
        [ -n "$out_file" ] && echo "$1" >> "$out_file"
    }

    log_block() {
        printf '%s\n' "$1"
        [ -n "$out_file" ] && printf '%s\n' "$1" >> "$out_file"
    }

    log_line "=== Deep Search: $query ==="
    log_line ""

    # Step 1: Get search result URLs from DuckDuckGo
    local ddg_url="https://html.duckduckgo.com/html/?q=${encoded_q}"
    
    # Extract URLs in one pass
    local urls=$(curl -k -s -L -A "$ua" -m 15 "$ddg_url" 2>/dev/null | awk '
    BEGIN { lc=0 }
    {
        line = $0
        while (match(line, /href="[^"]*uddg=[^"]*"/)) {
            href = substr(line, RSTART+6, RLENGTH-7)
            line = substr(line, RSTART+RLENGTH)
            if (match(href, /uddg=[^&]*/)) {
                url = substr(href, RSTART+5, RLENGTH-5)
                gsub(/%3A/, ":", url); gsub(/%2F/, "/", url)
                gsub(/%3F/, "?", url); gsub(/%3D/, "=", url)
                gsub(/%26/, "\\&", url); gsub(/%2C/, ",", url)
                gsub(/%2D/, "-", url); gsub(/%20/, " ", url)
                gsub(/%25/, "%", url)
                # Skip ads/trackers, non-http(s), and duplicates
                if (url ~ /^https?:\/\// &&
                    url !~ /duckduckgo\.com\/y\.js/ &&
                    url !~ /bing\.com\/aclick/ &&
                    url !~ /ad_domain=/ &&
                    url !~ /ad_provider=/ &&
                    url !~ /duckduckgo\.com\/?/) {
                    if (!(url in seen)) {
                        seen[url]=1
                        if (lc < 8) { print url; lc++ }
                    }
                }
            }
        }
    }')

    if [ -z "$urls" ]; then
        echo "No search results found. Try a different query."
        return
    fi

    log_line "--- Sources ---"
    log_block "$(echo "$urls" | head -"$max_pages")"
    log_line ""

    # Step 2: Scrape top N results and combine content
    local combined=""
    local page_num=0

    echo "$urls" | head -"$max_pages" | while IFS= read -r url; do
        [ -z "$url" ] && continue
        page_num=$((page_num + 1))

        log_line "--- Source $page_num ---"

        # Scrape with streaming awk (extract text, skip script/style)
        local content=$(curl -k -s -L -A "$ua" -m 12 "$url" 2>/dev/null | awk '
        BEGIN { skip=0; tc=0 }
        {
            if (match($0, /<script/)) skip=1
            if (match($0, /<\/script>/)) { skip=0; next }
            if (match($0, /<style/)) skip=1
            if (match($0, /<\/style>/)) { skip=0; next }
            if (match($0, /application\/ld\+json/)) skip=1
            if (match($0, /"@context"/) || match($0, /schema\.org/)) next
            if (skip) next

            # Extract title
            if (match($0, /<title[^>]*>[^<]*/)) {
                t = substr($0, RSTART, RLENGTH)
                gsub(/<title[^>]*>/, "", t)
                if (length(t) > 0) print "Title: " t
            }

            # Extract headings
            if (match($0, /<h[1-3][^>]*>[^<]*/)) {
                h = substr($0, RSTART, RLENGTH)
                gsub(/<h[1-3][^>]*>/, "", h)
                if (length(h) > 2) print "# " h
            }

            # Strip tags and collect text
            gsub(/<[^>]*>/, " ")
            gsub(/[ \t]+/, " ")
            gsub(/^ +| +$/, "")
            if (length($0) > 2 && tc < 2000) {
                tc += length($0)
                print $0
            }
        }' | head -c 2000)

        if [ -n "$content" ]; then
            log_block "$content"
        else
            log_line "(Could not extract content from this page)"
        fi
        log_line ""
    done

    log_line "=== End Deep Search ==="

    if [ -n "$out_file" ]; then
        if [ "$save_keep" = "true" ]; then
            log_line "[file] Saved: $out_file"
        else
            rm -f "$out_file" 2>/dev/null
        fi
    fi
}
