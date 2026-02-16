#!/bin/sh

# Plugin: Gmail Sender
# Tool: send_email
# Args: JSON string {"to": "...", "subject": "...", "body": "..."}

tool_send_email() {
    local json_args="$1"
    
    # Load config if not loaded
    [ -z "$CONFIG_LOADED" ] && . "${SCRIPT_DIR:-.}/config.sh"
    
    # Extract args
    local to="" subject="" body=""
    if command -v jsonfilter >/dev/null 2>&1; then
        to=$(echo "$json_args" | jsonfilter -e '@.to')
        subject=$(echo "$json_args" | jsonfilter -e '@.subject')
        body=$(echo "$json_args" | jsonfilter -e '@.body')
    else
        # Fallback parsing
        to=$(echo "$json_args" | grep -o '"to": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
        subject=$(echo "$json_args" | grep -o '"subject": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
        body=$(echo "$json_args" | grep -o '"body": *"[^"]*"' | sed 's/.*: *"//;s/"$//')
    fi
    
    # Check config
    local user="" pass=""
    user=$(jsonfilter -i "$CONFIG_FILE" -e '@.gmail_user' 2>/dev/null)
    pass=$(jsonfilter -i "$CONFIG_FILE" -e '@.gmail_app_password' 2>/dev/null)
    
    if [ -z "$user" ] || [ -z "$pass" ]; then
        echo "Error: Gmail not configured. Add 'gmail_user' and 'gmail_app_password' to config.json"
        return
    fi
    
    if [ -z "$to" ] || [ -z "$body" ]; then
        echo "Error: Recipient (to) and body required."
        return
    fi
    
    # Construct email temp file
    local mail_file="/tmp/mail_$$.txt"
    echo "From: \"MicroBot\" <$user>" > "$mail_file"
    echo "To: <$to>" >> "$mail_file"
    echo "Subject: $subject" >> "$mail_file"
    echo "" >> "$mail_file" # Header separator
    echo "$body" >> "$mail_file"
    
    # Send via curl SMTP
    # Using smtps://smtp.gmail.com:465
    echo "Sending email to $to..."
    local result
    result=$(curl --ssl-reqd \
         --url 'smtps://smtp.gmail.com:465' \
         --user "$user:$pass" \
         --mail-from "$user" \
         --mail-to "$to" \
         --upload-file "$mail_file" \
         -k -s 2>&1)
         
    if [ $? -eq 0 ]; then
        echo "Email sent successfully!"
    else
        echo "Error sending email: $result"
    fi
    
    rm -f "$mail_file"
}
