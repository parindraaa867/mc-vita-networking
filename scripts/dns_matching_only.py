#!/usr/bin/env python3
"""
Matching-only DNS redirect  (the stable, plugin-free approach).

This is how real Vita server revivals do it: redirect ONLY the specific game
server domains to your PC, and pass everything else through to real DNS so PSN
sign-in keeps working normally. No in-process hooking, so nothing to crash the
game.

I hijack ONLY:
    *.np.matching.playstation.net   (agent / session / lookup -> matchmaking)

Everything else (sign-in, profiles, friends, auth) resolves for real.

Run as Administrator (binds UDP 53). The Vita must use this PC as its DNS:
  - Easiest: keep using Windows Mobile Hotspot; set the Vita's DNS to the PC
    (192.168.137.1) in Wi-Fi advanced settings.
  - Then point the Vita at this server.

Requires:  pip install dnslib
"""
import sys
import socket
from dnslib import DNSRecord, RR, A, QTYPE
from dnslib.server import DNSServer, BaseResolver

UPSTREAM = "1.1.1.1"

# ONLY these get redirected. Narrow on purpose — do NOT hijack sign-in domains,
# or PSN auth breaks and the game crashes/cant connect.
# Path A: also redirect STUN so the Vita's NAT view is consistent with the
# matching agent being my LAN PC (see stun_server.py).
HIJACK_SUFFIXES = (
    ".np.matching.playstation.net",
    ".np.stun.playstation.net",
)


class MatchingRedirector(BaseResolver):
    def __init__(self, pc_ip):
        self.pc_ip = pc_ip

    def resolve(self, request, handler):
        qname = str(request.q.qname).rstrip(".").lower()
        reply = request.reply()

        if any(qname.endswith(s) for s in HIJACK_SUFFIXES):
            print(f"[HIJACK] {qname} -> {self.pc_ip}")
            reply.add_answer(RR(request.q.qname, QTYPE.A,
                                rdata=A(self.pc_ip), ttl=30))
            return reply

        # Log every passthrough so I can confirm the Vita is using us at all.
        print(f"[query ] {qname}")

        # Everything else: resolve for real so PSN works.
        try:
            up = DNSRecord.parse(request.send(UPSTREAM, 53, timeout=3))
            for rr in up.rr:
                reply.add_answer(rr)
        except Exception as e:
            print(f"[warn] upstream failed for {qname}: {e}")
        return reply


def main():
    if len(sys.argv) < 2:
        print("usage: python dns_matching_only.py <THIS_PC_IP>   e.g. 192.168.137.1")
        sys.exit(1)
    pc_ip = sys.argv[1]
    print(f"[*] Matching-only DNS redirect. Hijacking {HIJACK_SUFFIXES} -> {pc_ip}")
    print("[*] Everything else resolves normally (PSN sign-in stays intact).")
    print("[*] Set the Vita's DNS to this PC, then start Minecraft multiplayer.\n")
    # Bind to the SPECIFIC hotspot IP, not 0.0.0.0, to try to win the port over
    # the Windows ICS DNS responder. If this errors with "address already in
    # use", ICS owns :53 — stop it (see disable_ics_dns.ps1).
    DNSServer(MatchingRedirector(pc_ip), port=53, address=pc_ip).start()


if __name__ == "__main__":
    main()
