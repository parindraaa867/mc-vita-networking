# Capture Harness — Windows-Native Setup (no WSL, no Linux box)

This runs entirely on Windows. It's simpler than the Linux version because the
**PS Vita has a built-in HTTP proxy setting**, so there's no need for DNS redirection,
iptables, or transparent routing — just tell the Vita to send its web traffic
straight to mitmproxy on your PC.

Two layers, same as before:
1. **mitmproxy** (Windows) catches the Vita's HTTP/HTTPS → sign-in & matchmaking.
2. **Wireshark + Npcap** catches the raw **UDP game traffic** (the real prize).

Clean-room only: learn from observed traffic, never leaked source.

---

## 0. Find your PC's LAN IP

PowerShell:
```powershell
(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" }).IPAddress
```
Note it — call it **PC_IP** (e.g. `192.168.1.50`). The Vita must be on the same
Wi-Fi/LAN.

---

## 1. Install the tools (one time)

- **mitmproxy for Windows:** https://mitmproxy.org/  → download the Windows installer.
- **Wireshark:** https://www.wireshark.org/  → install it, and **let it install Npcap** when prompted (required for capture).
- **Python 3** (you have it). Optional DNS fallback needs: `pip install dnslib`.

---

## 2. Start mitmproxy in proxy mode (Terminal 1 — PowerShell)

```powershell
cd C:\Users\purus\mc-vita-capture
mitmweb -s scripts\psn_logger.py -p 8080 -w captures\minecraft_vita.flow
```
- `mitmweb` opens a browser UI at http://127.0.0.1:8080 so you can watch flows live.
- It listens as a normal HTTP proxy on **PC_IP:8080**.
- Leave this running.

> If Windows Firewall pops up, **Allow** it on private networks, or the Vita
> won't be able to reach the proxy.

---

## 3. Install mitmproxy's certificate on the Vita

The Vita must trust mitmproxy to read HTTPS.
1. With mitmproxy running and the Vita's proxy set (step 5), open the Vita
   browser to **http://mitm.it** → download the cert.
   - The Vita's stock browser may not install certs cleanly. If so, the cert
     also lives on your PC at `C:\Users\purus\.mitmproxy\mitmproxy-ca-cert.cer`.
2. **Reality check:** PSN endpoints are frequently **certificate-pinned**. Pinned
   calls will fail even with the cert trusted — that's expected and is itself
   useful data (it proves a taiHEN unpinning plugin is needed later). Capture
   what you can; note which hosts error in the mitmweb UI.

---

## 4. Start the raw UDP capture (Wireshark)

1. Open **Wireshark**.
2. Double-click your Wi-Fi/Ethernet interface to start capturing.
3. In the filter bar, type (replace with the Vita's IP once you know it):
   ```
   ip.addr == <VITA_IP>
   ```
4. Start this **before** you open Minecraft on the Vita.
   - Find the Vita's IP under Vita **Settings → Network → (your Wi-Fi) → View status**.

This is the layer that captures the peer-to-peer game protocol mitmproxy can't see.

---

## 5. Point the Vita at your PC

On the Vita: **Settings → Network → Wi-Fi Settings → (your network) → Advanced
Settings → Proxy Server → Use**:
- **Address:** PC_IP
- **Port:** 8080

Save / test the connection.

---

## 6. Capture a session

1. Confirm mitmweb (terminal 1) and Wireshark are both running.
2. On the Vita, open **Minecraft: Vita Edition (Enhanced)**.
3. Go online: host a world / join the Friends or online list / start a session.
4. Play for a couple of minutes — move around, let entities sync, have a second
   device/player join if you can. The more multiplayer activity, the richer the data.

---

## 7. Stop and analyze

1. Stop Wireshark (red square) → **File → Save As** → `captures\raw_session1.pcapng`.
2. Stop mitmweb (Ctrl-C in terminal 1). `captures\flows.csv` is now populated.
3. Run the summary:
   ```powershell
   cd C:\Users\purus\mc-vita-capture
   python scripts\analyze.py
   ```

---

## 8. (Optional) DNS fallback

If some traffic ignores the proxy, run the Python DNS redirect as Administrator
and set the Vita's **DNS** to PC_IP:
```powershell
pip install dnslib
python scripts\dns_redirect.py 192.168.1.50   # use your PC_IP
```

---

## What to keep afterward

- `captures\flows.csv`
- the `analyze.py` output
- the Wireshark capture filtered to the Vita's UDP (save the `.pcapng`, or the
  **Statistics → Conversations → UDP** tab)

Those answer:
- how much of PSN would have to be faked,
- whether the game payload is plaintext or encrypted,
- and therefore how feasible a PC host emulator actually is.

---

## Cleanup

When done, **turn the Vita's proxy back OFF** (Settings → Network → Proxy →
Do Not Use) or it'll have no internet once mitmproxy is closed.
