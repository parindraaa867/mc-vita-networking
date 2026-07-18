# mc-vita-networking

This is me and claude poking at how minecraft on the ps vita does online multiplayer, and whether
you can point it at your own server.

## what i found

- vita minecraft online uses sony's NP Matching2 thing. tcp to the
  `agent`/`session`/`lookup`-`*.np.matching.playstation.net` servers, plus stun
  over udp for nat stuff.
- mapped out the handshake (those `0x1301`/`0x1002` frames) including the full
  "host a world" flow.
- tried making my own server / dns redirect / relay so the vita talks to my pc
  instead. doesn't work. the console checks the whole real connection path, not
  just the bytes coming back — i even relayed sony's *actual* live responses
  through a vps and it still rejects it. only a straight connection to sony works.
- so the only real way to a custom server is modding the game itself to use a
  different network backend, not faking sony on the wire.

## what's in here

- `scripts/` — the capture + analysis stuff, and the server experiments (python/shell)
- `docs/` — how i captured the traffic + my RE notes (`RE_FINDINGS.md`)
- `plugin/` — small taihen plugin from the dns redirect tests
- `mc_server_mod/` — start of the "mod the game" approach (vita plugin + a pc server)

scripts rundown:

- `psn_logger.py` – mitmproxy addon, logs the vita's https traffic
- `dns_matching_only.py` – tiny dns server, only redirects the matching/stun domains
- `stun_server.py` – minimal stun responder
- `matching2_server.py` – replays captured matching responses back to the vita
- `matching2_relay.py` – relays between the vita and the real sony servers
- `analyze.py` / `extract_responses.py` – pull stuff out of the captures

## the two stacks

minecraft has two separate multiplayer paths:

- online (psn): `sceNpMatching2`, with game data over sony's p2p sockets + rudp.
  this is the one tied to sony's servers.
- ad-hoc (local wifi): `sceNetAdhoc` etc. no psn, no validation. this is the old
  psp-style local stack, and that kind of thing has been tunneled online before
  (ppsspp adhoc server, xlink kai).

## where it ends up

- can't fake sony's matching from outside. dead end on real hardware.
- realistic options are both client side: tunnel the ad-hoc stack, or mod the
  game's network layer to hit your own server (and maybe have the pc hold the
  world save).
- a pc can be a 24/7 relay + save store but it can't actually *run* the world,
  the engine only exists on the vita (or vita3k).

## building the plugin stuff

vitasdk + taihen. each folder has a `build.sh`, just `export VITASDK=/usr/local/vitasdk`
first.

## notes

did this for fun / preservation on hardware i own. no game code or decrypted
sony modules in here.
