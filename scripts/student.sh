#!/usr/bin/env bash
# Self-host helper for ONE student running the lab in WSL2 (or any Docker host).
#
#   ./scripts/student.sh <N> setup     one-time: generate + build + start
#   ./scripts/student.sh <N> normal    start normal-traffic phase
#   ./scripts/student.sh <N> attack     run one attack round
#   ./scripts/student.sh <N> exploit    run one exploit round
#   ./scripts/student.sh <N> stop       idle
#   ./scripts/student.sh <N> status     show containers + recent labels
#   ./scripts/student.sh <N> collect    zip your data to send back (DO THIS
#                                        BEFORE you uninstall WSL!)
#   ./scripts/student.sh <ID> down       stop the stack
#
# ID is your assigned student id (e.g. 223009712). The operator also gives you
# the shared SEED; set it once:  export FLLAB_SEED=42
# Default is the light headless setup. For the browser desktop, set once:
#   export FLLAB_DESKTOP=1
set -euo pipefail
ID="${1:?usage: student.sh <student-id> <setup|normal|attack|exploit|stop|status|collect|down>}"
CMD="${2:-setup}"
SEED="${FLLAB_SEED:-42}"
PORT=30001                         # self-host uses LAN slot 1
S="s${ID}"
cd "$(dirname "$0")/.."

phase() { echo "$1" > "control/$S/phase"; echo "[$S] phase -> $1"; }

case "$CMD" in
  setup)
    [ -d sites/content ] || python3 sites/gen_sites.py
    DESK=""; [ "${FLLAB_DESKTOP:-0}" = "1" ] && DESK="--with-desktop"
    python3 generate_compose.py --id "$ID" --seed "$SEED" $DESK
    docker compose --profile "$S" up -d --build
    echo
    echo "Stack is up. Drive phases:"
    echo "    ./scripts/student.sh ${ID} normal   (then attack / exploit / stop)"
    if [ -n "$DESK" ]; then
      echo "Browser desktop: https://localhost:${PORT}  user ${S}  (password in students.csv)"
      echo "    (self-signed cert -> Advanced -> Proceed)"
    fi
    ;;
  normal|attack|exploit) phase "$CMD" ;;
  stop|idle)              phase idle ;;
  status)
    docker compose --profile "$S" ps
    echo "--- recent labels ---"
    tail -n 6 logs/events.csv 2>/dev/null || echo "(no events yet)"
    ;;
  collect)
    OUT="$HOME/fllab-${S}-$(date +%Y%m%d-%H%M).tgz"
    tar czf "$OUT" "data/$S" logs/events.csv sites_map.csv
    echo "Wrote ${OUT}"
    echo ">>> SEND THIS FILE to the operator BEFORE you uninstall WSL. <<<"
    ;;
  down) docker compose --profile "$S" down ;;
  *) echo "unknown command: $CMD"; exit 1 ;;
esac
