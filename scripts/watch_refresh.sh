#!/usr/bin/env bash
# Babysit screener refresh-ohlcv: restart if no new tickers in 3 minutes.
TARGET=950
STALL_SECS=180
LOGFILE="/tmp/ohlcv_watch.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOGFILE"; }

kill_refresh() {
  pkill -f "screener refresh-ohlcv" 2>/dev/null
  sleep 2
}

start_refresh() {
  cd /Users/belwinjulian/SwingTrading
  uv run screener refresh-ohlcv >> "$LOGFILE" 2>&1 &
  echo $!
}

log "Watcher started. Target: $TARGET tickers."
kill_refresh
PID=$(start_refresh)
log "Refresh started (PID $PID)."

last_count=0
last_change=$(date +%s)

while true; do
  sleep 30
  count=$(ls /Users/belwinjulian/SwingTrading/data/ohlcv/ 2>/dev/null | wc -l | tr -d ' ')
  now=$(date +%s)

  if [ "$count" -ge "$TARGET" ]; then
    log "Done! $count tickers cached. Exiting watcher."
    exit 0
  fi

  if [ "$count" -gt "$last_count" ]; then
    log "Progress: $count tickers cached."
    last_count=$count
    last_change=$now
  else
    stalled=$(( now - last_change ))
    if [ "$stalled" -ge "$STALL_SECS" ]; then
      log "Stalled at $count for ${stalled}s — restarting refresh."
      kill_refresh
      PID=$(start_refresh)
      log "Restarted (PID $PID)."
      last_change=$now
    fi
  fi
done
