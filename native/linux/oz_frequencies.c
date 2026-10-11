// OpenZone: more radio frequencies, server side -- the native Linux server,
// DayZ 1.30.
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
// a frequency, `table[index % 9]` over nine hardcoded floats on 1.30, with
// `base + index * step`. See ../../docs/engine-frequency-table.md.
//
// HOW THE LOOKUP IS FOUND. This starts from what cannot differ -- the nine
// frequencies themselves, as data -- finds every instruction that refers to
// that table, and accepts one only as part of the shape 1.30 compiles: the
// argument sign-extended, the multiplier 0xE38E38E38E38E38F (one ninth, as a
// 64-bit `mul`), the instruction that addresses the table, a `movss` through
// it, and a `ret`. The jump goes to the function's entry, so every `call` to
// it lands on the grid. Whatever it finds or fails to find, it writes the bytes
// it looked at into the log, so that a refusal on a later build is a report.
//
// What `DayZServer` 1.30.164014 carries (GCC, a fixed-base executable at
// 0x400000; measured 2026-10-11), at +0x9EC850:
//
//     48 63 F6                        movsxd rsi, esi          ; esi = tuned index
//     48 BA 8F E3 38 8E E3 38 8E E3   movabs rdx, 0xE38E38E38E38E38F
//     48 89 F0                        mov    rax, rsi
//     48 F7 E2                        mul    rdx
//     48 C1 EA 03                     shr    rdx, 3
//     48 8D 04 D2                     lea    rax, [rdx + rdx*8]
//     48 29 C6                        sub    rsi, rax          ; index - 9*(index/9)
//     48 8D 05 <rel32>                lea    rax, [rip + table]
//     48 63 D6                        movsxd rdx, esi
//     F3 0F 10 04 90                  movss  xmm0, [rax + rdx*4]
//     C3                              ret
//
// -- forty-six bytes, the index in esi (the second argument of a member
// function). The transmitter initialiser carries the same arithmetic INLINED,
// at +0x9EC8CA, reading the index from the object (`[rbx + 0x18]`) and storing
// the frequency back into it (`[rbx + 0x1C]`), with one instruction of the
// caller's own in the middle (`mov byte [rbx + 0x15], 1`). That copy is matched
// byte for byte and replaced with a call that keeps the caller's instruction,
// so a freshly created transmitter reads the same grid as every later tuning.
// The 1.29 shape (a mask with 7 over eight frequencies) is not here: this
// branch is 1.30's, and the main branch keeps the older one.
//
// HOW IT IS REPLACED. A compiler that sees a leaf knows exactly which registers
// it touches, and may keep its own values in all the others across the call
// (GCC does at -O2: -fipa-ra). A replacement written in C clobbers whatever the
// calling convention lets it, and `mov rax, imm64; jmp rax` clobbers rax before
// it even gets there -- measured on the stand-in server, where it turned every
// frequency into 0.000 without crashing anything. So the entry gets a five-byte
// relative jump, which touches no register, to a relay page mapped within its
// reach; the relay jumps through an absolute address to an assembly stub; and
// the stub saves every register a caller could be relying on, calls the C
// function, and restores them. Only xmm0, the result, comes back changed. The
// inlined copy, which already clobbers rax, rcx and rdx itself, calls the same
// stub through rax.
//
// Everything else is the DLL's behaviour on purpose: the same grid file, looked
// for in the server's profile first and beside this library second; the same
// defaults; the same log lines, in oz_frequencies.log beside this library --
// or on the server's standard error, when that file cannot be written.

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

// The nine vanilla frequencies of 1.30, byte for byte what the engine carries.
static const float kVanilla[9] = {
    80.0f, 87.8f, 89.5f, 91.3f, 91.9f, 94.6f, 96.6f, 99.7f, 102.5f
};

// ------------------------------------------------------------------- the log

