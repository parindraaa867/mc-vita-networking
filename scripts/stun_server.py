#!/usr/bin/env python3
"""
Sony-variant STUN responder  (Path A, component 1).

The Vita queries us.np.stun.playstation.net (52.40.62.110) on UDP 3478/3479 to
learn its public address + NAT type BEFORE/while talking to the matching agent.
When I redirect the agent to my LAN PC but STUN still goes to real Sony (WAN),
the Vita's NAT view is inconsistent and it abandons the agent connection after
~5s. This server answers STUN locally so the NAT view is consistent with the
agent being my PC.

Protocol (RFC 5389 + classic, as captured from real Sony):
  Request:  0x0001 Binding Request, 20-byte header (type,len,txid[16]) + attrs.
  Response: 0x0101 Binding Response with attributes:
     0x0004 SOURCE-ADDRESS     (this server's addr)
     0x0005 CHANGED-ADDRESS    (the "other" server addr — I point it at us:3479)
     0x8020 XOR-MAPPED-ADDRESS (the client's mapped address, XOR'd w/ magic cookie)
     0x0001 MAPPED-ADDRESS     (plain, for older clients)
     [0x0008 MESSAGE-INTEGRITY HMAC-SHA1 — OMITTED in v1 to test if required]

I report the client's address AS I SEE IT (its LAN ip:port). For LAN play that
makes "public" == LAN, which is what I want.

Run as Administrator. Bind 3478 and 3479 (UDP). Keep dns_matching_only.py
running (now also redirecting us.np.stun -> this PC) and matching2_server.py.
"""
import socket
import struct
import threading
import sys

MAGIC = 0x2112A442  # RFC5389 magic cookie

def addr_attr(attr_type, ip_str, port):
    fam = 0x01
    ipb = socket.inet_aton(ip_str)
    val = struct.pack("!BBH", 0, fam, port) + ipb
    return struct.pack("!HH", attr_type, len(val)) + val

def xor_mapped_attr(ip_str, port):
    fam = 0x01
    xport = port ^ (MAGIC >> 16)
    ipi = struct.unpack("!I", socket.inet_aton(ip_str))[0]
    xip = ipi ^ MAGIC
    val = struct.pack("!BBH", 0, fam, xport) + struct.pack("!I", xip)
    return struct.pack("!HH", 0x0020, len(val)) + val

def build_response(txid, client_ip, client_port, my_ip, this_port, other_port):
    attrs = b""
    attrs += addr_attr(0x0004, my_ip, this_port)        # SOURCE-ADDRESS (us)
    attrs += addr_attr(0x0005, my_ip, other_port)       # CHANGED-ADDRESS (us, other port)
    attrs += xor_mapped_attr(client_ip, client_port)    # XOR-MAPPED-ADDRESS
    attrs += addr_attr(0x0001, client_ip, client_port)  # MAPPED-ADDRESS (plain)
    header = struct.pack("!HH", 0x0101, len(attrs)) + txid
    return header + attrs

def serve(bind_port, my_ip, other_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", bind_port))
    print(f"[*] STUN listening on UDP :{bind_port}")
    while True:
        data, addr = s.recvfrom(2048)
        if len(data) < 20:
            continue
        mtype, mlen = struct.unpack("!HH", data[:4])
        txid = data[4:20]
        print(f"[STUN] :{bind_port} req type=0x{mtype:04x} from {addr[0]}:{addr[1]} ({len(data)}B)")
        if mtype == 0x0001:  # Binding Request
            resp = build_response(txid, addr[0], addr[1], my_ip, bind_port, other_port)
            s.sendto(resp, addr)
            print(f"         -> mapped {addr[0]}:{addr[1]}, sent {len(resp)}B")

def main():
    if len(sys.argv) < 2:
        print("usage: python stun_server.py <THIS_PC_IP>   e.g. 192.168.1.31")
        sys.exit(1)
    my_ip = sys.argv[1]
    print(f"Sony-variant STUN responder on {my_ip} (3478/3479). Ctrl-C to stop.\n")
    threading.Thread(target=serve, args=(3478, my_ip, 3479), daemon=True).start()
    threading.Thread(target=serve, args=(3479, my_ip, 3478), daemon=True).start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nbye")

if __name__ == "__main__":
    main()
