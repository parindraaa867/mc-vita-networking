#!/usr/bin/env python3
"""
NP Matching2 transparent relay  (Milestone 2 — the right tool).

Sits between the Vita and Sony's real matching servers. The Vita connects here
(because dns_matching_only.py points agent-/session-* at this PC); I open a
matching connection to the REAL Sony server, then pipe bytes both ways and log
every frame to captures/matching2_relay.log.

Why this beats the replay server:
  - Multiplayer ACTUALLY WORKS (Sony handles the crypto; it just forwards), so no
    more network error.
  - I capture the COMPLETE protocol, both directions, including the 0x1001
    opening handshake the hotspot capture missed. That full log is what I need
    to later build a standalone (Sony-free) server.

The PC resolves the real upstream itself via normal DNS (only the Vita's DNS is
redirected, not the PC's), so getaddrinfo here returns Sony's real IP.

Run as Administrator (binds 3478/3480). Keep dns_matching_only.py running.
"""
import socket
import threading
import datetime
import os

# Port -> the real Sony hostname to forward to.
UPSTREAM_HOST = {
    3478: "agent-22001.ww.np.matching.playstation.net",
    3480: "session-22002.ww.np.matching.playstation.net",
}

LOG = os.path.join(os.path.dirname(__file__), "..", "captures",
                   "matching2_relay.log")
_loglock = threading.Lock()


def now():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(line):
    with _loglock:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(line)


def frame_summary(data: bytes, direction: str) -> str:
    if len(data) >= 6:
        typ = int.from_bytes(data[0:2], "big")
        length = int.from_bytes(data[2:4], "big")
        method = int.from_bytes(data[4:6], "big")
        return (f"{direction} type=0x{typ:04x} method=0x{method:04x} "
                f"len={length} ({len(data)}B) {data[:48].hex()}")
    return f"{direction} ({len(data)}B) {data.hex()}"


def pipe(src, dst, direction, port):
    """Forward src->dst, logging each chunk."""
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            log(f"[{now()}] :{port} {frame_summary(data, direction)}")
            dst.sendall(data)
    except Exception as e:
        log(f"[{now()}] :{port} {direction} pipe ended: {e}")
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass


def handle(client, addr, port):
    host = UPSTREAM_HOST[port]
    try:
        real_ip = socket.gethostbyname(host)
    except Exception as e:
        log(f"[{now()}] :{port} could not resolve {host}: {e}")
        client.close()
        return

    log(f"[{now()}] :{port} Vita {addr[0]}:{addr[1]} <-> {host} ({real_ip})")
    try:
        upstream = socket.create_connection((real_ip, port), timeout=10)
    except Exception as e:
        log(f"[{now()}] :{port} upstream connect failed: {e}")
        client.close()
        return

    t1 = threading.Thread(target=pipe, args=(client, upstream, "Vita->Sony", port),
                          daemon=True)
    t2 = threading.Thread(target=pipe, args=(upstream, client, "Sony->Vita", port),
                          daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()
    client.close(); upstream.close()
    log(f"[{now()}] :{port} session {addr[0]} ended")


def serve(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(8)
    log(f"[*] relay listening on TCP :{port} -> {UPSTREAM_HOST[port]}")
    while True:
        client, addr = s.accept()
        threading.Thread(target=handle, args=(client, addr, port),
                         daemon=True).start()


def main():
    log(f"\n===== relay start {datetime.datetime.now()} =====")
    print("NP Matching2 transparent relay — multiplayer should work AND I log "
          "the full protocol.\n")
    threads = [threading.Thread(target=serve, args=(p,), daemon=True)
               for p in UPSTREAM_HOST]
    for t in threads:
        t.start()
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
