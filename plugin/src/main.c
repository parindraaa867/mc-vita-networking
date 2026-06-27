/*
 * mcvita_redirect.suprx
 * ---------------------------------------------------------------------------
 * taiHEN plugin for Minecraft: PS Vita Edition (Enhanced)  [NPWR06859_00]
 *
 * MILESTONE 1 goal: redirect the NP Matching2 server hostnames to YOUR PC so
 * the game's matchmaking traffic lands on a server you control, instead of
 * Sony's. I do this by hooking the DNS resolver (sceNetResolverStartNtoa):
 * when the game asks to resolve one of the matching servers, I answer with
 * the PC's IP.
 *
 * Why this works (the key idea): this code runs *inside* the game process, so
 * everything the game encrypts/signs is still done by the game with its own
 * keys. I am not breaking crypto — I am just changing *where* the already-
 * formed packets are sent. The PC then speaks the matching2 wire protocol I
 * captured (the 1301/1002 frames).
 *
 * This is the Killzone-Mercenary-style "redirect" strategy (Strategy A).
 *
 * Build with vitasdk (see ../CMakeLists.txt). Drop the .suprx in ur_default
 * config under the Minecraft titleid so taiHEN loads it into the game.
 * ---------------------------------------------------------------------------
 */

#include <vitasdk.h>
#include <taihen.h>

#define MAX_HOOKS 4

/* --- tiny libc-free helpers (plugin is built -nostdlib) --- */
static unsigned my_strlen(const char *s)
{
    unsigned n = 0;
    while (s && s[n]) n++;
    return n;
}

static int my_strstr(const char *hay, const char *needle)
{
    if (!hay || !needle) return 0;
    for (const char *h = hay; *h; h++) {
        const char *a = h, *b = needle;
        while (*a && *b && *a == *b) { a++; b++; }
        if (!*b) return 1; /* found */
    }
    return 0;
}

/* Append src to dst at *pos (bounded by cap), advancing *pos. */
static void append(char *dst, unsigned *pos, unsigned cap, const char *src)
{
    while (src && *src && *pos < cap - 1) dst[(*pos)++] = *src++;
    dst[*pos] = 0;
}

/* Parse "a.b.c.d" into a 32-bit network-byte-order address, with NO net import
 * (so the plugin has zero SceNet dependencies and always loads). */
static unsigned ip_to_netaddr(const char *ip)
{
    unsigned bytes[4] = {0, 0, 0, 0};
    int idx = 0, val = 0, have = 0;
    for (const char *c = ip; ; c++) {
        if (*c >= '0' && *c <= '9') {
            val = val * 10 + (*c - '0');
            have = 1;
        } else {
            if (have && idx < 4) bytes[idx++] = val & 0xff;
            val = 0; have = 0;
            if (*c == 0) break;
        }
    }
    /* network byte order: first octet in the lowest-address byte */
    return (bytes[0]) | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24);
}

/* ------------------------------------------------------------------------- *
 *  CONFIG: the PC that will run your matching2 server.
 *  Set this to the IP the Vita can reach (your hotspot PC is 192.168.137.1).
 * ------------------------------------------------------------------------- */
static const char *PC_IP = "192.168.137.1";

/* Hostnames to hijack -> redirected to PC_IP. These are the three NP Matching2
 * roles I saw the game resolve in the capture. Substring match keeps it robust
 * against the rotating agent/session numbers (agent-22001, session-22002, ...). */
static const char *REDIRECT_SUBSTR[] = {
    ".np.matching.playstation.net",   /* covers agent- / session- / lookup- */
};
#define N_REDIRECT (sizeof(REDIRECT_SUBSTR) / sizeof(REDIRECT_SUBSTR[0]))

static SceUID g_hooks[MAX_HOOKS];
static tai_hook_ref_t g_ref_resolver;

static void log_line(const char *msg)
{
    /* Simple file log on the memory card so I can see what the game resolved. */
    /* Log to drive ROOTS (no subdir dependency — a fresh SD2Vita may not have
     * ux0:data/). Try ur0: first (always mounted), then ux0:. Also mirror to
     * the kernel debug printf so PrincessLog/USB sees it even with no card. */
    static const char *paths[] = {
        "ur0:mcvita_redirect.log",
        "ux0:mcvita_redirect.log",
    };
    for (unsigned i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        SceUID fd = sceIoOpen(paths[i],
                              SCE_O_WRONLY | SCE_O_CREAT | SCE_O_APPEND, 0777);
        if (fd >= 0) {
            sceIoWrite(fd, msg, my_strlen(msg));
            sceIoWrite(fd, "\n", 1);
            sceIoClose(fd);
        }
    }
    sceClibPrintf("[mcvita] %s\n", msg);
}

