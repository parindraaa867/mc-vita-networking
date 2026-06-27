#!/usr/bin/env python3
"""
Milestone-1 confirmation listener.

Listens on the NP Matching2 ports (TCP 3478 & 3480) on the PC. When the redirect
plugin works, the Vita will connect here instead of Sony. This just accepts the
connection, logs the peer, and dumps the first bytes the game sends — which
should be a 1301-type matching2 request frame.

It does NOT speak the protocol yet (that's Milestone 2). Right now the goal is only
proof that the game's matchmaking traffic reaches the PC.

Run (PowerShell, may need Administrator for low ports / firewall allow):
    python scripts\\fake_matching_listener.py
"""
import socket
import threading
import datetime

PORTS = [3478, 3480]


def hexdump(data: bytes, width=16):
    out = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"  {i:04x}  {hexs:<{width*3}}  {ascii_}")
    return "\n".join(out)


def handle(conn, addr, port):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ts}] *** CONNECTION on :{port} from {addr[0]}:{addr[1]} ***")
    print("    ^ the redirect works — the Vita is talking to your PC!")
    try:
        conn.settimeout(5)
        data = conn.recv(4096)
        if data:
            print(f"    first {len(data)} bytes:")
            print(hexdump(data))
            # Tag the frame type I documented.
            if data[:2] == b"\x13\x01":
                print("    -> looks like a matching2 REQUEST frame (0x1301). Confirmed.")
        else:
            print("    (connected but sent no data before timeout)")
    except socket.timeout:
        print("    (no data within 5s)")
    except Exception as e:
        print(f"    error: {e}")
    finally:
        conn.close()


def serve(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
    except OSError as e:
        print(f"[!] could not bind :{port} ({e}). "
              f"Close anything using it / run as admin.")
        return
    s.listen(5)
    print(f"[*] listening on TCP :{port}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle, args=(conn, addr, port), daemon=True).start()


def main():
    print("Matching2 redirect listener — waiting for the Vita to connect.")
    print("Make sure the plugin is loaded and the Vita is on your hotspot.\n")
    threads = [threading.Thread(target=serve, args=(p,), daemon=True) for p in PORTS]
    for t in threads:
        t.start()
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
