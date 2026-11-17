#!/usr/bin/env bash
# Operator helper: bring a student's stack (desktop + ~5 sites + toolbox +
# capture) up or down. Only active students consume resources.
#
#   ./scripts/session.sh s001 up
#   ./scripts/session.sh s001 down
set -euo pipefail
S="${1:?usage: session.sh <sNNN> up|down}"
ACTION="${2:?usage: session.sh <sNNN> up|down}"
case "$ACTION" in
  up)   docker compose --profile "$S" up -d ;;
  down) docker compose --profile "$S" down ;;
  *)    echo "action must be 'up' or 'down'"; exit 1 ;;
esac
