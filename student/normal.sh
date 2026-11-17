#!/usr/bin/env bash
# Start the NORMAL traffic phase.
echo normal > /config/Desktop/fllab-control/phase
echo "[normal] Benign traffic to your lab websites is now being generated."
echo "         Run ./stop.sh to pause, then ./attack.sh or ./exploit.sh."
