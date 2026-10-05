// OpenZone: more radio frequencies, server side -- the native Linux server.
//
// The Windows server gets a proxy hid.dll (../src): the executable imports that
// library, so a file with its name beside the executable is loaded first. The
// Linux server is an ELF executable with no such import to stand in for, so the
// same replacement is delivered the way Linux offers one: a shared object named
// in LD_PRELOAD, whose constructor runs before the server's main().
//
//     LD_PRELOAD=/path/to/oz_frequencies.so ./DayZServer -config=serverDZ.cfg -profiles=profiles
//
// What it replaces is the same thing: the engine's lookup from a tuned index to
// a frequency, `table[index & 7]` over eight hardcoded floats, with
// `base + index * step`. See ../../docs/engine-frequency-table.md.
//
// HOW THE LOOKUP IS FOUND, and why not the way the DLL does it. The DLL matches
// eighteen exact bytes, because every Windows build compiles the lookup the
// same way. The Linux build comes from a different compiler, and nobody here
// had its bytes when this was written. So this starts from what cannot differ
// -- the eight frequencies themselves, as data -- finds the instruction that
// refers to that table, and accepts it only next to its two neighbours: the
// mask of an argument with 7, and the return. Whatever it finds or fails to
// find, it writes the bytes it looked at into the log, so that a refusal on a
// real server is a report that can be acted on, not a shrug.
//
// HOW IT IS REPLACED, and why not with the DLL's twelve bytes either. A
// compiler that sees a three-instruction leaf knows exactly which registers it
// touches, and may keep its own values in all the others across the call (GCC
// does at -O2: -fipa-ra). A replacement written in C clobbers whatever the
// calling convention lets it, and `mov rax, imm64; jmp rax` clobbers rax before
// it even gets there -- measured on the stand-in server, where it turned every
// frequency into 0.000 without crashing anything. So the site gets a five-byte
// relative jump, which touches no register, to a relay page mapped within its
// reach; the relay jumps through an absolute address to an assembly stub; and
// the stub saves every register a caller could be relying on, calls the C
// function, and restores them. Only xmm0, the result, comes back changed.
//
// Everything else is the DLL's behaviour on purpose: the same grid file, looked
// for in the server's profile first and beside this library second; the same
// defaults; the same log lines, in oz_frequencies.log beside this library.

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <link.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#ifndef MAP_FIXED_NOREPLACE
#define MAP_FIXED_NOREPLACE 0x100000
#endif

// ---------------------------------------------------------------- configuration

struct Config
{
    double base;    // MHz of index 0
    double step;    // MHz between neighbouring indices
    int    count;   // how many channels exist; indices wrap within this
};

// The same three numbers as the DLL (../src/dllmain.cpp), the mod's built-in
// profiles (OZR_Profiles.LoadDefaults) and native/oz_frequencies.json: one band
// for every radio, 136.000..155.950 MHz in steps of 0.050, 400 channels. Four
// copies of one default now; change them together.
static struct Config g_config = { 136.0, 0.05, 400 };

static char g_dir[PATH_MAX]      = "";   // where this library lives
static char g_profiles[PATH_MAX] = "";   // the server's -profiles directory, absolute
static char g_exe[PATH_MAX]      = "";   // bare name of the process we are in
static int  g_looksLikeServer    = 0;    // its command line carries -config= or -profiles=

// The eight vanilla frequencies, byte for byte what the engine carries.
static const float kVanilla[8] = {
    87.8f, 89.5f, 91.3f, 91.9f, 94.6f, 96.6f, 99.7f, 102.5f
};

// ------------------------------------------------------------------- the log

// Written beside the library. A mod that quietly does nothing is the worst
// outcome here -- every path through this file ends in a line saying what
// happened.
static void Log(const char* fmt, ...)
{
    char path[PATH_MAX + 32];
    snprintf(path, sizeof(path), "%s/oz_frequencies.log", g_dir[0] ? g_dir : ".");

    int fd = open(path, O_WRONLY | O_APPEND | O_CREAT, 0644);
    if (fd < 0)
        return;

    time_t now = time(NULL);
    struct tm tm;
    localtime_r(&now, &tm);

    char line[2048];
    int n = snprintf(line, sizeof(line), "%02d:%02d:%02d  ", tm.tm_hour, tm.tm_min, tm.tm_sec);

    va_list args;
    va_start(args, fmt);
    int m = vsnprintf(line + n, sizeof(line) - (size_t)n - 1, fmt, args);
    va_end(args);

    if (m < 0)
        m = 0;
    n += m;
    if (n > (int)sizeof(line) - 2)
        n = (int)sizeof(line) - 2;
    line[n++] = '\n';

    ssize_t ignored = write(fd, line, (size_t)n);
    (void)ignored;
    close(fd);
}

