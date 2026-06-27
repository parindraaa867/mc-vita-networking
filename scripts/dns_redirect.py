#!/usr/bin/env python3
"""
Tiny pure-Python DNS server for Windows (no dnsmasq needed).

OPTIONAL fallback. The main Windows path uses the Vita's built-in HTTP *proxy*
setting (see docs/SETUP_WINDOWS.md), which needs no DNS trickery at all. Use
this only if some traffic ignores the proxy and you want to force PSN/Minecraft
domains to resolve to this PC.

It answers a configured list of domains with THIS_PC_IP and forwards everything
else to a real upstream resolver so the Vita keeps working.

Run (Administrator PowerShell, since it binds UDP 53):
    python scripts\\dns_redirect.py 192.168.1.50

Requires:  pip install dnslib
"""
import sys
import socket
from dnslib import DNSRecord, RR, A, QTYPE
from dnslib.server import DNSServer, BaseResolver

UPSTREAM = "1.1.1.1"

# Domains to hijack -> answered with THIS_PC_IP. Add more as captures reveal them.
HIJACK_SUFFIXES = (
    "np.community.playstation.net",
    "np.dl.playstation.net",
    "dl.playstation.net",
    "sonyentertainmentnetwork.com",
    "minecraft.net",
    "mojang.com",
)


class Redirector(BaseResolver):
    def __init__(self, pc_ip):
        self.pc_ip = pc_ip

    def resolve(self, request, handler):
        qname = str(request.q.qname).rstrip(".").lower()
        reply = request.reply()
        if any(qname.endswith(s) for s in HIJACK_SUFFIXES):
            print(f"[hijack] {qname} -> {self.pc_ip}")
            reply.add_answer(RR(request.q.qname, QTYPE.A, rdata=A(self.pc_ip), ttl=60))
            return reply
        # Pass through to upstream.
        try:
            proxied = DNSRecord.parse(request.send(UPSTREAM, 53, timeout=3))
            for rr in proxied.rr:
                reply.add_answer(rr)
        except Exception as e:
            print(f"[warn] upstream failed for {qname}: {e}")
        return reply


def main():
    if len(sys.argv) < 2:
        print("usage: python dns_redirect.py <THIS_PC_IP>")
        sys.exit(1)
    pc_ip = sys.argv[1]
    print(f"[*] DNS redirect up. Hijacking {len(HIJACK_SUFFIXES)} domains -> {pc_ip}")
    print("[*] Point the Vita's DNS at this PC. Ctrl-C to stop.")
    server = DNSServer(Redirector(pc_ip), port=53, address="0.0.0.0")
    server.start()


if __name__ == "__main__":
    main()
