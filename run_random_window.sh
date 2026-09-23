#!/usr/bin/env bash
# Run BumbleAuto on even hours (10am-8pm).
# Sleeps 0-20min so actual run lands between :00-:20.
# Guarantees 40+ min buffer before next hour's job.
#
# Usage: add to system crontab:
#   0 10-20/2 * * * /path/to/bumble-auto/run_random_window.sh >> cron.log 2>&1
#
# Each hour picks a random delay 0-20min, sleeps, then runs the bot.
# Combined with the random like cap (SESSION_LIKE_MIN-MAX_LIKES_PER_SESSION),
# every run looks different to Bumble's detection systems.

set -euo pipefail
cd "$(dirname "$0")"
export PATH="/home/ada/.local/bin:/usr/bin:/bin:$PATH"

# Max 20 min random delay — still guarantees 40+ min runtime before next cron
delay=$((RANDOM % 1200))
start_time=$(date -d "+${delay} seconds" '+%H:%M')
echo "[$(date)] Cron fired. Will run at ~${start_time} (${delay}s delay)"
sleep "$delay"

echo "[$(date)] Starting run..."
source .venv/bin/activate

# The `|| EXIT_CODE=$?` below is load-bearing, not decoration. Under the
# `set -e` at the top, a bare `python -u main.py` kills this script the
# instant the run fails — before the next two lines get to report it. So
# the Done line only ever printed on success, which is precisely when it
# says nothing useful, and the log's last line on any failure was whatever
# python happened to print last. A missing "Done" line is the failure
# signal, and it reads like the opposite.
#
# errexit doesn't apply to commands in an && / || list except the one
# following the final operator, so python is exempt here while its status
# still lands in EXIT_CODE. The pre-set 0 is required: when the run
# succeeds the || branch never executes, and `set -u` would abort on an
# unset EXIT_CODE at the echo below — the same bug in a different costume.
EXIT_CODE=0
python -u main.py --mode carlos 2>&1 || EXIT_CODE=$?
echo "[$(date)] Done (exit $EXIT_CODE)"
exit $EXIT_CODE
