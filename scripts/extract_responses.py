#!/usr/bin/env python3
"""
Extract canonical NP Matching2 responses from a clean capture.

Reads host_session_full.pcapng, follows the agent (3478) and session (3480)
streams, pairs each Vita request with the very next Sony response, and writes a
method -> response-template table to captures/matching_responses.json.

The matching2_server.py loads that table and replays the right response per
method (sequence-patched). Auto-extraction avoids hand-copying long hex.

Requires tshark on PATH (Wireshark install).
"""
import json
import subprocess
import os

PCAP = os.path.join(os.path.dirname(__file__), "..", "captures",
                    "host_session_full.pcapng")
OUT = os.path.join(os.path.dirname(__file__), "..", "captures",
                   "matching_responses.json")
TSHARK = r"C:\Program Files\Wireshark\tshark.exe"

# (stream, port-label). Find these stream numbers with:
#   tshark -r f.pcapng -Y "tcp.port==3478||tcp.port==3480" -T fields -e tcp.stream | sort -u
STREAMS = {
    "agent": 65,    # 3478
    "session": 72,  # 3480
}


def follow(stream):
    """Return ordered list of (direction, hexbytes). dir 0 = client->server."""
    out = subprocess.run(
        [TSHARK, "-r", PCAP, "-q", "-z", f"follow,tcp,raw,{stream}"],
        capture_output=True, text=True)
    msgs = []
    for line in out.stdout.splitlines():
        s = line.strip()
        if not s or not all(c in "0123456789abcdefABCDEF" for c in s):
            continue
        # Indented (tab) lines are server->client in tshark's follow output.
        direction = 1 if line.startswith("\t") else 0
        msgs.append((direction, s))
    return msgs


def method_of(hexstr):
    if len(hexstr) >= 12:
        return int(hexstr[8:12], 16)  # bytes [4:6]
    return None


def main():
    table = {}
    for label, stream in STREAMS.items():
        msgs = follow(stream)
        table[label] = {}
        for i, (d, hx) in enumerate(msgs):
            if d != 0:
                continue  # only requests
            m = method_of(hx)
            if m is None:
                continue
            # find the next server->client message = the response
            for j in range(i + 1, len(msgs)):
                if msgs[j][0] == 1 and len(msgs[j][1]) >= 12:
                    key = f"0x{m:04x}"
                    if key not in table[label]:
                        table[label][key] = msgs[j][1]
                    break
        print(f"{label} (stream {stream}): "
              f"{', '.join(sorted(table[label].keys()))}")
    with open(OUT, "w") as f:
        json.dump(table, f, indent=2)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