// -------------------------------------------------------------- config reading

// The same reader as the DLL's: find "key", skip to the colon, parse a number.
// Anything it cannot find keeps its default, and says so in the log.
static int ReadNumber(const char* text, const char* key, double* out)
{
    char quoted[64];
    snprintf(quoted, sizeof(quoted), "\"%s\"", key);

    const char* at = strstr(text, quoted);
    if (!at)
        return 0;

    const char* colon = strchr(at + strlen(quoted), ':');
    if (!colon)
        return 0;

    char* end = NULL;
    double v = strtod(colon + 1, &end);
    if (end == colon + 1)
        return 0;

    *out = v;
    return 1;
}

static int ReadWholeFile(const char* path, char* out, size_t cap)
{
    int fd = open(path, O_RDONLY);
    if (fd < 0)
        return 0;

    size_t got = 0;
    for (;;)
    {
        ssize_t n = read(fd, out + got, cap - 1 - got);
        if (n < 0)
        {
            Log("%s could not be read (%s)", path, strerror(errno));
            close(fd);
            return 0;
        }
        if (n == 0)
            break;
        got += (size_t)n;
        if (got >= cap - 1)
            break;
    }
    close(fd);
    out[got] = '\0';
    return 1;
}

// Our own arguments, as the kernel keeps them: NUL-separated in
// /proc/self/cmdline. Picks out -profiles= and notes whether this process was
// started the way a server is.
static void ReadCommandLine(void)
{
    static char raw[65536];
    int fd = open("/proc/self/cmdline", O_RDONLY);
    if (fd < 0)
        return;
    ssize_t n = read(fd, raw, sizeof(raw) - 1);
    close(fd);
    if (n <= 0)
        return;
    raw[n] = '\0';

    for (ssize_t i = 0; i < n; i += (ssize_t)strlen(raw + i) + 1)
    {
        const char* arg = raw + i;
        if (strncmp(arg, "-config=", 8) == 0 || strncmp(arg, "-profiles=", 10) == 0)
            g_looksLikeServer = 1;
        if (strncmp(arg, "-profiles=", 10) != 0)
            continue;

        const char* value = arg + 10;
        size_t len = strlen(value);
        while (len > 0 && value[len - 1] == '/')
            len--;
        if (len == 0 || len >= PATH_MAX)
            continue;

        // Relative to the WORKING directory -- where the server was launched
        // from, not where this library happens to live.
        if (value[0] == '/')
        {
            memcpy(g_profiles, value, len);
            g_profiles[len] = '\0';
        }
        else
        {
            char cwd[PATH_MAX];
            if (!getcwd(cwd, sizeof(cwd)))
                continue;
            size_t at = strlen(cwd);
            if (at + 1 + len >= PATH_MAX)
                continue;
            memcpy(g_profiles, cwd, at);
            g_profiles[at] = '/';
            memcpy(g_profiles + at + 1, value, len);
            g_profiles[at + 1 + len] = '\0';
        }
    }
}

