// OpenZone: more radio frequencies, server side.
//
// A proxy hid.dll that replaces the engine's frequency lookup so that a tuned
// index maps to `base + index * step` instead of to one of eight hardcoded
// values. See ../../docs/engine-frequency-table.md for why that one function is
// the whole limit and why the design looks like this.
//
// It patches the SERVER ONLY, on purpose. Client and server are the same
// executable in the same directory on a Diag stand, so an ungated proxy would
// patch both -- and the entire question this exists to answer is whether a stock
// client works against a patched server.

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "forwards.h"
#include "patch.h"

// ---------------------------------------------------------------- configuration

struct Config
{
    double base;    // MHz of index 0
    double step;    // MHz between neighbouring indices
    int    count;   // how many channels exist; indices wrap within this
};

// The same three numbers as the mod's built-in radio profiles derive
// (OZR_Profiles.LoadDefaults) and as native/oz_frequencies.json carries: one
// band for every radio, 136.000..155.950 MHz in steps of 0.050, 400 channels.
// Three copies of one default; change them together.
static Config g_config = { 136.0, 0.05, 400 };
static wchar_t g_dir[MAX_PATH] = L"";

// The server's -profiles directory, or empty when it named none.
//
// This is the one place the MOD can write and this DLL cannot reach any
// other way: script file access in DayZ is confined to $profile:. So the
// grid is looked for THERE FIRST, which is what makes an in-game admin
// panel able to set it at all; the copy beside the DLL stays as the
// fallback and as the shipped default.
static wchar_t g_profiles[MAX_PATH] = L"";

// ------------------------------------------------------------------- the log

// Written beside the DLL. A mod that quietly does nothing is the worst outcome
// here -- every path through this file ends in a line saying what happened.
static void Log(const char* fmt, ...)
{
    wchar_t path[MAX_PATH];
    _snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%s\\oz_frequencies.log", g_dir);

    HANDLE h = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE)
        return;

    SYSTEMTIME t;
    GetLocalTime(&t);

    char line[1024];
    int n = _snprintf_s(line, sizeof(line), _TRUNCATE, "%02d:%02d:%02d  ",
                        t.wHour, t.wMinute, t.wSecond);

    va_list args;
    va_start(args, fmt);
    n += _vsnprintf_s(line + n, sizeof(line) - n, _TRUNCATE, fmt, args);
    va_end(args);

    if (n > 0 && n < static_cast<int>(sizeof(line)) - 2)
    {
        line[n++] = '\r';
        line[n++] = '\n';
        DWORD written = 0;
        WriteFile(h, line, n, &written, NULL);
    }
    CloseHandle(h);
}

// -------------------------------------------------------------- config reading

// A three-number config does not justify a JSON library, and a dependency in a
// DLL that loads this early is a liability. This reads exactly the shape the
// documented file has: it finds "key", skips to the colon, and parses a number.
// Anything it cannot find keeps its default, and says so in the log.
static bool ReadNumber(const char* text, const char* key, double* out)
{
    char quoted[64];
    _snprintf_s(quoted, sizeof(quoted), _TRUNCATE, "\"%s\"", key);

    const char* at = strstr(text, quoted);
    if (!at)
        return false;

    const char* colon = strchr(at + strlen(quoted), ':');
    if (!colon)
        return false;

    char* end = NULL;
    double v = strtod(colon + 1, &end);
    if (end == colon + 1)
        return false;

    *out = v;
    return true;
}

// Pull -profiles= out of our own command line.
//
// Every launcher passes it, but the form varies: quoted or bare, with or
// without a trailing slash, absolute or relative to the working directory.
// All of those are handled here, because a path that is ALMOST right reads
// exactly like a missing file.
//
// Tolerant of failure on purpose: no -profiles simply means there is no
// admin-editable copy, which is the state every stand was in until now.
static void FindProfilesDir()
{
    const wchar_t* cmd = GetCommandLineW();
    if (!cmd)
        return;

    const wchar_t* at = wcsstr(cmd, L"-profiles=");
    if (!at)
        return;

    at += 10;   // past "-profiles="

    wchar_t raw[MAX_PATH];
    size_t n = 0;

    if (*at == L'"')
    {
        at++;
        while (*at && *at != L'"' && n < MAX_PATH - 1)
            raw[n++] = *at++;
    }
    else
    {
        // An unquoted path ends at the next argument. A path with spaces
        // in it must have been quoted, so this is not a case that can be
        // recovered -- nor one we can be handed by a launcher that works.
        while (*at && *at != L' ' && n < MAX_PATH - 1)
            raw[n++] = *at++;
    }
    raw[n] = L'\0';

    if (n == 0)
        return;

    while (n > 0 && (raw[n - 1] == L'\\' || raw[n - 1] == L'/'))
        raw[--n] = L'\0';

    // Relative to the WORKING directory -- where the server was launched
    // from, not where this DLL happens to live.
    if (!GetFullPathNameW(raw, MAX_PATH, g_profiles, NULL))
        wcscpy_s(g_profiles, MAX_PATH, raw);
}