// Written beside the library. A mod that quietly does nothing is the worst
// outcome here -- every path through this file ends in a line saying what
// happened.
//
// A library installed where the server's user may not write (/usr/local/lib,
// a read-only mount) has no log file to write to. Its lines then go to the
// server's standard error, which is the console, the journal or the panel --
// the next place an admin looks -- after one line saying why they are there.
static void Log(const char* fmt, ...)
{
    static const char tag[] = "oz_frequencies: ";
    char buf[sizeof(tag) + 2048];
    char* line = buf + sizeof(tag) - 1;
    const size_t cap = sizeof(buf) - (sizeof(tag) - 1);
    memcpy(buf, tag, sizeof(tag) - 1);

    time_t now = time(NULL);
    struct tm tm;
    localtime_r(&now, &tm);

    int n = snprintf(line, cap, "%02d:%02d:%02d  ", tm.tm_hour, tm.tm_min, tm.tm_sec);

    va_list args;
    va_start(args, fmt);
    int m = vsnprintf(line + n, cap - (size_t)n - 1, fmt, args);
    va_end(args);

    if (m < 0)
        m = 0;
    n += m;
    if (n > (int)cap - 2)
        n = (int)cap - 2;
    line[n++] = '\n';

    char path[PATH_MAX + 32];
    snprintf(path, sizeof(path), "%s/oz_frequencies.log", g_dir[0] ? g_dir : ".");

    ssize_t ignored;
    int fd = open(path, O_WRONLY | O_APPEND | O_CREAT, 0644);
    if (fd < 0)
    {
        static int said = 0;
        if (!said)
        {
            said = 1;
            char note[PATH_MAX + 160];
            int k = snprintf(note, sizeof(note), "%scannot write %s (%s); its lines follow here\n",
                             tag, path, strerror(errno));
            ignored = write(STDERR_FILENO, note, (size_t)k);
        }
        ignored = write(STDERR_FILENO, buf, sizeof(tag) - 1 + (size_t)n);
        (void)ignored;
        return;
    }

    ignored = write(fd, line, (size_t)n);
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
static uintptr_t      g_imageEnd = 0;   // one past its highest segment, bss included

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
        if (*index == 0 && start + ph->p_memsz > g_imageEnd)
            g_imageEnd = start + ph->p_memsz;
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

// 0xE38E38E38E38E38F, the multiplier both compilers use for an unsigned 64-bit
// division by nine, as the eight bytes of a `movabs`.
static const unsigned char kMagic[8] = { 0x8F, 0xE3, 0x38, 0x8E, 0xE3, 0x38, 0x8E, 0xE3 };

// The inlined copy in the transmitter initialiser, byte for byte as 1.30.164014
// carries it, the rel32 of the lea wildcarded. rbx is the object, [rbx + 0x18]
// the tuned index; the `mov byte [rbx + 0x15], 1` in the middle is the
// caller's own and is kept when the block is replaced.
static const unsigned char kInlined[] = {
    0x48, 0x63, 0x4B, 0x18,                                     // movsxd rcx, [rbx + 0x18]
    0x48, 0xBA, 0x8F, 0xE3, 0x38, 0x8E, 0xE3, 0x38, 0x8E, 0xE3, // movabs rdx, 1/9
    0xC6, 0x43, 0x15, 0x01,                                     // mov byte [rbx + 0x15], 1
    0x48, 0x89, 0xC8,                                           // mov rax, rcx
    0x48, 0xF7, 0xE2,                                           // mul rdx
    0x48, 0xC1, 0xEA, 0x03,                                     // shr rdx, 3
    0x48, 0x8D, 0x04, 0xD2,                                     // lea rax, [rdx + rdx*8]
    0x48, 0x29, 0xC1,                                           // sub rcx, rax
    0x48, 0x8D, 0x05, 0x00, 0x00, 0x00, 0x00,                   // lea rax, [rip + table]
    0x48, 0x63, 0xC9,                                           // movsxd rcx, ecx
    0xF3, 0x0F, 0x10, 0x04, 0x88,                               // movss xmm0, [rax + rcx*4]
};
#define INLINED_LEN     ((int)sizeof(kInlined))
#define INLINED_REL_AT  38   // the lea's rel32
#define INLINED_REL_END 42   // what that rel32 is relative to
static const unsigned char kInlinedKeep[] = { 0xC6, 0x43, 0x15, 0x01 };  // mov byte [rbx + 0x15], 1
static const unsigned char kInlinedLoad[] = { 0x8B, 0x73, 0x18 };        // mov esi, [rbx + 0x18]

struct Found
{
    unsigned char* site;      // the leaf's entry: where the jump goes
    unsigned char* ret;       // the leaf's `ret`
    unsigned char* table;
    int            argIndex;  // 2: the index is in esi; 1: in edi
    unsigned char* inlineAt;  // the inlined copy that reads the same table, or NULL
};

// The address in [lo, hi] that `call rel32` instructions in the image land
// on -- the most called one when there are several -- or NULL.
static unsigned char* CallTarget(unsigned char* lo, unsigned char* hi)
{
    unsigned char* cand[8];
    int candN[8];
    int nc = 0;
    for (int s = 0; s < g_nsegs; s++)
    {
        if (!g_segs[s].exec || g_segs[s].size < 5)
            continue;
        unsigned char* a = g_segs[s].start;
        unsigned char* end = a + g_segs[s].size;
        for (unsigned char* p = a; p + 5 <= end; p++)
        {
            if (*p != 0xE8)
                continue;
            int32_t rel;
            memcpy(&rel, p + 1, 4);
            unsigned char* t = p + 5 + rel;
            if (t < lo || t > hi)
                continue;
            int k;
            for (k = 0; k < nc && cand[k] != t; k++)
                ;
            if (k == nc)
            {
                if (nc == 8)
                    continue;
                cand[nc] = t;
                candN[nc] = 0;
                nc++;
            }
            candN[k]++;
        }
    }
    unsigned char* best = NULL;
    int bestN = 0;
    for (int k = 0; k < nc; k++)
    {
        if (candN[k] > bestN)
        {
            best = cand[k];
            bestN = candN[k];
        }
    }
    return best;
}

// Is `ref` -- four bytes of code that address the table -- the one inside the
// LEAF? The leaf is: a movsxd of the argument, the multiplier, a mul, the
// instruction that addresses the table, a movss through it, a ret. Nothing
// here assumes alignment; an ENDBR64 in front belongs to the function.
static int MatchLeaf(unsigned char* ref, struct Found* out)
{
    const struct Seg* seg = ExecSeg(ref);
    if (!seg)
        return 0;
    unsigned char* lo  = seg->start;
    unsigned char* end = seg->start + seg->size;

    // The instruction that addresses the table, and the movss that reads it.
    unsigned char* ri;
    unsigned char* movss = NULL;
    if (ref - lo >= 3 && (ref[-3] & 0xFB) == 0x48 && ref[-2] == 0x8D && (ref[-1] & 0xC7) == 0x05)
    {
        ri = ref - 3;   // lea r64, [rip + table]; a movss through that register follows
        for (unsigned char* p = ref + 4; p + 5 <= end && p < ref + 4 + 12; p++)
        {
            if (p[0] == 0xF3 && p[1] == 0x0F && p[2] == 0x10 && p[3] == 0x04)
            {
                movss = p;
                break;
            }
        }
    }
    else if (ref - lo >= 5 && ref[-5] == 0xF3 && ref[-4] == 0x0F && ref[-3] == 0x10
             && ref[-2] == 0x04 && (ref[-1] & 0xC7) == 0x85)
    {
        ri = ref - 5;   // movss xmm0, [index * 4 + table], in an executable at a fixed base
        movss = ri;
    }
    else
        return 0;
    if (!movss)
        return 0;

    // The return: right after the movss, or after one more short instruction.
    unsigned char* after = (movss == ri) ? ref + 4 : movss + 5;
    unsigned char* ret = NULL;
    for (unsigned char* p = after; p < end && p < after + 8; p++)
    {
        if (*p == 0xC3)
        {
            ret = p;
            break;
        }
    }
    if (!ret)
        return 0;

    // The multiplier, loaded by a movabs at most 48 bytes before the table
    // instruction, and a mul between the two.
    unsigned char* magic = NULL;
    for (unsigned char* p = ri - 10; p >= lo && p >= ri - 48; p--)
    {
        if ((p[0] & 0xFE) == 0x48 && (p[1] & 0xF8) == 0xB8 && memcmp(p + 2, kMagic, sizeof(kMagic)) == 0)
        {
            magic = p;
            break;
        }
    }
    if (!magic)
        return 0;
    int mul = 0;
    for (unsigned char* p = magic + 10; p + 2 < ri; p++)
    {
        if ((p[0] & 0xFE) == 0x48 && p[1] == 0xF7 && (p[2] & 0xF8) == 0xE0)
            mul = 1;
    }
    if (!mul)
        return 0;

    // The argument: a movsxd of esi or edi between the function's start and
    // the table instruction, in whichever order the compiler put it and the
    // multiplier (GCC 7 sign-extends first, GCC 13 loads the multiplier first).
    unsigned char* movsxd = NULL;
    int arg = 0;
    for (unsigned char* p = magic - 16 >= lo ? magic - 16 : lo; p + 2 < ri && !movsxd; p++)
    {
        if (p[0] == 0x48 && p[1] == 0x63 && (p[2] & 0xC0) == 0xC0)
        {
            int rm = p[2] & 7;
            if (rm == 6 || rm == 7)
            {
                movsxd = p;
                arg = rm == 6 ? 2 : 1;
            }
        }
    }
    if (!movsxd)
        return 0;
    unsigned char* first = movsxd < magic ? movsxd : magic;

    // The entry: where the callers land. A `call rel32` whose target sits in
    // the few bytes before the first instruction recognised names it exactly
    // -- the compiler may have put a register copy or an ENDBR64 there, and a
    // jump written anywhere later would let those instructions run first and
    // lose what they clobber. Without any caller in the image, the first
    // recognised instruction is taken, an ENDBR64 in front of it included.
    unsigned char* entry = CallTarget(first - 16 >= lo ? first - 16 : lo, first);
    if (!entry)
    {
        entry = first;
        if (entry - lo >= 4 && entry[-4] == 0xF3 && entry[-3] == 0x0F && entry[-2] == 0x1E && entry[-1] == 0xFA)
            entry -= 4;
    }

    out->site = entry;
    out->ret = ret;
    out->argIndex = arg;
    return 1;
}

// Is `ref` the lea inside the inlined copy, byte for byte? Returns its start.
static unsigned char* MatchInlined(unsigned char* ref)
{
    const struct Seg* seg = ExecSeg(ref);
    if (!seg)
        return NULL;
    unsigned char* at = ref - INLINED_REL_AT;
    if (at < seg->start || at + INLINED_LEN > seg->start + seg->size)
        return NULL;
    for (int i = 0; i < INLINED_LEN; i++)
    {
        if (i >= INLINED_REL_AT && i < INLINED_REL_END)
            continue;
        if (at[i] != kInlined[i])
            return NULL;
    }
    return at;
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
                 "the nine vanilla frequencies of 1.30 are not in the executable (%d segment(s) "
                 "searched) -- this is not a 1.30 server, or the game changed its table; "
                 "nothing was patched", g_nsegs);
        return 0;
    }

    // Every place in the code whose four bytes land on a table: as a
    // displacement from the next instruction, or as the bare address in an
    // executable linked at a fixed base.
    struct Found found[MAX_REFS];
    int nfound = 0;
    int nrefs = 0;
    unsigned char* inlined[MAX_REFS];
    unsigned char* inlinedTable[MAX_REFS];
    int ninlined = 0;

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

            unsigned char* copy = MatchInlined(p);
            if (copy && ninlined < MAX_REFS)
            {
                inlined[ninlined] = copy;
                inlinedTable[ninlined] = table;
                ninlined++;
                continue;
            }

            struct Found one;
            memset(&one, 0, sizeof(one));
            if (!MatchLeaf(p, &one))
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
                 "%d reference(s) to the vanilla table, none of them the 1.30 leaf (a sign-extended "
                 "argument, the 1/9 multiplier, a mul, the table, a movss and a return) -- this "
                 "build compiles the lookup differently; the bytes are in the lines above, "
                 "nothing was patched", nrefs);
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

    // The inlined copy is taken only when it is unique and reads the same
    // table; anything else is reported and left alone, because the leaf alone
    // already covers every tuning and a wrong mid-function patch would be fatal.
    char inlineNote[160] = "; no inlined copy";
    if (ninlined == 1 && inlinedTable[0] == out->table)
    {
        out->inlineAt = inlined[0];
        snprintf(inlineNote, sizeof(inlineNote), "; inlined copy at +0x%llX reads the same table",
                 (unsigned long long)(inlined[0] - g_base));
    }
    else if (ninlined == 1)
    {
        snprintf(inlineNote, sizeof(inlineNote), "; inlined copy at +0x%llX reads another table, left alone",
                 (unsigned long long)(inlined[0] - g_base));
    }
    else if (ninlined > 1)
    {
        snprintf(inlineNote, sizeof(inlineNote), "; %d inlined copies, left alone", ninlined);
    }

    snprintf(why, whyLen,
             "lookup at +0x%llX (%d bytes to its return, index in %s), table at +0x%llX, "
             "table is the known vanilla nine%s",
             (unsigned long long)(out->site - g_base), (int)(out->ret + 1 - out->site),
             out->argIndex == 2 ? "esi, the second argument" : "edi, the first argument",
             (unsigned long long)(out->table - g_base), inlineNote);
    return 1;
}

