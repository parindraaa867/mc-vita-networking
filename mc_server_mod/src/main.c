/*
 * mcserver_mod.suprx  —  Minecraft: PS Vita Edition custom-server mod (foundation)
 * ---------------------------------------------------------------------------
 * Goal of the whole mod: make Minecraft talk to YOUR PC server instead of
 * Sony's matchmaking, and load/save the world from that server, so the PC is a
 * 24/7 coordinator + canonical world store. First Vita to connect hosts; others
 * join through the server.
 *
 * THIS FILE = the foundation:
 *   - loads into Minecraft (titleid PCSE00491) via taiHEN
 *   - opens a TCP connection to the PC server and does a hello handshake
 *   - lays out the two hook seams (network + storage) with clear TODOs
 *
 * What still needs reverse-engineering before the hooks do real work: the
 * in-binary addresses of the game's SQRNetworkManager_Vita methods and the
 * LevelStorageSource path. The leaked source gives the NAMES + behavior; I
 * locate the addresses in the eboot (Ghidra) and fill them into the hooks.
 * Clean-room: understand from source, implement here ourselves.
 *
 * Lessons already learned (baked in):
 *   - target ONLY PCSE00491 in config.txt, never *ALL (froze the system)
 *   - NO blocking SD-card I/O on hot paths; logging stays light
 *   - do network work on a worker thread after the game has started, so I
 *     don't fight module-load ordering
 * ---------------------------------------------------------------------------
 */

#include <vitasdk.h>
#include <taihen.h>

/* ====== CONFIG: your PC server ====== */
#define PC_SERVER_IP   "192.168.1.31"   /* <-- set to your server's IP */
#define PC_SERVER_PORT 25700            /* your custom protocol port */

#define MAX_HOOKS 8
static SceUID g_hooks[MAX_HOOKS];
static tai_hook_ref_t g_ref[MAX_HOOKS];
static int g_sock = -1;

/* ---- tiny helpers (no libc) ---- */
static unsigned slen(const char *s){unsigned n=0;while(s&&s[n])n++;return n;}
static void logln(const char *m){
    SceUID fd=sceIoOpen("ur0:mcserver_mod.log",SCE_O_WRONLY|SCE_O_CREAT|SCE_O_APPEND,0777);
    if(fd>=0){sceIoWrite(fd,m,slen(m));sceIoWrite(fd,"\n",1);sceIoClose(fd);}
    sceClibPrintf("[mcmod] %s\n",m);
}
static unsigned ip2net(const char*ip){
    unsigned b[4]={0,0,0,0};int i=0,v=0,h=0;
    for(const char*c=ip;;c++){
        if(*c>='0'&&*c<='9'){v=v*10+(*c-'0');h=1;}
        else{if(h&&i<4)b[i++]=v&0xff;v=0;h=0;if(!*c)break;}
    }
    return b[0]|(b[1]<<8)|(b[2]<<16)|(b[3]<<24);
}

/* =========================================================================
 *  TRANSPORT: connect to the PC server.
 *  This is the pipe the network + storage hooks will use. For now it just
 *  connects and does a hello so I can confirm the Vita reaches the server.
 * ========================================================================= */
static int connect_to_server(void)
{
    /* Minecraft has already initialized the net library, so I can create a
     * socket directly. (If this ever fails with a not-initialized error, I'd
     * add sceNetCtlInit/sceNetInit guarded by a check.) */
    int s = sceNetSocket("mcmod_sock", SCE_NET_AF_INET, SCE_NET_SOCK_STREAM, 0);
    if (s < 0) { logln("[net] socket() failed"); return -1; }

    SceNetSockaddrIn addr;
    sceClibMemset(&addr, 0, sizeof(addr));
    addr.sin_family = SCE_NET_AF_INET;
    addr.sin_port   = sceNetHtons(PC_SERVER_PORT);
    addr.sin_addr.s_addr = ip2net(PC_SERVER_IP);

    int r = sceNetConnect(s, (SceNetSockaddr*)&addr, sizeof(addr));
    if (r < 0) { logln("[net] connect() failed"); sceNetSocketClose(s); return -1; }

    logln("[net] connected to PC server");
    /* hello handshake: identify ourselves; server replies with role/world info */
    const char *hello = "MCVITA_MOD/0 HELLO\n";
    sceNetSend(s, hello, slen(hello), 0);

    char buf[256];
    int n = sceNetRecv(s, buf, sizeof(buf)-1, 0);
    if (n > 0) { buf[n] = 0; logln("[net] server said:"); logln(buf); }
    g_sock = s;
    return s;
}

/* =========================================================================
 *  HOOK SEAM 1 — NETWORK  (SQRNetworkManager_Vita)
 *  Replace the sceNpMatching2 backend with my direct server connection.
 *  I will hook the game's methods (addresses TBD from Ghidra), e.g.:
 *    SQRNetworkManager_Vita::CreateAndJoinRoom(...)  -> tell server "host"
 *    SQRNetworkManager_Vita::JoinRoom(...)           -> tell server "join"
 *    SQRNetworkManager_Vita::LocalDataSend(...)      -> send game data via g_sock
 *    (+ feed incoming server data back into the game's recv path)
 *  TODO: install taiHookFunctionOffset hooks once addresses are known.
 * ========================================================================= */
static void install_network_hooks(void)
{
    logln("[hook] network seam: pending game-function addresses (see Ghidra step)");
    /* example shape (filled in after RE):
     * g_hooks[0] = taiHookFunctionOffset(&g_ref[0], game_modid,
     *                  segidx, OFFSET_CreateAndJoinRoom, 1, hk_CreateAndJoinRoom);
     */
}

/* =========================================================================
 *  HOOK SEAM 2 — STORAGE  (LevelStorageSource / LevelStorage)
 *  Feed the world from the PC and save it back, instead of local files only.
 *  MVP plan (Option A): when hosting, download the save blob from the server,
 *  write it to the Vita save dir, let the normal storage load it; on auto-save,
 *  upload it back.
 *  TODO: hook the save-list/open path, or simpler — pre-place the downloaded
 *  save files before the game enumerates saves.
 * ========================================================================= */
static void install_storage_hooks(void)
{
    logln("[hook] storage seam: pending save path/format wiring (see source map)");
}

/* ---- worker thread: runs after the game is up ---- */
static int worker(SceSize args, void *argp)
{
    (void)args; (void)argp;
    /* give Minecraft a moment to finish initializing its net library */
    sceKernelDelayThread(8 * 1000 * 1000); /* 8s */
    logln("=== mcserver_mod worker start ===");
    connect_to_server();
    install_network_hooks();
    install_storage_hooks();
    return 0;
}

int module_start(SceSize argc, const void *args)
{
    (void)argc; (void)args;
    for (int i = 0; i < MAX_HOOKS; i++) g_hooks[i] = -1;
    logln("=== mcserver_mod loaded into Minecraft ===");

    SceUID th = sceKernelCreateThread("mcmod_worker", worker,
                                      0x10000100, 0x4000, 0, 0, NULL);
    if (th >= 0) sceKernelStartThread(th, 0, NULL);
    else logln("[err] could not start worker thread");
    return SCE_KERNEL_START_SUCCESS;
}

int module_stop(SceSize argc, const void *args)
{
    (void)argc; (void)args;
    if (g_sock >= 0) sceNetSocketClose(g_sock);
    for (int i = 0; i < MAX_HOOKS; i++)
        if (g_hooks[i] >= 0) taiHookRelease(g_hooks[i], g_ref[i]);
    logln("=== mcserver_mod unloaded ===");
    return SCE_KERNEL_STOP_SUCCESS;
}
