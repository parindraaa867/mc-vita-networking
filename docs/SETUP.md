# Minecraft: PS Vita Edition (Enhanced) — Capture Harness

**Goal of this stage:** produce the first real network trace of Vita Minecraft
going online, to see *how* its multiplayer works. This is the prerequisite for
everything else (fake-PSN, PC host emulator). No server yet — this stage is just
gathering the data that tells you if/how one is buildable.

Everything here is **clean-room**: learn the protocol by *observing traffic*,
not from any leaked source. Keep it that way.

---

## What you need

- A HENkaku/Enso Vita (or PS TV) with **Minecraft Vita Edition Enhanced** installed.
- Your PC on the **same LAN** as the Vita.
- WSL with: `mitmproxy`, `dnsmasq`, `tcpdump`, `python3`.
  ```bash
  sudo apt update && sudo apt install -y mitmproxy dnsmasq tcpdump python3
  ```

---

## The picture

```
 Vita  ──DNS──►  this PC (dnsmasq)      # answers PSN domains with PC's IP
 Vita  ──HTTPS─► this PC (mitmproxy)    # transparent proxy, logs the handshake
 Vita  ──UDP───► (peers / PSN)          # raw game P2P — caught by tcpdump
```

Two capture layers run at once:
1. **mitmproxy** sees HTTP/HTTPS (sign-in, matchmaking REST). → `scripts/psn_logger.py`
2. **tcpdump** sees the raw UDP the game uses for actual play. → `scripts/capture_raw.sh`

You need both, because the interesting game protocol is almost certainly the UDP
that never touches mitmproxy.

---

## ⚠️ WSL2 networking note (read first)

WSL2 has its own NAT'd IP that the Vita on your LAN **cannot reach**. Two options:

- **Easiest:** run this from a **real Linux box / Raspberry Pi** on the LAN, or
  a Linux VM in **bridged** mode. Then the PC IP the Vita talks to is real.
- **WSL2 anyway:** you must forward the Windows host's LAN ports into WSL with
  `netsh interface portproxy` (53/udp for DNS, 80+443 for mitmproxy) and open
  the Windows firewall. This is fiddly; the bridged-VM/Pi route is far less pain.

Whichever you pick, note **the IP the Vita will actually reach** — call it
`PC_IP` — and use it consistently below.

---

## Steps

### 1. Point the config files at your PC
Edit `scripts/dnsmasq.conf` and replace every `192.168.1.50` with your `PC_IP`.

### 2. Install mitmproxy's CA on the Vita
PSN traffic is TLS. To read it, the Vita must trust mitmproxy's certificate.
- Run `mitmproxy` once to generate the CA (`~/.mitmproxy/mitmproxy-ca-cert.cer`).
- **Reality check:** PSN endpoints are often **certificate-pinned**, so even an
  installed CA may not be enough — pinned calls will just fail. That failure is
  itself useful data (it shows a taiHEN unpinning plugin is required later).
  Capture what you can; note which hosts refuse.

### 3. Start DNS redirect (terminal 1)
```bash
sudo dnsmasq --no-daemon --conf-file=scripts/dnsmasq.conf
```

### 4. Start the transparent proxy (terminal 2)
```bash
mitmdump -s scripts/psn_logger.py --mode transparent --showhost \
         -w captures/minecraft_vita.flow
```
(Transparent mode needs the PC to route the Vita's 80/443 to mitmproxy —
`iptables` REDIRECT on Linux. On a Pi/VM:
```bash
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 80  -j REDIRECT --to-port 8080
sudo iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 443 -j REDIRECT --to-port 8080
```
)

### 5. Start raw capture (terminal 3)
```bash
sudo ./scripts/capture_raw.sh <VITA_IP> eth0
```

### 6. On the Vita
- Settings → Network → set **DNS** (and gateway, if doing transparent) to `PC_IP`.
- Open **Minecraft Enhanced** → go online / host or join a session → play a bit.

### 7. Stop & analyze
Ctrl-C all three. Then:
```bash
python3 scripts/analyze.py
```
Open the newest `captures/raw_*.pcap` in Wireshark, filter
`udp && ip.addr == <VITA_IP>`.

---

## What to look for in the results

| Question | Where to look |
|---|---|
| What domains does sign-in hit? | `flows.csv` rows tagged `PSN` |
| Is there a REST matchmaking call? | `analyze.py` "matchmaking" section |
| Is the game P2P, and on what UDP ports? | the `.pcap`, UDP filter |
| Is the P2P payload encrypted or plaintext? | inspect UDP bytes in Wireshark |
| Are PSN calls cert-pinned? | mitmproxy TLS errors per host |

Those five answers determine whether a PC host emulator is feasible and how
much of PSN would have to be faked. Keep `flows.csv`, the `analyze.py` output,
and the UDP conversation from Wireshark.