// Read one file whole. Missing is not an error at either of the two places
// this gets asked, so it is reported as false and nothing else.
static bool ReadWholeFile(const wchar_t* path, char* out, DWORD cap)
{
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE)
        return false;

    DWORD read = 0;
    BOOL ok = ReadFile(h, out, cap - 1, &read, NULL);
    CloseHandle(h);
    if (!ok)
    {
        Log("%ls could not be read (%lu)", path, GetLastError());
        return false;
    }

    out[read] = '\0';
    return true;
}

static void LoadConfig()
{
    char text[4096];
    wchar_t path[MAX_PATH];
    bool got = false;

    // The admin-editable copy WINS. It sits beside the rest of the mod
    // configs, so a panel that can edit those can edit this one too.
    //
    // The name carries its owner. That directory is shared by three mods, and
    // a plain "Frequencies.json" was one collision away from being somebody
    // else's -- which is exactly what happened once to "Radio.json".
    if (g_profiles[0])
    {
        _snwprintf_s(path, MAX_PATH, _TRUNCATE,
                     L"%s\\OpenZone\\OZ_Radio_Frequencies.json", g_profiles);
        got = ReadWholeFile(path, text, sizeof(text));
        if (got)
            Log("grid read from the profile: %ls", path);
    }

    if (!got)
    {
        _snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%s\\oz_frequencies.json", g_dir);
        got = ReadWholeFile(path, text, sizeof(text));
        if (got)
            Log("grid read from beside the DLL: %ls", path);
    }

    if (!got)
    {
        Log("no grid file in the profile or beside the DLL; using defaults "
            "base=%.3f step=%.3f count=%d", g_config.base, g_config.step, g_config.count);
        return;
    }

    double count = g_config.count;
    if (!ReadNumber(text, "base_mhz", &g_config.base))
        Log("oz_frequencies.json has no base_mhz; keeping %.3f", g_config.base);
    if (!ReadNumber(text, "step_mhz", &g_config.step))
        Log("oz_frequencies.json has no step_mhz; keeping %.3f", g_config.step);
    if (ReadNumber(text, "count", &count))
        g_config.count = static_cast<int>(count);
    else
        Log("oz_frequencies.json has no count; keeping %d", g_config.count);

    if (g_config.count < 1)
    {
        Log("count=%d is not usable; forcing 1", g_config.count);
        g_config.count = 1;
    }
    if (g_config.step == 0.0)
    {
        // Every channel would hash to the same key and the mod would appear to
        // do nothing at all. Refuse the value rather than ship that confusion.
        Log("step_mhz=0 would make every channel identical; forcing 0.2");
        g_config.step = 0.2;
    }
}

// ------------------------------------------------------------ the replacement

// Replaces the engine's `float (*)(void* self, int index)`. On x64 the index
// arrives in edx and the result goes back in xmm0, which is what a plain
// function of this signature already does.
//
// Indices wrap rather than clamp, because SetNextChannel is `inc index` with no
// bound of its own: clamping would make the last channel a dead end instead of
// cycling the way the vanilla mask did.
extern "C" float OzFrequencyByIndex(void* /*self*/, int index)
{
    const int n = g_config.count;
    int i = index % n;
    if (i < 0)
        i += n;
    return static_cast<float>(g_config.base + i * g_config.step);
}

// ---------------------------------------------------------------- self-test

// With OZ_FREQUENCIES_SELFTEST=1 in the environment, call the engine's lookup
// through its own entry right after patching and log what it answers. The
// entry now holds our jump, so this exercises the redirect itself on the real
// binary -- the same check the Linux library offers, and the one that tells a
// server operator in twenty seconds whether a new build is covered.
static void SelfTest(unsigned char* func)
{
    wchar_t flag[8] = L"";
    if (!GetEnvironmentVariableW(L"OZ_FREQUENCIES_SELFTEST", flag, 8) || flag[0] != L'1')
        return;

    typedef float (*Lookup)(void*, int);
    Lookup lookup = reinterpret_cast<Lookup>(func);
    const int n = g_config.count;
    Log("self-test: the engine's lookup now answers index 0 = %.3f, 1 = %.3f, 9 = %.3f, "
        "%d = %.3f, %d = %.3f (wraps), -1 = %.3f (wraps)",
        lookup(0, 0), lookup(0, 1), lookup(0, 9),
        n - 1, lookup(0, n - 1), n, lookup(0, n), lookup(0, -1));
}

// ------------------------------------------------------------------- start-up

// Two ways to be the server, and both are needed.
//
// A Diag build is one executable for client and server, told apart only by
// -server on the command line. A real DayZServer_x64.exe needs no such flag --
// it is the dedicated server -- so a gate that read the command line alone
// would skip the very install this is meant for, and skip it silently.
// The bare file name of the process we were loaded into, or empty if Windows
// would not say.
static wchar_t g_exe[MAX_PATH] = L"";