static int should_redirect(const char *host)
{
    if (!host) return 0;
    for (unsigned i = 0; i < N_REDIRECT; i++) {
        if (my_strstr(host, REDIRECT_SUBSTR[i]))
            return 1;
    }
    return 0;
}

/*
 * Hooked DNS resolver. Signature mirrors sceNetResolverStartNtoa:
 *   int sceNetResolverStartNtoa(int rid, const char *hostname,
 *                               SceNetInAddr *addr, int timeout,
 *                               int retry, int flags);
 * On a hijacked host I fill *addr with PC_IP and return success, so the game
 * never talks to Sony's DNS for that name.
 */
static int hook_resolverStartNtoa(int rid, const char *hostname,
                                  SceNetInAddr *addr, int timeout,
                                  int retry, int flags)
{
    /*
     * HOT PATH — keep this fast and side-effect-free. NO SD-card file I/O here
     * (that froze the system when called on every lookup). Only the kernel
     * debug printf, which is non-blocking and safe.
     */
    if (should_redirect(hostname)) {
        if (addr) {
            /* Fill SceNetInAddr (s_addr is network byte order), no net import. */
            *(unsigned *)addr = ip_to_netaddr(PC_IP);
        }
        sceClibPrintf("[mcvita][redirect] %s -> %s\n", hostname, PC_IP);
        /* Redirects are RARE (only the matching servers), so one file write
         * here is safe — unlike logging every passthru, which froze the box. */
        {
            char buf[160];
            unsigned p = 0;
            append(buf, &p, sizeof(buf), "[redirect] ");
            append(buf, &p, sizeof(buf), hostname);
            append(buf, &p, sizeof(buf), " -> ");
            append(buf, &p, sizeof(buf), PC_IP);
            log_line(buf);
        }
        return 0; /* success, skip real resolver */
    }

    /* Not a target: pass straight through. No logging on this path. */
    return TAI_CONTINUE(int, g_ref_resolver, rid, hostname, addr,
                        timeout, retry, flags);
}

/*
 * Worker thread: wait for the SceNet module to actually be loaded in this
 * process (the game loads networking lazily, when you go online), then hook
 * SceNet's EXPORT of sceNetResolverStartNtoa. Hooking the export catches every
 * caller regardless of which sub-module calls it — unlike hooking the main
 * module's import table, which only works if the eboot imports it directly.
 */
static int hook_worker(SceSize args, void *argp)
{
    (void)args; (void)argp;

    /* Poll for up to ~60s for SceNet to appear, then hook its export. */
    for (int attempt = 0; attempt < 240; attempt++) {
        g_hooks[0] = taiHookFunctionExport(
            &g_ref_resolver,
            "SceNet",       /* module name in this process */
            0x6BF8B2A2,     /* SceNet library NID */
            0x1EB11857,     /* sceNetResolverStartNtoa */
            hook_resolverStartNtoa);

        if (g_hooks[0] >= 0) {
            log_line("[ok] export hook installed");
            return 0;
        }
        sceKernelDelayThread(250 * 1000); /* 250 ms */
    }

    log_line("[error] SceNet never appeared / export hook failed");
    return 0;
}

int module_start(SceSize argc, const void *args)
{
    (void)argc; (void)args;
    for (int i = 0; i < MAX_HOOKS; i++) g_hooks[i] = -1;

    log_line("=== mcvita_redirect loaded ===");

    /* Don't hook here (SceNet may not be loaded yet). Spawn a thread that waits
     * for SceNet, then hooks its export. */
    SceUID thid = sceKernelCreateThread("mcvita_hook", hook_worker,
                                        0x10000100, 0x4000, 0, 0, NULL);
    if (thid >= 0)
        sceKernelStartThread(thid, 0, NULL);
    else
        log_line("[error] could not start hook worker thread");

    return SCE_KERNEL_START_SUCCESS;
}

int module_stop(SceSize argc, const void *args)
{
    (void)argc; (void)args;
    for (int i = 0; i < MAX_HOOKS; i++)
        if (g_hooks[i] >= 0) taiHookRelease(g_hooks[i], g_ref_resolver);
    log_line("=== mcvita_redirect unloaded ===");
    return SCE_KERNEL_STOP_SUCCESS;
}
