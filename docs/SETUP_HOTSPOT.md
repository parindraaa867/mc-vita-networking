# Capture v2 — Hotspot Method (for the UDP matchmaking + game traffic)

## Why this, instead of the proxy

The proxy method (SETUP_WINDOWS.md) was great for grabbing PSN's HTTP config
files — that got `matching.xml` and the matching-agent server. **That part is done.**

But the proxy method **cannot** capture the next bit:
- The matchmaking handshake is **UDP on port 3478** — HTTP proxies don't carry UDP.
- Worse, intercepting PSN's pinned TLS **broke the sign-in session**, so the game
  never even reached the matchmaking stage.

This method fixes both: the PC becomes the Vita's **gateway**, so ALL its traffic
(UDP included) shows up at the packet level, and PSN works normally because it's
only *forwarding*, not intercepting.

---

## Setup

### 1. Turn on Windows Mobile Hotspot
Settings → Network & Internet → **Mobile hotspot** → On.
- Share from: your internet connection (Wi-Fi or Ethernet).
- Note the **hotspot Wi-Fi name + password** it shows.
- If "Mobile hotspot" is greyed out, your Wi-Fi adapter may not support hosted
  networks — fall back method below.

### 2. IMPORTANT: turn the Vita's proxy OFF
Vita → Settings → Network → Wi-Fi → your network → Advanced → **Proxy → Do Not Use.**
(No mitmproxy this time. Leave it closed.)

### 3. Connect the Vita to the PC's hotspot
Vita → Settings → Network → Wi-Fi → pick the **hotspot network** → connect.
- The Vita now gets its internet *through* your PC.
- Find the Vita's new IP: it'll be on the hotspot subnet (often `192.168.137.x`).
  Check Windows: `arp -a` in PowerShell, or the hotspot panel shows connected
  devices + IPs.

### 4. Start Wireshark on the hotspot adapter
- Open Wireshark.
- The capture interface is the **"Local Area Connection* N"** virtual adapter that
  Mobile Hotspot creates (NOT your normal Wi-Fi). If unsure, start capturing on
  all and watch which one shows the Vita's IP.
- Filter (use the Vita's hotspot IP):
  ```
  ip.addr == 192.168.137.x
  ```

### 5. Reproduce the multiplayer attempt
- Open Minecraft Enhanced on the Vita → go online → host a world AND/OR sit in
  the "searching for players" screen for 2–3 minutes.
- This time PSN sign-in works (no interception), so it should actually reach the
  **matching agent** — that's the UDP 3478 traffic to grab.

### 6. Stop & save
- Wireshark stop → File → Save As → `captures\hotspot_session1.pcapng`.

---

## What success looks like

After saving, look for:
- UDP packets between the Vita and an IP on **port 3478** (the matching agent) —
  this is the NP Matching2 handshake.
- Possibly other UDP ports opening up = the actual peer-to-peer game channel.
- Whether those payloads are **plaintext or encrypted** (the make-or-break Q).

Then analyze `captures\hotspot_session1.pcapng`.

---

## Fallback if Mobile Hotspot won't work

If your adapter can't host: connect the PC to the router by **Ethernet**, and the
Vita by Wi-Fi, then either:
- enable **Internet Connection Sharing (ICS)** on the Ethernet→Wi-Fi, or
- use `bettercap`/`arp spoof` to route the Vita's traffic through the PC (more
  involved).
