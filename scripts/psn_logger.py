"""
mitmproxy addon for capturing Minecraft: PS Vita Edition (Enhanced) network traffic.

Logs every HTTP(S) flow the Vita makes — full URLs, headers, and bodies — and
tags the ones that belong to PSN / NP matchmaking infrastructure so the
interesting handshake traffic is easy to find afterwards.

Run with:
    mitmdump -s scripts/psn_logger.py --mode transparent --showhost \
             -w captures/minecraft_vita.flow

Then load captures/minecraft_vita.flow back in mitmweb or mitmproxy to inspect.
Bodies are also dumped to captures/bodies/ for quick offline grepping.
"""

import os
import json
import time
from mitmproxy import http, ctx

# Domains known (from the Vita packet-capture archive) to be PSN / NP infra.
# Anything matching these is almost certainly part of sign-in / matchmaking /
# session brokering — i.e. the stuff to understand to fake a host.
PSN_MARKERS = (
    "np.community.playstation.net",   # profiles, search, matchmaking
    "np.dl.playstation.net",          # downloads / livearea
    "playstation.net",                # catch-all PSN
    "playstation.com",
    "scee.com",                       # SCE Europe game backends (see LBP capture)
    "sonyentertainmentnetwork.com",
    "dl.playstation.net",
)

# Things that are almost certainly Minecraft's own game backend rather than PSN.
GAME_MARKERS = (
    "minecraft",
    "mojang",
    "4jstudios",
    "xboxlive",   # 4J/Mojang sometimes routed account stuff oddly; tag it if seen
)

CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "captures")
BODY_DIR = os.path.join(CAPTURE_DIR, "bodies")
LOG_CSV = os.path.join(CAPTURE_DIR, "flows.csv")

os.makedirs(BODY_DIR, exist_ok=True)


def _classify(host: str) -> str:
    h = host.lower()
    if any(m in h for m in GAME_MARKERS):
        return "GAME"
    if any(m in h for m in PSN_MARKERS):
        return "PSN"
    return "OTHER"


def load(loader):
    # Fresh CSV header each run.
    with open(LOG_CSV, "w", encoding="utf-8") as f:
        f.write("ts,tag,method,host,port,path,status,req_len,resp_len,content_type\n")
    ctx.log.info(f"[psn_logger] logging to {os.path.abspath(LOG_CSV)}")


def _dump_body(flow_id: str, which: str, data: bytes, host: str):
    if not data:
        return
    safe_host = host.replace(":", "_").replace("/", "_")
    fn = os.path.join(BODY_DIR, f"{int(time.time()*1000)}_{safe_host}_{which}_{flow_id[:8]}.bin")
    with open(fn, "wb") as f:
        f.write(data)


def response(flow: http.HTTPFlow):
    host = flow.request.pretty_host
    tag = _classify(host)

    req_body = flow.request.raw_content or b""
    resp_body = flow.response.raw_content if flow.response else b""

    line = "{ts},{tag},{method},{host},{port},{path},{status},{rl},{sl},{ct}\n".format(
        ts=time.strftime("%Y-%m-%d %H:%M:%S"),
        tag=tag,
        method=flow.request.method,
        host=host,
        port=flow.request.port,
        path=flow.request.path.split("?")[0].replace(",", "%2C"),
        status=flow.response.status_code if flow.response else 0,
        rl=len(req_body),
        sl=len(resp_body),
        ct=(flow.response.headers.get("content-type", "") if flow.response else "").split(";")[0],
    )
    with open(LOG_CSV, "a", encoding="utf-8") as f:
        f.write(line)

    # Dump bodies for the interesting (non-OTHER) flows so I can grep offline.
    if tag in ("PSN", "GAME"):
        _dump_body(flow.id, "req", req_body, host)
        _dump_body(flow.id, "resp", resp_body, host)
        ctx.log.info(f"[{tag}] {flow.request.method} {host}{flow.request.path[:60]}")
