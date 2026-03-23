#!/bin/bash

# Linuxserver-style PUID/PGID handling
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "
─────────────────────────────────────────
     ___ ___  _  ___   _____ ___ ___
    / __/ _ \| \| \ \ / / __| _ \_  )
   | (_| (_) | .  |\ V /| _||   // /
    \___\___/|_|\_| \_/ |___|_|_/___|

  File Format Converter
─────────────────────────────────────────
  PUID:     ${PUID}
  PGID:     ${PGID}
  TZ:       ${TZ}
  Max size: ${MAX_FILE_SIZE}MB
  Base URL: ${BASE_URL:-http://localhost:7391}
─────────────────────────────────────────
"

# Create group and user if they don't exist
if ! getent group converter > /dev/null 2>&1; then
    groupadd -g "$PGID" converter
fi
if ! getent passwd converter > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -d /app -s /bin/bash converter
fi

# Set timezone
if [ -f /usr/share/zoneinfo/"$TZ" ]; then
    ln -snf /usr/share/zoneinfo/"$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
fi

# Fix permissions
chown -R converter:converter /app /config

# Run Flask as the converter user
exec gosu converter python -m app.app
