#!/usr/bin/env bash
# Run hinge-auto at a random offset within the current hour.
# Intended for an external cron that fires every hour at :00.
#
# Usage: add to system crontab:
#   0 * * * * /home/ada/.openclaw/workspace/hinge-auto/run_random_window.sh
#
# Each hour picks a random delay 0-30min, sleeps, then runs the bot.
# Combined with the 0-2 random like cap, every run looks different.

set -euo pipefail
cd "$(dirname "$0")"

# Random delay 0-30 minutes (in seconds). Cap at 30 to leave a 15min
# buffer + ~10-15min runtime so runs never overlap the next hour.
delay=$((RANDOM % 1800))
start_time=$(date -d "+${delay} seconds" '+%H:%M')
echo "[$(date)] Cron fired. Will run at ~${start_time} (${delay}s delay)"
sleep "$delay"

echo "[$(date)] Starting run..."
source .venv/bin/activate
python -u main.py --mode carlos 2>&1
EXIT_CODE=$?
echo "[$(date)] Done (exit $EXIT_CODE)"
exit $EXIT_CODE
