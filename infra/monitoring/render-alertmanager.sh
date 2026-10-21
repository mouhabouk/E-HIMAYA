#!/bin/sh
# Renders alertmanager.yml with the SMTP settings from the environment, then starts Alertmanager.
set -eu
esc() { printf '%s' "$1" | sed 's/[\\&|]/\\&/g'; }
sed -e "s|\${ALERT_EMAIL_TO}|$(esc "$ALERT_EMAIL_TO")|g" \
    -e "s|\${ALERT_EMAIL_FROM}|$(esc "$ALERT_EMAIL_FROM")|g" \
    -e "s|\${SMTP_HOST}|$(esc "$SMTP_HOST")|g" \
    -e "s|\${SMTP_PORT}|$(esc "$SMTP_PORT")|g" \
    -e "s|\${SMTP_USERNAME}|$(esc "${SMTP_USERNAME:-}")|g" \
    -e "s|\${SMTP_PASSWORD}|$(esc "${SMTP_PASSWORD:-}")|g" \
    /etc/alertmanager/alertmanager.yml > /tmp/alertmanager.yml
exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager "$@"
