# ┏━━ SIMULATION ━━ e-Himaya channels simulator: FCM HTTP v1 (with OAuth) and a Tunisian SMS gateway, dev/test only
# ┃ PRODUCTION: never deploy this package; remove the notify-sim service from infra/compose.yml and set the API's
# ┃   FCM_SERVICE_ACCOUNT, FCM_API_URL, SMS_HTTP_URL, SMS_HTTP_TOKEN to the real values (docs/api/notify-sim.md).
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — e-Himaya notify-sim: stands in for Firebase Cloud Messaging and the SMS gateway in development."""
