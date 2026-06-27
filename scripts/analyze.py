#!/usr/bin/env python3
"""
First-pass analyzer for a capture session.

Reads captures/flows.csv (from psn_logger.py) and prints a summary:
  - which hosts the Vita talked to, grouped by PSN / GAME / OTHER
  - the endpoints most likely tied to matchmaking / session setup
  - a reminder of which raw .pcap to open in Wireshark for the P2P side

Usage:
    python3 scripts/analyze.py
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(__file__)
CSV = os.path.join(HERE, "..", "captures", "flows.csv")

# Path fragments that smell like matchmaking / session brokering.
MATCH_HINTS = ("match", "session", "lobby", "room", "join", "host",
               "p2p", "nat", "signal", "presence", "search")


def main():
    if not os.path.exists(CSV):
        print("No captures/flows.csv yet. Run a capture session first.")
        return

    by_tag = defaultdict(lambda: defaultdict(int))   # tag -> host -> count
    suspects = []

    with open(CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_tag[row["tag"]][row["host"]] += 1
            path = row["path"].lower()
            if any(h in path for h in MATCH_HINTS):
                suspects.append((row["tag"], row["method"], row["host"], row["path"]))

    for tag in ("GAME", "PSN", "OTHER"):
        hosts = by_tag.get(tag, {})
        if not hosts:
            continue
        print(f"\n=== {tag} hosts ({len(hosts)}) ===")
        for host, n in sorted(hosts.items(), key=lambda x: -x[1]):
            print(f"  {n:5d}  {host}")

    print("\n=== Likely matchmaking / session endpoints ===")
    if not suspects:
        print("  (none matched yet — the handshake may be raw UDP; check the .pcap)")
    else:
        for tag, method, host, path in suspects:
            print(f"  [{tag}] {method} {host}{path}")

    print("\nNext: open the newest captures/raw_*.pcap in Wireshark and filter")
    print("  udp && ip.addr == <VITA_IP>   to study the peer-to-peer game protocol.")


if __name__ == "__main__":
    main()
