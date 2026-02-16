#!/bin/sh
# MicroBot Plugin: News Summary
# Provides: tool_get_news

tool_get_news() {
    local args="$1"
    local source="lanacion"
    local topic=""

    # Parse arguments
    if [ -n "$args" ]; then
        if command -v jsonfilter >/dev/null 2>&1; then
            local s=$(echo "$args" | jsonfilter -e '@.source' 2>/dev/null)
            [ -n "$s" ] && source="$s"
            local t=$(echo "$args" | jsonfilter -e '@.topic' 2>/dev/null)
            [ -n "$t" ] && topic="$t"
            local q=$(echo "$args" | jsonfilter -e '@.query' 2>/dev/null)
            [ -n "$q" ] && topic="$q"
        else
            # Fallback: extract from query format
            local q=$(echo "$args" | grep -o '"query"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"query"[[:space:]]*:[[:space:]]*"//;s/"//')
            [ -n "$q" ] && topic="$q"
        fi
    fi

    echo "=== News of the day ==="
    echo ""

    case "$source" in
        lanacion|lanación|ln)
            echo "📰 La Nación (Argentina)"
            echo ""
            # Scrape La Nación homepage
            local url="https://www.lanacion.com.ar"
            local result
            if command -v curl >/dev/null 2>&1; then
                result=$(curl -k -s -L -A "Mozilla/5.0" -m 15 "$url" 2>/dev/null)
            else
                result=$(wget -q -O - --no-check-certificate -U "Mozilla/5.0" "$url" 2>/dev/null)
            fi

            if [ -n "$result" ]; then
                # Extract headlines using awk
                echo "$result" | awk '
                BEGIN { count=0 }
                /<h[1-3][^>]*>/ {
                    line = $0
                    while (match(line, /<h[1-3][^>]*>[^<]*/)) {
                        h = substr(line, RSTART, RLENGTH)
                        gsub(/<h[1-3][^>]*>/, "", h)
                        gsub(/<\/h[1-3]>/, "", h)
                        gsub(/&nbsp;/, " ", h)
                        gsub(/&amp;/, "\\&", h)
                        gsub(/&#039;/, "\047", h)
                        gsub(/"/, "", h)
                        gsub(/^[ \t]+|[ \t]+$/, "", h)
                        if (length(h) > 20 && count < 10) {
                            print "- " h
                            count++
                        }
                        line = substr(line, RSTART + RLENGTH)
                    }
                }'
            else
                echo "Error: No se pudo obtener noticias de La Nación"
            fi
            ;;

        clarin|clarín)
            echo "📰 Clarín (Argentina)"
            echo ""
            local url="https://www.clarin.com"
            local result
            if command -v curl >/dev/null 2>&1; then
                result=$(curl -k -s -L -A "Mozilla/5.0" -m 15 "$url" 2>/dev/null)
            else
                result=$(wget -q -O - --no-check-certificate -U "Mozilla/5.0" "$url" 2>/dev/null)
            fi

            if [ -n "$result" ]; then
                echo "$result" | awk '
                BEGIN { count=0 }
                /<h[1-3][^>]*>/ {
                    line = $0
                    while (match(line, /<h[1-3][^>]*>[^<]*/)) {
                        h = substr(line, RSTART, RLENGTH)
                        gsub(/<h[1-3][^>]*>/, "", h)
                        gsub(/<\/h[1-3]>/, "", h)
                        gsub(/&nbsp;/, " ", h)
                        gsub(/&amp;/, "\\&", h)
                        gsub(/&#039;/, "\047", h)
                        gsub(/"/, "", h)
                        gsub(/^[ \t]+|[ \t]+$/, "", h)
                        if (length(h) > 20 && count < 10) {
                            print "- " h
                            count++
                        }
                        line = substr(line, RSTART + RLENGTH)
                    }
                }'
            else
                echo "Error: No se pudo obtener noticias de Clarín"
            fi
            ;;

        infobae)
            echo "📰 Infobae (Argentina)"
            echo ""
            local url="https://www.infobae.com"
            local result
            if command -v curl >/dev/null 2>&1; then
                result=$(curl -k -s -L -A "Mozilla/5.0" -m 15 "$url" 2>/dev/null)
            else
                result=$(wget -q -O - --no-check-certificate -U "Mozilla/5.0" "$url" 2>/dev/null)
            fi

            if [ -n "$result" ]; then
                echo "$result" | awk '
                BEGIN { count=0 }
                /<h[1-3][^>]*>/ {
                    line = $0
                    while (match(line, /<h[1-3][^>]*>[^<]*/)) {
                        h = substr(line, RSTART, RLENGTH)
                        gsub(/<h[1-3][^>]*>/, "", h)
                        gsub(/<\/h[1-3]>/, "", h)
                        gsub(/&nbsp;/, " ", h)
                        gsub(/&amp;/, "\\&", h)
                        gsub(/&#039;/, "\047", h)
                        gsub(/"/, "", h)
                        gsub(/^[ \t]+|[ \t]+$/, "", h)
                        if (length(h) > 20 && count < 10) {
                            print "- " h
                            count++
                        }
                        line = substr(line, RSTART + RLENGTH)
                    }
                }'
            else
                echo "Error: No se pudo obtener noticias de Infobae"
            fi
            ;;

        bbc)
            echo "📰 BBC Mundo"
            echo ""
            local url="https://www.bbc.com/mundo"
            local result
            if command -v curl >/dev/null 2>&1; then
                result=$(curl -k -s -L -A "Mozilla/5.0" -m 15 "$url" 2>/dev/null)
            else
                result=$(wget -q -O - --no-check-certificate -U "Mozilla/5.0" "$url" 2>/dev/null)
            fi

            if [ -n "$result" ]; then
                echo "$result" | awk '
                BEGIN { count=0 }
                /<h[1-3][^>]*>/ {
                    line = $0
                    while (match(line, /<h[1-3][^>]*>[^<]*/)) {
                        h = substr(line, RSTART, RLENGTH)
                        gsub(/<h[1-3][^>]*>/, "", h)
                        gsub(/<\/h[1-3]>/, "", h)
                        gsub(/&nbsp;/, " ", h)
                        gsub(/&amp;/, "\\&", h)
                        gsub(/&#039;/, "\047", h)
                        gsub(/"/, "", h)
                        gsub(/^[ \t]+|[ \t]+$/, "", h)
                        if (length(h) > 20 && count < 10) {
                            print "- " h
                            count++
                        }
                        line = substr(line, RSTART + RLENGTH)
                    }
                }'
            else
                echo "Error: No se pudo obtener noticias de BBC"
            fi
            ;;

        *)
            # Default: web search for news
            echo "🔍 Buscando noticias sobre: ${topic:-actualidad}"
            echo ""

            if [ -n "$topic" ]; then
                # Use web search tool
                local search_query="noticias ${topic} hoy"
                cd "${SCRIPT_DIR:-.}" && . ./config.sh && . ./tools.sh && tool_web_search "$search_query"
            else
                echo "Fuentes disponibles:"
                echo "  - lanacion (La Nación Argentina)"
                echo "  - clarin (Clarín Argentina)"
                echo "  - infobae (Infobae Argentina)"
                echo "  - bbc (BBC Mundo)"
                echo ""
                echo "Ejemplo: get_news lanacion"
                echo "         get_news {\"source\": \"bbc\"}"
                echo "         get_news {\"topic\": \"tecnología\"}"
            fi
            ;;
    esac
}