// ------------------------------------------------------------------ the patch

#define JUMP_LEN  5    // E9 rel32

// A page within a relative jump's reach of `site`, to hold the relay. Tried at
// 64 KiB steps outward from the site, below and above; MAP_FIXED_NOREPLACE asks
// for exactly that address or nothing, and a kernel too old to know the flag
// treats the address as a hint, which the comparison below catches.
//
// `ceiling`, when not zero, rules out every page that would end above it. The
// heap grows upward from the end of the executable, and a page planted there
// would stand in its way; below that end -- under the image, or in a gap
// between its segments, where the real server's relay lands -- nothing grows.
static unsigned char* MapNear(const unsigned char* site, size_t page, uintptr_t ceiling)
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
            if (ceiling && want + page > ceiling)
                continue;
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

    // Out of the heap's way first; anywhere in reach only if that finds nothing.
    unsigned char* relay = MapNear(site, page, g_imageEnd);
    if (!relay)
        relay = MapNear(site, page, 0);
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
                 "mprotect(read+exec) failed AFTER the bytes were written: %s -- that page of "
                 "the server's code is left without execute permission and the server will "
                 "crash; start it without this library (a policy that forbids changed code "
                 "pages, SELinux's execmod for one, does this)", strerror(errno));
        return 0;
    }
    __builtin___clear_cache((char*)site, (char*)site + JUMP_LEN);

    snprintf(why, whyLen, "redirected %d bytes through a relay at %p", JUMP_LEN, (void*)relay);
    return 1;
}

