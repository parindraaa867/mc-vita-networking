#!/usr/bin/env python3
"""
NP Matching2 standalone server — Milestone 2.

Loads the canonical responses auto-extracted from the clean host capture
(captures/matching_responses.json) and answers the Vita itself — NO Sony, NO
relay. Replays the correct response per method, sequence-patched.

This is the decisive crypto test: I now have the COMPLETE response set (incl.
the 0x1001 opening) and I connect DIRECTLY (no relay NAT issue). If the Vita
accepts my responses and a hosted world opens, the 16-byte tokens are NOT
cryptographically validated -> I can build a real stateful room registry on top
of this. If it errors right after a reply, there's per-session crypto.

Run as Administrator. Keep dns_matching_only.py running so the Vita reaches it.
"""
import socket
import threading
import binascii
import datetime
import json
import os

RESP_FILE = os.path.join(os.path.dirname(__file__), "..", "captures",
                         "matching_responses.json")
PORT_LABEL = {3478: "agent", 3480: "session"}


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def load_tables():
    with open(RESP_FILE) as f:
        raw = json.load(f)
    # label -> { method_int -> bytes }
    tables = {}
    for label, methods in raw.items():
        tables[label] = {int(k, 16): binascii.unhexlify(v)
                         for k, v in methods.items()}
    return tables


TABLES = load_tables()


def read_frame(conn):
    # Read one byte first. Real frames start with 0x13 (type 0x1301); a lone
    # 0x00 is a HEARTBEAT the server must echo (seen between 0x1001 and 0x1008
    # in the capture). Without this the Vita times out after ~5s.
    first = conn.recv(1)
    if not first:
        return None
    if first != b"\x13":
        return first  # heartbeat / single byte — caller echoes it
    hdr = first
    while len(hdr) < 4:
        c = conn.recv(4 - len(hdr))
        if not c:
            return None
        hdr += c
    total = int.from_bytes(hdr[2:4], "big")
    if total < 4:
        return hdr
    body = b""
    while len(body) < total - 4:
        c = conn.recv(total - 4 - len(body))
        if not c:
            return None
        body += c
    return hdr + body


def patch_seq(resp: bytes, seq: bytes) -> bytes:
    return resp[:6] + seq + resp[10:]


def handle(conn, addr, port):
    label = PORT_LABEL[port]
    table = TABLES.get(label, {})
    print(f"[{now()}] {label}:{port} connect from {addr[0]}:{addr[1]}")
    try:
        while True:
            frame = read_frame(conn)
            if frame is None:
                print(f"[{now()}] {label}: {addr[0]} closed")
                return
            if len(frame) < 6:
                conn.sendall(frame)  # echo keepalive
                continue
            method = int.from_bytes(frame[4:6], "big")
            seq = frame[6:10]
            resp = table.get(method)
            if resp:
                conn.sendall(patch_seq(resp, seq))
                print(f"[{now()}] {label}: req 0x{method:04x} seq={seq.hex()} "
                      f"-> sent {len(resp)}B")
            else:
                print(f"[{now()}] {label}: req 0x{method:04x} seq={seq.hex()} "
                      f"-> NO RESPONSE for this method")
    except ConnectionResetError:
        print(f"[{now()}] {label}: {addr[0]} reset")
    except Exception as e:
        print(f"[{now()}] {label}: error {e}")
    finally:
        conn.close()


def serve(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(8)
    print(f"[*] {PORT_LABEL[port]} listening on :{port} "
          f"({len(TABLES.get(PORT_LABEL[port], {}))} methods)")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle, args=(conn, addr, port),
                         daemon=True).start()


def main():
    print("NP Matching2 standalone server (Milestone 2) — no Sony, no relay.")
    print("Testing whether the Vita accepts my own responses.\n")
    ts = [threading.Thread(target=serve, args=(p,), daemon=True)
          for p in PORT_LABEL]
    for t in ts:
        t.start()
    try:
        for t in ts:
            t.join()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
