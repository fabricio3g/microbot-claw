#!/bin/sh
# Tool template: define tool_{name} and parse JSON args with jsonfilter.

tool_example() {
    local args="$1"
    local input=$(echo "$args" | jsonfilter -e '@.input' 2>/dev/null)
    [ -z "$input" ] && { echo "Error: input required"; return; }
    echo "Example tool received: $input"
}
