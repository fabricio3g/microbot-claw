#!/bin/sh
# Scaffold a new plugin tool

echo "=== MicroBot-Claw Tool Scaffolder ==="
printf "Tool name (no spaces, lowercase): "
read name

if [ -z "$name" ]; then
    echo "Error: name required"
    exit 1
fi

case "$name" in
    *[!a-zA-Z0-9_-]*)
        echo "Error: name should be alnum/underscore/dash only"
        exit 1
        ;;
esac

printf "Description: "
read desc
printf "Args (comma separated, e.g. url,query,limit): "
read args

args_json="[]"
if [ -n "$args" ]; then
    args_json=$(echo "$args" | awk -F',' '{
        printf "[";
        for (i=1; i<=NF; i++) {
            gsub(/^ +| +$/, "", $i);
            if (length($i) > 0) {
                printf "%s\"%s\"", (i>1?",":""), $i;
            }
        }
        printf "]";
    }')
fi

json_path="plugins/${name}.json"
sh_path="plugins/${name}.sh"

cat > "$json_path" <<EOF
{
  "name": "${name}",
  "description": "${desc}",
  "args": ${args_json}
}
EOF

cat > "$sh_path" <<EOF
#!/bin/sh

# Plugin: ${name}
# Tool: ${name}
# Args: JSON string

tool_${name}() {
    local json_args="\$1"
    # TODO: parse args and implement tool
    echo "OK: ${name} not implemented yet"
}
EOF

chmod +x "$sh_path" 2>/dev/null
echo "Created:"
echo "  $json_path"
echo "  $sh_path"
