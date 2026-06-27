# RE notes

rough notes from reversing how vita minecraft does matchmaking. mostly for
future me.

## the protocol

online multiplayer = sony NP Matching2. the vita talks tcp to:

- `agent-22001.ww.np.matching.playstation.net` :3478
- `session-22002.ww.np.matching.playstation.net` :3480
- `lookup-22001.ww.np.matching.playstation.net`

config comes from `static-resource.np.community.playstation.net/.../NPWR06859_00-matching.xml`
(NPWR06859_00 = minecraft's np comm id, title id is PCSE00491).

messages are length-prefixed TLV, big endian:

```
[2B type][2B len][2B method][4B seq][2B status][4B ctx][16B token][TLV body...]
 0x1301 = request
 0x1002 = response
```

methods seen: 0x1001 connect/auth (first one), 0x1008 hello, 0x1209 lookup,
0x1202 create room, 0x1207 keepalive, 0x120a leave. session server uses 0x32xx.

the full host flow (captured):

```
0x1001 auth -> 0x1008 hello -> 0x1209 lookup -> 0x1202 create room
-> 0x1207 keepalive...  then 0x120a on exit
```

room create carries the room name + the host's ip. game data after that goes
over sony's SCE_NET_SOCK_DGRAM_P2P sockets + rudp, mesh with the host as hub.

## why a custom server doesn't work

tried a bunch, all fail at the 0x1001 step (vita closes after ~5s):

- standalone server replaying captured responses (lan + public vps) — fail
- same + emulating stun — fail
- relaying to the REAL sony servers through my pc/vps — fail

the relay is the key one: it forwards sony's actual live response bytes
(`8e6fd06b...`, which is identical to what i was replaying anyway, the token's
stable) and the vita STILL rejects it. so it's not the bytes. the only thing
that works is a direct connection to sony. the console is validating the whole
genuine path (the multi-server stun nat detection tied to the matching/session
tcp connections), which you can't fake from a middlebox.

the matching2 module's header parser itself does no token check — it just
copies/byteswaps the header. so there's no simple "patch the check" either.

## so

network side is a dead end on real hw. real options:

- ad-hoc tunneling (sceNetAdhoc stack, no psn — tunnelable like ppsspp does)
- mod the game's own network layer to talk to your own server

## modding notes

game's net layer = SQRNetworkManager (uses sceNpMatching2 directly:
CreateAndJoinRoom / JoinRoom / LocalDataSend / room sync).

world storage is nicely layered:
LevelStorageSource -> LevelStorage -> ChunkStorage (McRegion on disk,
ConsoleSaveFileSplit for the console layout, or in-memory variants). so a pc
could hold the save and feed it to whatever vita is hosting.

a mod would hook both: the net layer (point it at your server) and the storage
layer (load/save the world from the pc). that's the path that could actually
work.
