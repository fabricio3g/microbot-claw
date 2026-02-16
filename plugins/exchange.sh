#!/bin/sh
# MicroBot Plugin: Exchange Rate (Frankfurter API, no key)
# Provides: tool_get_exchange_rate
# LLM decides from_currency, to_currency, amount from user question

tool_get_exchange_rate() {
    local args="$1"
    local from_currency="USD"
    local to_currency=""
    local amount="1"

    if command -v jsonfilter >/dev/null 2>&1 && [ -n "$args" ]; then
        from_currency=$(echo "$args" | jsonfilter -e '@.from_currency' 2>/dev/null)
        to_currency=$(echo "$args" | jsonfilter -e '@.to_currency' 2>/dev/null)
        amount=$(echo "$args" | jsonfilter -e '@.amount' 2>/dev/null)
        [ -z "$from_currency" ] && from_currency=$(echo "$args" | jsonfilter -e '@.base' 2>/dev/null)
        [ -z "$to_currency" ] && to_currency=$(echo "$args" | jsonfilter -e '@.target' 2>/dev/null)
        if [ -z "$to_currency" ]; then
            local q=$(echo "$args" | jsonfilter -e '@.query' 2>/dev/null)
            if [ -n "$q" ]; then
                from_currency=$(echo "$q" | awk '{print $1}')
                to_currency=$(echo "$q" | awk '{print $2}')
            fi
        fi
    else
        [ -n "$args" ] && {
            from_currency=$(echo "$args" | grep -o '"from_currency"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"from_currency"[[:space:]]*:[[:space:]]*"//;s/"$//')
            to_currency=$(echo "$args" | grep -o '"to_currency"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"to_currency"[[:space:]]*:[[:space:]]*"//;s/"$//')
            amount=$(echo "$args" | grep -o '"amount"[[:space:]]*:[[:space:]]*[0-9.]*' | sed 's/.*:[[:space:]]*//')
            [ -z "$from_currency" ] && from_currency=$(echo "$args" | grep -o '"base"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"base"[[:space:]]*:[[:space:]]*"//;s/"$//')
            [ -z "$to_currency" ] && to_currency=$(echo "$args" | grep -o '"target"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"target"[[:space:]]*:[[:space:]]*"//;s/"$//')
        }
    fi

    [ -z "$from_currency" ] && from_currency="USD"
    [ -z "$to_currency" ] && { echo "Error: to_currency required (e.g. EUR, GBP, ARS)."; return; }
    [ -z "$amount" ] && amount="1"

    from_currency=$(echo "$from_currency" | tr 'a-z' 'A-Z' | tr -cd 'A-Z')
    to_currency=$(echo "$to_currency" | tr 'a-z' 'A-Z' | tr -cd 'A-Z')
    [ ${#from_currency} -ne 3 ] && from_currency="USD"
    [ ${#to_currency} -ne 3 ] && { echo "Error: to_currency must be 3-letter code (e.g. EUR, GBP)."; return; }

    local url="https://api.frankfurter.dev/latest?amount=${amount}&from=${from_currency}&to=${to_currency}"
    local result
    if command -v curl >/dev/null 2>&1; then
        result=$(curl -k -s -m 10 "$url")
    else
        result=$(wget -q -O - --no-check-certificate "$url" 2>/dev/null)
    fi

    if [ -z "$result" ]; then
        echo "Error: Could not fetch exchange rate."
        return
    fi

    local rate=""
    if command -v jsonfilter >/dev/null 2>&1; then
        rate=$(echo "$result" | jsonfilter -e "@.rates.${to_currency}" 2>/dev/null)
    fi
    [ -z "$rate" ] && rate=$(echo "$result" | grep -o "\"${to_currency}\"[[:space:]]*:[[:space:]]*[0-9.]*" | sed 's/.*:[[:space:]]*//')

    if [ -n "$rate" ]; then
        echo "${amount} ${from_currency} = ${rate} ${to_currency}"
        echo "Data: Frankfurter (free, no key)"
    else
        echo "Error: Could not get rate for ${from_currency} to ${to_currency}."
    fi
}