static void FindExeName()
{
    wchar_t full[MAX_PATH] = L"";
    if (!GetModuleFileNameW(NULL, full, MAX_PATH))
        return;

    const wchar_t* name = wcsrchr(full, L'\\');
    name = name ? name + 1 : full;
    wcscpy_s(g_exe, MAX_PATH, name);
}

static bool IsDedicatedServer()
{
    const wchar_t* cmd = GetCommandLineW();
    if (cmd && wcsstr(cmd, L"-server") != NULL)
        return true;

    return _wcsicmp(g_exe, L"DayZServer_x64.exe") == 0;
}

// Everything the game itself ships in that directory.
//
// A proxy is loaded by whatever runs from the folder it sits in, and that
// folder holds six executables, not one: the launcher and the BattlEye shim
// run on every ordinary game start. Their silence is expected and has to stay
// silent, or the log fills with lines about processes that were never going to
// be a server.
static bool IsKnownGameProcess()
{
    static const wchar_t* known[] = {
        L"DayZ_x64.exe",
        L"DayZDiag_x64.exe",
        L"DayZ_BE.exe",
        L"DayZLauncher.exe",
        L"CrashReporter.exe",
        L"DayZUninstaller.exe",
    };

    for (int i = 0; i < static_cast<int>(sizeof(known) / sizeof(known[0])); i++)
    {
        if (_wcsicmp(g_exe, known[i]) == 0)
            return true;
    }
    return false;
}

static void Start(HMODULE self)
{
    GetModuleFileNameW(self, g_dir, MAX_PATH);
    wchar_t* slash = wcsrchr(g_dir, L'\\');
    if (slash)
        *slash = L'\0';

    // Before LoadConfig: the log always lives beside the DLL, but the grid
    // may not, and LoadConfig has to know where to look first.
    FindProfilesDir();
    FindExeName();

    if (!IsDedicatedServer())
    {
        // Silent for the GAME, loud for a stranger.
        //
        // The silence is deliberate: on a Diag stand this branch runs for the
        // client on every launch, and a line per launch would bury the file
        // under noise.
        //
        // Being silent for EVERYTHING was the mistake. "No DLL beside the
        // executable" and "DLL loaded, then rejected by this gate" both left
        // no log at all -- so the one file whose whole job is to make a silent
        // failure impossible could not tell them apart, and they need opposite
        // fixes. A process that is not one of the game's own is exactly what a
        // renamed or wrapped server looks like, and that is the only shape in
        // which this gate can be wrong about a real server.
        if (!IsKnownGameProcess())
        {
            Log("----");
            Log("NOT PATCHED: loaded into \"%ls\", which is neither "
                "DayZServer_x64.exe nor one of the game's own executables, "
                "and its command line carries no -server. If this IS the "
                "server, launch it with -server.", g_exe);
        }
        return;
    }

    Log("----");
    LoadConfig();

    HMODULE host = GetModuleHandleW(NULL);
    PatchTargets targets = {};
    char why[512] = "";

    if (!FindFrequencyCode(host, &targets, why, sizeof(why)))
    {
        Log("NOT PATCHED: %s", why);
        return;
    }
    Log("found: %s", why);

    if (!targets.tableIsVanilla)
    {
        Log("note: the game's own frequency table is not the %d this shape was "
            "written against -- the patch still applies, but re-check the "
            "research notes against this build", targets.tableCount);
    }

    if (!RedirectFunction(targets.func, reinterpret_cast<void*>(&OzFrequencyByIndex),
                          why, sizeof(why)))
    {
        Log("NOT PATCHED: %s", why);
        return;
    }

    Log("patched: %s", why);

    // 1.30 inlines a second copy of the lookup into the transmitter
    // initialiser. Without this a freshly created radio would start on the
    // game's own table and only join the grid at its first tuning; with it,
    // every path reads one grid. Failing here leaves the leaf patched.
    if (targets.inlineAt)
    {
        if (PatchInlinedLookup(&targets, reinterpret_cast<void*>(&OzFrequencyByIndex),
                               why, sizeof(why)))
            Log("patched: %s", why);
        else
            Log("inlined copy left alone: %s", why);
    }

    SelfTest(targets.func);
    // The STEP gets four places, not three. It is the number most likely to
    // be mis-set, and at three places the shipped 0.0125 prints as 0.013 --
    // a log that rounds the value being checked is a log that lies about it.
    Log("channels: %d, from %.3f MHz in steps of %.4f MHz (index 0 = %.3f, "
        "index %d = %.3f)",
        g_config.count, g_config.base, g_config.step,
        g_config.base, g_config.count - 1,
        g_config.base + (g_config.count - 1) * g_config.step);
}

BOOL APIENTRY DllMain(HMODULE self, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(self);
        Start(self);
    }
    return TRUE;
}
