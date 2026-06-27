#!/usr/bin/env bash
#
# Raw packet capture for the Vita's NON-HTTP traffic.
#
# Minecraft's actual in-game multiplayer is almost certainly UDP peer-to-peer,
# which will NOT pass through mitmproxy (that only sees HTTP/HTTPS). This grabs
# everything to/from the Vita at the packet level so we can study the game
# protocol, NAT-traversal, and any custom UDP ports.
#
# Usage:
#   sudo ./scripts/capture_raw.sh <VITA_IP> [iface]
#
# Open the resulting .pcap in Wireshark afterwards. Filter ideas:
#   udp && ip.addr == <VITA_IP>           -> all Vita UDP (game P2P candidate)
#   !(tcp.port == 443 || tcp.port == 80)  -> non-web traffic
#
set -euo pipefail

VITA_IP="${1:?usage: capture_raw.sh <VITA_IP> [iface]}"
IFACE="${2:-any}"
OUT="captures/raw_$(date +%Y%m%d_%H%M%S).pcap"

mkdir -p captures
echo "[*] Capturing all traffic for Vita $VITA_IP on iface '$IFACE'"
echo "[*] Writing to $OUT  (Ctrl-C to stop)"
echo "[*] Tip: start this BEFORE you open Minecraft on the Vita and go online."

# host filter keeps the file small and focused on the Vita.
exec tcpdump -i "$IFACE" -n -w "$OUT" "host $VITA_IP"
