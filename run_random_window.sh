#!/usr/bin/env bash
# Run BumbleAuto at :20 past each hour (9am-9pm).
# Sleeps 0-40min so actual run lands anywhere between :20-:60.
#
# Usage: add to system crontab:
#   20 9-21 * * * /path/to/bumble-auto/run_random_window.sh >> cron.log 2>&1
#
# Each hour picks a random delay 0-40min, sleeps, then runs the bot.
# Combined with the random like cap (SESSION_LIKE_MIN-MAX_LIKES_PER_SESSION),
# every run looks different to Bumble's detection systems.

set -euo pipefail
cd "$(dirname "$0")"
export PATH="/home/ada/.local/bin:/usr/bin:/bin:$PATH"

# Random delay 0-40 minutes (in seconds). Cap at 40 to leave a buffer
# + ~10-15min runtime so runs never overlap the next hour.
delay=$((RANDOM % 2400))
start_time=$(date -d "+${delay} seconds" '+%H:%M')
echo "[$(date)] Cron fired. Will run at ~${start_time} (${delay}s delay)"
sleep "$delay"

echo "[$(date)] Starting run..."
source .venv/bin/activate
python -u main.py --mode carlos 2>&1
EXIT_CODE=$?
echo "[$(date)] Done (exit $EXIT_CODE)"
exit $EXIT_CODE
