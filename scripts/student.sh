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
#   ./scripts/student.sh <N> down       stop the stack
#
# N is your assigned student number (e.g. 7). The operator also gives you the
# shared SEED; set it once:  export FLLAB_SEED=42
set -euo pipefail
N="${1:?usage: student.sh <student-number> <setup|normal|attack|exploit|stop|status|collect|down>}"
CMD="${2:-setup}"
SEED="${FLLAB_SEED:-42}"
PORT=$((30000 + N))
S=$(printf 's%03d' "$N")
cd "$(dirname "$0")/.."

phase() { echo "$1" > "control/$S/phase"; echo "[$S] phase -> $1"; }

case "$CMD" in
  setup)
    [ -d sites/content ] || python3 sites/gen_sites.py
    python3 generate_compose.py --start "$N" --end "$N" --seed "$SEED"
    docker compose --profile "$S" up -d --build
    echo
    echo "Stack is up. Open the desktop in your browser:"
    echo "    https://localhost:${PORT}    user: ${S}"
    echo "    password: see the 'password' column in students.csv"
    echo "    (self-signed cert -> Advanced -> Proceed)"
    echo "Then drive phases:  ./scripts/student.sh ${N} normal   (etc.)"
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
