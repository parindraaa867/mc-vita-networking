# Milestone 1 — Redirect Plugin

**Goal:** make Minecraft Vita send its matchmaking traffic to YOUR PC instead of
Sony, by hijacking the DNS resolution of `*.np.matching.playstation.net`.

If it works, the Vita will try to connect to your PC on TCP 3478/3480 (the
matching ports), and you'll see those `1301`/`1002` frames arrive at the PC.
That single observation proves the whole redirect approach is viable.

This runs *inside* the game, so the game still does its own crypto — the plugin
only changes the destination. No PSN crypto-breaking required.

---

## Build (WSL, vitasdk)

```bash
export VITASDK=/usr/local/vitasdk           # wherever yours lives
cd /mnt/c/Users/purus/mc-vita-capture/plugin
cmake -S . -B build && cmake --build build
# -> build/mcvita_redirect.suprx
```

Set `PC_IP` in `src/main.c` first if your hotspot PC isn't `192.168.137.1`.

---

## Install (Vita)

1. Copy `mcvita_redirect.suprx` to `ux0:tai/` on the Vita.
2. Edit `ux0:tai/config.txt`, add it under the Minecraft title id:
   ```
   *NPWR06859_00
   ux0:tai/mcvita_redirect.suprx
   ```
   > Note: `config.txt` uses the **title id of the running app**. `NPWR06859_00`
   > is the NP Communication ID; the actual *title id* (e.g. `PCSx#####`) may
   > differ — use the title id shown by VitaShell / your bubble manager for the
   > Minecraft app. If unsure, add it under `*ALL` temporarily to test.
3. Reload taiHEN config (HENkaku Settings -> Reload taiHEN config) or reboot.

---

## Verify it loaded

After launching Minecraft and entering multiplayer, check the log the plugin
writes:
```
ux0:data/mcvita_redirect.log
```
You want to see lines like:
```
=== mcvita_redirect loaded ===
[ok] resolver hook installed
[redirect] lookup-22001.ww.np.matching.playstation.net -> 192.168.137.1
```

Then on the PC, run a listener and watch for the game knocking:
```powershell
# crude: see if anything hits the matching ports on the PC
python ..\scripts\fake_matching_listener.py
```

---

## If the hook fails ([error] resolver hook failed)

That means the function NIDs in `main.c` don't match this firmware/game build.
The two NIDs to verify:
- `0xD9DEED85`  = SceNet library
- `0x110F1F44`  = sceNetResolverStartNtoa

Get the real ones from the game's imports:
1. With the game running, dump its module info with a NID-dump plugin
   (e.g. `taipool`/`modulelist`), or
2. Look up the NIDs for your firmware in the vita NID database
   (https://github.com/vitasdk/vita-headers — `db/<fw>/...`), under SceNet.

Update the two values in `taiHookFunctionImport(...)` and rebuild.

> Alternative if the resolver hook is troublesome: hook `sceNetConnect` /
> `sceNetSocket` instead and rewrite the sockaddr destination there — a different
> interception point with the same goal.

---

## What success looks like / next step

- **Vita log shows `[redirect] ...`** -> the hook works.
- **PC sees an inbound TCP connection on 3478/3480** -> the redirect works end to
  end. The game is now talking to my PC.

At that point the game will send the first matching2 request and wait for a
response it understands. That's Milestone 2: the PC has to *answer* in the
matching2 wire format, built from the captured `1301`/`1002` frames + the
dissector.