// The inlined copy: the caller's own instruction first, then the index into
// esi, then a call to the member stub through rax -- which the original block
// clobbers anyway -- and nops to the end of the block. The stub saves and
// restores every other register and leaves the frequency in xmm0, which is
// exactly what the instruction after the block stores.
static int PatchInlined(unsigned char* at, void* stub, char* why, size_t whyLen)
{
    unsigned char code[sizeof(kInlined)];
    size_t n = 0;
    memcpy(code + n, kInlinedKeep, sizeof(kInlinedKeep));
    n += sizeof(kInlinedKeep);
    memcpy(code + n, kInlinedLoad, sizeof(kInlinedLoad));
    n += sizeof(kInlinedLoad);
    code[n++] = 0x48;
    code[n++] = 0xB8;
    memcpy(code + n, &stub, sizeof(void*));
    n += sizeof(void*);
    code[n++] = 0xFF;
    code[n++] = 0xD0;
    while (n < sizeof(code))
        code[n++] = 0x90;

    const size_t page = (size_t)sysconf(_SC_PAGESIZE);
    uintptr_t from = (uintptr_t)at & ~(uintptr_t)(page - 1);
    uintptr_t to = ((uintptr_t)at + sizeof(code) + page - 1) & ~(uintptr_t)(page - 1);
    if (mprotect((void*)from, to - from, PROT_READ | PROT_WRITE) != 0)
    {
        snprintf(why, whyLen, "mprotect(read+write) on the inlined copy failed: %s; left alone",
                 strerror(errno));
        return 0;
    }
    memcpy(at, code, sizeof(code));
    if (mprotect((void*)from, to - from, PROT_READ | PROT_EXEC) != 0)
    {
        snprintf(why, whyLen,
                 "mprotect(read+exec) failed AFTER the inlined copy was written: %s -- that page "
                 "of the server's code is left without execute permission and the server will "
                 "crash; start it without this library", strerror(errno));
        return 0;
    }
    __builtin___clear_cache((char*)at, (char*)at + sizeof(code));
    snprintf(why, whyLen, "inlined copy: replaced %d bytes with a call", INLINED_LEN);
    return 1;
}