static void FindExeName(void)
{
    char full[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", full, sizeof(full) - 1);
    if (n <= 0)
        return;
    full[n] = '\0';

    const char* name = strrchr(full, '/');
    name = name ? name + 1 : full;
    snprintf(g_exe, sizeof(g_exe), "%s", name);
}

static void LoadConfig(void)
{
    static char text[4096];
    char path[PATH_MAX + 64];
    int got = 0;

    // The admin-editable copy WINS, exactly as for the DLL: it sits beside the
    // rest of the mod's configs, where the mod itself can write it.
    if (g_profiles[0])
    {
        snprintf(path, sizeof(path), "%s/OpenZone/OZ_Radio_Frequencies.json", g_profiles);
        got = ReadWholeFile(path, text, sizeof(text));
        if (got)
            Log("grid read from the profile: %s", path);
    }

    if (!got)
    {
        snprintf(path, sizeof(path), "%s/oz_frequencies.json", g_dir[0] ? g_dir : ".");
        got = ReadWholeFile(path, text, sizeof(text));
        if (got)
            Log("grid read from beside the library: %s", path);
    }

    if (!got)
    {
        Log("no grid file in the profile or beside the library; using defaults "
            "base=%.3f step=%.3f count=%d", g_config.base, g_config.step, g_config.count);
        return;
    }

    double count = g_config.count;
    if (!ReadNumber(text, "base_mhz", &g_config.base))
        Log("oz_frequencies.json has no base_mhz; keeping %.3f", g_config.base);
    if (!ReadNumber(text, "step_mhz", &g_config.step))
        Log("oz_frequencies.json has no step_mhz; keeping %.3f", g_config.step);
    if (ReadNumber(text, "count", &count))
        g_config.count = (int)count;
    else
        Log("oz_frequencies.json has no count; keeping %d", g_config.count);

    if (g_config.count < 1)
    {
        Log("count=%d is not usable; forcing 1", g_config.count);
        g_config.count = 1;
    }
    if (g_config.step == 0.0)
    {
        Log("step_mhz=0 would make every channel identical; forcing 0.2");
        g_config.step = 0.2;
    }
}

// ------------------------------------------------------------ the replacement

// What the stubs below call. Indices wrap rather than clamp, as in the DLL:
// the engine's own "next channel" is a bare increment.
__attribute__((visibility("hidden"), used, noinline))
float oz_frequency_c(int index)
{
    const int n = g_config.count;
    int i = index % n;
    if (i < 0)
        i += n;
    return (float)(g_config.base + i * g_config.step);
}

// The entry stubs. Control arrives here straight from the middle of the
// engine's lookup, with every register exactly as its caller left it, so
// everything a System V callee may clobber is saved around the call into C:
// the flags, the nine caller-saved general registers, and xmm1..xmm15. (The C
// side uses legacy SSE only, which leaves the upper halves of the ymm
// registers alone.) xmm0 carries the result back.
//
// Ten pushes are 80 bytes; the lookup is entered by a `call`, so rsp is 8 past
// a 16-byte boundary there, and 8 + 80 + 248 lands on one again for the call.
//
// Two of them, because the index is in a different register depending on how
// the engine declares the lookup: the second argument (esi) of a member
// function, or the first (edi) of a free one.
__asm__(
    ".text\n"
    ".macro OZ_STUB name, take_index\n"
    "    .p2align 4\n"
    "    .type \\name, @function\n"
    "\\name:\n"
    "    pushfq\n"
    "    push %rax\n"
    "    push %rcx\n"
    "    push %rdx\n"
    "    push %rsi\n"
    "    push %rdi\n"
    "    push %r8\n"
    "    push %r9\n"
    "    push %r10\n"
    "    push %r11\n"
    "    sub $248, %rsp\n"
    "    movdqu %xmm1,    0(%rsp)\n"
    "    movdqu %xmm2,   16(%rsp)\n"
    "    movdqu %xmm3,   32(%rsp)\n"
    "    movdqu %xmm4,   48(%rsp)\n"
    "    movdqu %xmm5,   64(%rsp)\n"
    "    movdqu %xmm6,   80(%rsp)\n"
    "    movdqu %xmm7,   96(%rsp)\n"
    "    movdqu %xmm8,  112(%rsp)\n"
    "    movdqu %xmm9,  128(%rsp)\n"
    "    movdqu %xmm10, 144(%rsp)\n"
    "    movdqu %xmm11, 160(%rsp)\n"
    "    movdqu %xmm12, 176(%rsp)\n"
    "    movdqu %xmm13, 192(%rsp)\n"
    "    movdqu %xmm14, 208(%rsp)\n"
    "    movdqu %xmm15, 224(%rsp)\n"
    "    \\take_index\n"
    "    call oz_frequency_c\n"
    "    movdqu   0(%rsp), %xmm1\n"
    "    movdqu  16(%rsp), %xmm2\n"
    "    movdqu  32(%rsp), %xmm3\n"
    "    movdqu  48(%rsp), %xmm4\n"
    "    movdqu  64(%rsp), %xmm5\n"
    "    movdqu  80(%rsp), %xmm6\n"
    "    movdqu  96(%rsp), %xmm7\n"
    "    movdqu 112(%rsp), %xmm8\n"
    "    movdqu 128(%rsp), %xmm9\n"
    "    movdqu 144(%rsp), %xmm10\n"
    "    movdqu 160(%rsp), %xmm11\n"
    "    movdqu 176(%rsp), %xmm12\n"
    "    movdqu 192(%rsp), %xmm13\n"
    "    movdqu 208(%rsp), %xmm14\n"
    "    movdqu 224(%rsp), %xmm15\n"
    "    add $248, %rsp\n"
    "    pop %r11\n"
    "    pop %r10\n"
    "    pop %r9\n"
    "    pop %r8\n"
    "    pop %rdi\n"
    "    pop %rsi\n"
    "    pop %rdx\n"
    "    pop %rcx\n"
    "    pop %rax\n"
    "    popfq\n"
    "    ret\n"
    "    .size \\name, . - \\name\n"
    ".endm\n"
    "OZ_STUB oz_stub_member, \"mov %esi, %edi\"\n"
    "OZ_STUB oz_stub_free, \"nop\"\n"
);

extern void oz_stub_member(void) __attribute__((visibility("hidden")));
extern void oz_stub_free(void) __attribute__((visibility("hidden")));

// ---------------------------------------------------------- the executable map

#define MAX_SEGS 32

struct Seg
{
    unsigned char* start;
    size_t         size;    // the file-backed part; the rest is bss and never code
    int            exec;
};

static struct Seg     g_segs[MAX_SEGS];
static int            g_nsegs = 0;
static unsigned char* g_base  = NULL;   // load bias of the main executable

// dl_iterate_phdr reports the main program first, with an empty name. The same
// walk finds this library's own path -- the object one of whose segments holds
// an address of ours -- which is how the log and the grid file get their place
// without dladdr(), whose symbol version would tie the build to a new glibc.
static int OnObject(struct dl_phdr_info* info, size_t size, void* data)
{
    (void)size;
    int* index = (int*)data;
    const uintptr_t mine = (uintptr_t)&g_config;

    for (int i = 0; i < info->dlpi_phnum; i++)
    {
        const ElfW(Phdr)* ph = &info->dlpi_phdr[i];
        if (ph->p_type != PT_LOAD)
            continue;

        uintptr_t start = (uintptr_t)info->dlpi_addr + ph->p_vaddr;
        if (*index == 0 && g_nsegs < MAX_SEGS)
        {
            g_base = (unsigned char*)info->dlpi_addr;
            g_segs[g_nsegs].start = (unsigned char*)start;
            g_segs[g_nsegs].size  = ph->p_filesz < ph->p_memsz ? ph->p_filesz : ph->p_memsz;
            g_segs[g_nsegs].exec  = (ph->p_flags & PF_X) != 0;
            g_nsegs++;
        }
        if (mine >= start && mine < start + ph->p_memsz && info->dlpi_name && info->dlpi_name[0])
        {
            char resolved[PATH_MAX];
            if (realpath(info->dlpi_name, resolved))
            {
                char* slash = strrchr(resolved, '/');
                if (slash)
                {
                    *slash = '\0';
                    snprintf(g_dir, sizeof(g_dir), "%s", resolved);
                }
            }
        }
    }
    (*index)++;
    return 0;
}

// The executable segment holding `p`, or NULL.
static const struct Seg* ExecSeg(const unsigned char* p)
{
    for (int i = 0; i < g_nsegs; i++)
    {
        if (g_segs[i].exec && p >= g_segs[i].start && p < g_segs[i].start + g_segs[i].size)
            return &g_segs[i];
    }
    return NULL;
}

// ------------------------------------------------------------ finding the code

#define MAX_TABLES 4
#define MAX_REFS   16

static void Hex(const unsigned char* p, size_t n, char* out, size_t cap)
{
    size_t at = 0;
    if (cap > 0)
        out[0] = '\0';
    for (size_t i = 0; i < n && at + 4 < cap; i++)
        at += (size_t)snprintf(out + at, cap - at, "%02X ", p[i]);
    if (at > 0)
        out[at - 1] = '\0';
}

struct Found
{
    unsigned char* site;      // where the jump goes: the first of the lookup's instructions we own
    unsigned char* ret;       // the lookup's `ret`
    unsigned char* table;
    int            argIndex;  // 2: the index is in esi; 1: in edi
};

// Is `ref` -- four bytes of code that address the table -- part of the lookup?
// The lookup is three things in a row, in either order of the first two: an
// `and` of a register with 7, the instruction that addresses the table, and a
// `ret`. Nothing here assumes where the function starts or how it is aligned.
static int MatchAt(unsigned char* ref, struct Found* out)
{
    const struct Seg* seg = ExecSeg(ref);
    if (!seg)
        return 0;
    unsigned char* lo  = seg->start;
    unsigned char* end = seg->start + seg->size;

    // The instruction that addresses the table.
    unsigned char* ri;
    if (ref - lo >= 3 && (ref[-3] & 0xFB) == 0x48 && ref[-2] == 0x8D && (ref[-1] & 0xC7) == 0x05)
        ri = ref - 3;   // lea r64, [rip + table]; a movss through that register follows
    else if (ref - lo >= 5 && ref[-5] == 0xF3 && ref[-4] == 0x0F && ref[-3] == 0x10
             && ref[-2] == 0x04 && (ref[-1] & 0xC7) == 0x85)
        ri = ref - 5;   // movss xmm0, [index * 4 + table], in an executable at a fixed base
    else
        return 0;

    // The return: right after, or after one more short instruction.
    unsigned char* ret = NULL;
    for (unsigned char* p = ref + 4; p < end && p < ref + 4 + 12; p++)
    {
        if (*p == 0xC3)
        {
            ret = p;
            break;
        }
    }
    if (!ret)
        return 0;

    // `and r32, 7` is 83 /4 ib: 83, a ModRM of E0..E7, 07. It is the table
    // instruction's neighbour: before it, with at most a register copy between,
    // or right behind it.
    unsigned char* from = ri - lo >= 8 ? ri - 8 : lo;
    unsigned char* mask = NULL;
    for (unsigned char* p = from; p + 2 < ret; p++)
    {
        if (p[0] == 0x83 && (p[1] & 0xF8) == 0xE0 && p[2] == 0x07)
        {
            mask = p;
            break;
        }
    }
    if (!mask)
        return 0;
    if (mask < ri && ri - (mask + 3) > 3)
        return 0;
    if (mask > ri && (mask < ref + 4 || mask - (ref + 4) > 3))
        return 0;

    // Which argument is being masked: esi or edi directly, or a copy of one of
    // them made just before (mov in either encoding, or movsxd).
    int reg = mask[1] & 7;
    int arg = reg == 6 ? 2 : (reg == 7 ? 1 : 0);
    for (unsigned char* p = from; !arg && p + 1 < mask; p++)
    {
        unsigned char op = p[0], modrm = p[1];
        if ((modrm & 0xC0) != 0xC0)
            continue;
        int r = (modrm >> 3) & 7, rm = modrm & 7;
        if (op == 0x89 && rm == reg)
            arg = r == 6 ? 2 : (r == 7 ? 1 : 0);
        else if ((op == 0x8B || op == 0x63) && r == reg)
            arg = rm == 6 ? 2 : (rm == 7 ? 1 : 0);
    }
    if (!arg)
        return 0;

    unsigned char* site = mask < ri ? mask : ri;
    if (ret + 1 - site < 5)
        return 0;

    out->site = site;
    out->ret = ret;
    out->argIndex = arg;
    return 1;
}

// Returns 1 with *out filled, or 0 with `why` saying what was seen instead.
static int FindLookup(struct Found* out, char* why, size_t whyLen)
{
    unsigned char* tables[MAX_TABLES];
    int ntables = 0;

    for (int s = 0; s < g_nsegs && ntables < MAX_TABLES; s++)
    {
        unsigned char* at = g_segs[s].start;
        size_t left = g_segs[s].size;
        while (left >= sizeof(kVanilla) && ntables < MAX_TABLES)
        {
            unsigned char* hit = memmem(at, left, kVanilla, sizeof(kVanilla));
            if (!hit)
                break;
            tables[ntables++] = hit;
            left -= (size_t)(hit + 1 - at);
            at = hit + 1;
        }
    }

    if (g_nsegs == 0)
    {
        snprintf(why, whyLen, "the executable's segments could not be listed");
        return 0;
    }
    if (ntables == 0)
    {
        snprintf(why, whyLen,
                 "the eight vanilla frequencies are not in the executable (%d segment(s) searched) "
                 "-- the game changed its table, and this build finds the lookup through it; "
                 "nothing was patched", g_nsegs);
        return 0;
    }

    // Every place in the code whose four bytes land on a table: as a
    // displacement from the next instruction in a position-independent
    // executable, or as the bare address in one linked at a fixed base.
    struct Found found[MAX_REFS];
    int nfound = 0;
    int nrefs = 0;

    for (int s = 0; s < g_nsegs; s++)
    {
        if (!g_segs[s].exec || g_segs[s].size < 8)
            continue;
        unsigned char* lo = g_segs[s].start;
        unsigned char* end = lo + g_segs[s].size;
        for (unsigned char* p = lo; p + 4 <= end; p++)
        {
            int32_t rel;
            memcpy(&rel, p, 4);
            unsigned char* target = p + 4 + rel;
            unsigned char* table = NULL;
            for (int t = 0; t < ntables && !table; t++)
            {
                int absolute = (uintptr_t)tables[t] <= 0x7FFFFFFFu
                            && (uint32_t)rel == (uint32_t)(uintptr_t)tables[t];
                if (target == tables[t] || absolute)
                    table = tables[t];
            }
            if (!table)
                continue;

            nrefs++;
            if (nrefs > MAX_REFS)
                continue;

            // Sixteen bytes before and twenty after: enough to read the
            // lookup off the log whatever shape it has.
            unsigned char* a = p - lo >= 16 ? p - 16 : lo;
            unsigned char* b = end - p >= 20 ? p + 20 : end;
            char hex[40 * 3 + 4];
            Hex(a, (size_t)(b - a), hex, sizeof(hex));
            Log("reference %d: code at +0x%llX addresses the table at +0x%llX; bytes from +0x%llX: %s",
                nrefs, (unsigned long long)(p - g_base), (unsigned long long)(table - g_base),
                (unsigned long long)(a - g_base), hex);

            struct Found one;
            if (!MatchAt(p, &one))
                continue;
            one.table = table;

            int repeat = 0;
            for (int k = 0; k < nfound; k++)
                repeat |= (found[k].site == one.site);
            if (!repeat)
                found[nfound++] = one;
        }
    }

    if (nrefs == 0)
    {
        snprintf(why, whyLen,
                 "the vanilla table is at +0x%llX but no code addresses it; nothing was patched",
                 (unsigned long long)(tables[0] - g_base));
        return 0;
    }
    if (nfound == 0)
    {
        snprintf(why, whyLen,
                 "%d reference(s) to the vanilla table, none of them beside a mask with 7 and a "
                 "return -- this build compiles the lookup differently (inlined into its "
                 "callers, most likely); the bytes are in the lines above, nothing was patched",
                 nrefs);
        return 0;
    }
    if (nfound > 1)
    {
        // Ambiguity is a refusal, not a coin flip, exactly as in the DLL.
        snprintf(why, whyLen,
                 "%d places look like the frequency lookup (the first two at +0x%llX and "
                 "+0x%llX); refusing to guess", nfound,
                 (unsigned long long)(found[0].site - g_base),
                 (unsigned long long)(found[1].site - g_base));
        return 0;
    }

    *out = found[0];
    snprintf(why, whyLen,
             "lookup at +0x%llX (%d bytes to its return, index in %s), table at +0x%llX, "
             "table is the known vanilla eight",
             (unsigned long long)(out->site - g_base), (int)(out->ret + 1 - out->site),
             out->argIndex == 2 ? "esi, the second argument" : "edi, the first argument",
             (unsigned long long)(out->table - g_base));
    return 1;
}

// ------------------------------------------------------------------ the patch

#define JUMP_LEN  5    // E9 rel32

// A page within a relative jump's reach of `site`, to hold the relay. Tried at
// 64 KiB steps outward from the site, below and above; MAP_FIXED_NOREPLACE asks
// for exactly that address or nothing, and a kernel too old to know the flag
// treats the address as a hint, which the comparison below catches.
static unsigned char* MapNear(const unsigned char* site, size_t page)
{
    const uintptr_t reach = 0x70000000u;
    const uintptr_t step = 0x10000u;
    const uintptr_t origin = (uintptr_t)site & ~(uintptr_t)(step - 1);

    for (uintptr_t delta = step; delta < reach; delta += step)
    {
        for (int up = 0; up < 2; up++)
        {
            if (!up && origin < delta + step)
                continue;
            uintptr_t want = up ? origin + delta : origin - delta;
            void* got = mmap((void*)want, page, PROT_READ | PROT_WRITE,
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
            if (got == MAP_FAILED)
                continue;
            if ((uintptr_t)got == want)
                return (unsigned char*)got;
            munmap(got, page);
        }
    }
    return NULL;
}

static int Redirect(unsigned char* site, void* stub, char* why, size_t whyLen)
{
    const size_t page = (size_t)sysconf(_SC_PAGESIZE);

    unsigned char* relay = MapNear(site, page);
    if (!relay)
    {
        snprintf(why, whyLen, "no free page within 2 GiB of the lookup for the relay; nothing was patched");
        return 0;
    }

    // jmp [rip + 0], then the address it reads: fourteen bytes, no register.
    static const unsigned char jmpIndirect[6] = { 0xFF, 0x25, 0x00, 0x00, 0x00, 0x00 };
    memcpy(relay, jmpIndirect, sizeof(jmpIndirect));
    memcpy(relay + sizeof(jmpIndirect), &stub, sizeof(void*));
    if (mprotect(relay, page, PROT_READ | PROT_EXEC) != 0)
    {
        snprintf(why, whyLen, "mprotect(read+exec) on the relay failed: %s; nothing was patched",
                 strerror(errno));
        munmap(relay, page);
        return 0;
    }

    unsigned char jump[JUMP_LEN];
    int32_t rel = (int32_t)(relay - (site + JUMP_LEN));
    jump[0] = 0xE9;
    memcpy(jump + 1, &rel, 4);

    uintptr_t from = (uintptr_t)site & ~(uintptr_t)(page - 1);
    uintptr_t to = ((uintptr_t)site + JUMP_LEN + page - 1) & ~(uintptr_t)(page - 1);

    // Writable, then executable again -- never both at once, so this also works
    // where a policy forbids pages that are writable and executable together.
    // Nothing else runs yet: this is a constructor, before the server's main().
    if (mprotect((void*)from, to - from, PROT_READ | PROT_WRITE) != 0)
    {
        snprintf(why, whyLen, "mprotect(read+write) on the lookup failed: %s; nothing was patched",
                 strerror(errno));
        munmap(relay, page);
        return 0;
    }

    memcpy(site, jump, JUMP_LEN);

    if (mprotect((void*)from, to - from, PROT_READ | PROT_EXEC) != 0)
    {
        snprintf(why, whyLen,
                 "mprotect(read+exec) failed AFTER the bytes were written: %s -- the server "
                 "will crash on its first frequency lookup", strerror(errno));
        return 0;
    }
    __builtin___clear_cache((char*)site, (char*)site + JUMP_LEN);

    snprintf(why, whyLen, "redirected %d bytes through a relay at %p", JUMP_LEN, (void*)relay);
    return 1;
}

// ------------------------------------------------------------------- start-up

// LD_PRELOAD reaches every process started with it in the environment -- the
// shell that launches the server, steamcmd, whatever a wrapper script runs --
// so the gate is the executable's name. Those other processes are expected and
// stay silent. A process that was started LIKE a server (it carries -config= or
// -profiles=) under another name is the one case worth a line: that is what a
// renamed or wrapped server looks like, and silence there would hide it.
static int IsServer(void)
{
    return strncmp(g_exe, "DayZServer", 10) == 0;
}

__attribute__((constructor))
static void Start(void)
{
    int index = 0;
    dl_iterate_phdr(OnObject, &index);

    ReadCommandLine();
    FindExeName();

    if (!IsServer())
    {
        if (g_looksLikeServer)
        {
            Log("----");
            Log("NOT PATCHED: loaded into \"%s\", which is not DayZServer, though its command "
                "line looks like a server's. If this IS the server, name the executable "
                "DayZServer.", g_exe);
        }
        return;
    }

    Log("----");
    LoadConfig();

    struct Found found;
    char why[768] = "";

    if (!FindLookup(&found, why, sizeof(why)))
    {
        Log("NOT PATCHED: %s", why);
        return;
    }
    Log("found: %s", why);

    void* stub = found.argIndex == 2 ? (void*)&oz_stub_member : (void*)&oz_stub_free;
    if (!Redirect(found.site, stub, why, sizeof(why)))
    {
        Log("NOT PATCHED: %s", why);
        return;
    }

    Log("patched: %s", why);
    Log("channels: %d, from %.3f MHz in steps of %.4f MHz (index 0 = %.3f, index %d = %.3f)",
        g_config.count, g_config.base, g_config.step,
        g_config.base, g_config.count - 1,
        g_config.base + (g_config.count - 1) * g_config.step);
}
