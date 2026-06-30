#!/usr/bin/env bash
# Run BumbleAuto on even hours (10am-8pm).
# Sleeps 0-30min so actual run lands between :00-:30.
# Guarantees 30+ min buffer before next hour's job.
#
# Usage: add to system crontab:
#   0 10-20/2 * * * /path/to/bumble-auto/run_random_window.sh >> cron.log 2>&1
#
# Each hour picks a random delay 0-30min, sleeps, then runs the bot.
# Combined with the random like cap (SESSION_LIKE_MIN-MAX_LIKES_PER_SESSION),
# every run looks different to Bumble's detection systems.

set -euo pipefail
cd "$(dirname "$0")"
export PATH="/home/ada/.local/bin:/usr/bin:/bin:$PATH"

# Max 30 min random delay to guarantee 30+ min runtime before next cron
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