// The engine's lookup, called the way the engine calls it. Only meaningful
// after the redirect: from the site on, the original bytes are no longer a
// function of their own.
static float CallLookup(const struct Found* found, int index)
{
    if (found->argIndex == 2)
        return ((float (*)(void*, int))found->site)(NULL, index);
    return ((float (*)(int))found->site)(index);
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
                "line carries a server's arguments. A launcher that passes them along (timeout, "
                "nohup) looks like this and can be ignored; if this IS the server under another "
                "name, name the executable DayZServer.", g_exe);
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

    if (found.inlineAt)
    {
        if (PatchInlined(found.inlineAt, (void*)&oz_stub_member, why, sizeof(why)))
            Log("patched: %s", why);
        else
            Log("inlined copy left alone: %s", why);
    }

    Log("channels: %d, from %.3f MHz in steps of %.4f MHz (index 0 = %.3f, index %d = %.3f)",
        g_config.count, g_config.base, g_config.step,
        g_config.base, g_config.count - 1,
        g_config.base + (g_config.count - 1) * g_config.step);

    // OZ_FREQUENCIES_SELFTEST=1: call the engine's own lookup, through the jump
    // just written, and say what it answers. This is the proof on a real server
    // that does not need the game to boot: the path engine -> relay -> stub -> C
    // either returns the grid or it does not.
    if (getenv("OZ_FREQUENCIES_SELFTEST"))
    {
        const int n = g_config.count;
        Log("self-test: the engine's lookup now answers index 0 = %.3f, 1 = %.3f, 9 = %.3f, "
            "%d = %.3f, %d = %.3f (wraps), -1 = %.3f (wraps)",
            CallLookup(&found, 0), CallLookup(&found, 1), CallLookup(&found, 9),
            n - 1, CallLookup(&found, n - 1), n, CallLookup(&found, n), CallLookup(&found, -1));
    }
}
