#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Favicon Grabber
# @raycast.mode silent
# @raycast.argument1 { "type": "text", "placeholder": "Brand name or website URL" }

# Optional parameters:
# @raycast.icon 🎴

# Documentation:
# @raycast.author bztravis88
# @raycast.authorURL https://raycast.com/bztravis88

set -euo pipefail

fail() { echo "$*" >&2; exit 1; }
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PYTHON=""
for candidate in "$(command -v python3 || true)" /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" -c 'import html.parser, urllib.parse' >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
[[ -n "$PYTHON" ]] || fail "Python 3 is required. Install it and try again."
WEBSITES="$("$PYTHON" "$SCRIPT_DIR/find_favicons.py" resolve-all "${1:-}")" || exit 1
URL="${WEBSITES%%$'\n'*}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fetch() {
    /usr/bin/curl --location --max-redirs 5 --fail --silent --show-error \
        --connect-timeout 5 --max-time 15 --max-filesize 10485760 \
        --proto '=http,https' --proto-redir '=http,https' \
        --user-agent 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' "$@"
}

PAGE_FAILED=0
if ! FINAL_URL="$(fetch --output "$TEMP_DIR/page.html" --write-out '%{url_effective}' "$URL" 2>"$TEMP_DIR/curl-error")"; then
    PAGE_FAILED=1
    FINAL_URL="$URL"
    : > "$TEMP_DIR/page.html"
fi
"$PYTHON" "$SCRIPT_DIR/find_favicons.py" discover "$FINAL_URL" "$TEMP_DIR/page.html" > "$TEMP_DIR/candidates"

while IFS= read -r ICON_URL; do
    if ! fetch --output "$TEMP_DIR/download" "$ICON_URL" 2>"$TEMP_DIR/curl-error"; then
        continue
    fi
    rm -f -- "$TEMP_DIR/favicon.png"
    if ! /usr/bin/sips -s format png "$TEMP_DIR/download" --out "$TEMP_DIR/favicon.png" > /dev/null 2>&1; then
        continue
    fi
    [[ -s "$TEMP_DIR/favicon.png" ]] || continue
    if ! /usr/bin/sips -g pixelWidth -g pixelHeight "$TEMP_DIR/favicon.png" 2>/dev/null | \
        /usr/bin/awk '/pixelWidth:|pixelHeight:/ { if ($2 + 0 > 0) n++ } END { exit(n != 2) }'; then
        continue
    fi
    if ! /usr/bin/osascript - "$TEMP_DIR/favicon.png" > /dev/null <<'APPLESCRIPT'
on run argv
    set imageFile to POSIX file (item 1 of argv)
    set imageData to read imageFile as «class PNGf»
    set the clipboard to imageData
end run
APPLESCRIPT
    then
        fail "Found a favicon, but could not copy it to the clipboard."
    fi
    "$PYTHON" - "$WEBSITES" <<'PYTHON'
import sys
from urllib.parse import urlsplit
websites = sys.argv[1].splitlines()
print(", ".join(urlsplit(url).hostname for url in websites))
PYTHON
    exit 0
done < "$TEMP_DIR/candidates"

if [[ "$PAGE_FAILED" == 1 ]]; then
    fail "Could not fetch the website or a usable fallback favicon. Check the URL and connection."
fi
fail "No usable favicon found. PNG, JPEG, and ICO images are supported; SVG icons are skipped."
