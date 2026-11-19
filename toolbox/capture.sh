#!/bin/sh
# Capture entrypoint for the capture sidecar.
#
# We must NOT use `tcpdump -i any`: it writes "Linux cooked v2" (SLL2) frames
# that nfstream/nDPI cannot parse (to_pandas() returns None). Instead capture on
# the lab-LAN interface (the one holding a 10.10.0.0/16 address) so the pcap is
# standard Ethernet, which nfstream reads correctly. Works in both headless
# (single LAN interface) and --with-desktop (wan + lan) modes.
IFACE=$(ip -o -4 addr show 2>/dev/null | awk '/ 10\.10\./ {print $2; exit}')
[ -z "$IFACE" ] && IFACE=eth0
echo "capture: using interface $IFACE"
exec tcpdump -i "$IFACE" -n -s 0 -G 3600 \
    -w /pcap/%Y%m%d-%H%M%S.pcap -Z root net 10.10.0.0/16
