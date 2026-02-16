# Minimal cron runner: calls TRIGGER_URL and exits.
# Set TRIGGER_URL in Railway Variables (e.g. https://your-app.railway.app/trigger-sync)
FROM curlimages/curl:latest
ENV TRIGGER_URL=""
# Use explicit sh -c to ensure proper variable expansion
CMD ["/bin/sh", "-c", "if [ -n \"$TRIGGER_URL\" ]; then curl -sS -X GET \"$TRIGGER_URL\" || exit 1; else echo 'ERROR: TRIGGER_URL not set'; exit 1; fi"]
