<#
.SYNOPSIS
Script-level profiler and long-run monitor for the retail DayZ server:
which script function, from which mod, the main thread is running, every
freeze of that thread, and what every other thread is doing -- without
Python, for hours, surviving server restarts.

.DESCRIPTION
Same method as script-profile.py: samples the main thread of
DayZServer_x64.exe and on every sample reads the Enforce VM's own call stack;
every other thread is sampled too (addresses only, at a lower rate) with its
CPU time per minute, so a freeze that does not live on the main thread still
shows up, by thread. Nothing is installed; the game process is only read.

Double-click profile-server.bat, or from PowerShell:

    powershell -ExecutionPolicy Bypass -File script-profile.ps1
        the monitor (24 h by default): every minute one window goes to
        <out>.log and <out>.windows.csv, every thread's minute to
        <out>.threads.csv, every freeze of the main thread to
        <out>.hitches.csv, the cumulative <out>.functions.csv and
        <out>.engine.csv are rewritten; when the server restarts it waits
        for the new process and carries on. Closing the window at any moment
        loses at most the current minute. Files land next to this script.

    powershell -ExecutionPolicy Bypass -File script-profile.ps1 -Seconds 60
        one window, the report on the screen: for a problem happening now.

The script elevates itself (the server usually runs elevated). Offsets are
for DayZServer_x64.exe of 2026-08-13 (16,965,176 bytes); a different build is
refused rather than guessed. See script-profile.py for the structures read.

.PARAMETER Hours
How long the monitor runs (default 24).

.PARAMETER Seconds
Sample this long and print the report instead of monitoring.

.PARAMETER ThreadsHz
Samples per second of every other thread (default 50; 0 = main thread only).

.PARAMETER Out
File prefix (default: script-profile-<date> next to this script).
#>
param(
    [int]$ProcessIdToSample = 0,
    [string]$Exe = "DayZServer_x64.exe",
    [double]$Seconds = 0,
    [double]$Hours = 24,
    [double]$Window = 60,
    [double]$Hz = 200,
    [double]$ThreadsHz = 50,
    [int]$Top = 30,
    [double]$MinRunMs = 150,
    [string]$Out = "",
    [switch]$NoElevate
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $NoElevate) {
    $argList = @("-ExecutionPolicy", "Bypass", "-NoExit", "-File", ('"' + $PSCommandPath + '"'),
                 "-ProcessIdToSample", $ProcessIdToSample, "-Exe", $Exe, "-Seconds", $Seconds, "-Hours", $Hours,
                 "-Window", $Window, "-Hz", $Hz, "-ThreadsHz", $ThreadsHz, "-Top", $Top, "-MinRunMs", $MinRunMs)
    if ($Out -ne "") { $argList += @("-Out", ('"' + $Out + '"')) }
    Write-Host "the server runs elevated, so this asks for elevation too..."
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    exit
}

$src = @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

public class DzScriptProfiler
{
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, IntPtr size, out IntPtr read);
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr OpenThread(uint access, bool inherit, uint tid);
    [DllImport("kernel32.dll")] static extern uint SuspendThread(IntPtr h);
    [DllImport("kernel32.dll")] static extern uint ResumeThread(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool GetThreadContext(IntPtr h, IntPtr ctx);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll")] static extern bool GetThreadTimes(IntPtr h, out long creation, out long exit, out long kernel, out long user);
    [StructLayout(LayoutKind.Sequential)] struct IO_COUNTERS { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
    [DllImport("kernel32.dll")] static extern bool GetProcessIoCounters(IntPtr h, out IO_COUNTERS io);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern int GetThreadDescription(IntPtr h, out IntPtr desc);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr p);
    [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint ms);
    [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint ms);
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr CreateWaitableTimerExW(IntPtr attrs, IntPtr name, uint flags, uint access);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetWaitableTimer(IntPtr h, ref long due, int period, IntPtr routine, IntPtr arg, bool resume);

    const uint PROCESS_VM_READ = 0x10, PROCESS_QUERY_INFORMATION = 0x400, SYNCHRONIZE = 0x100000;
    const uint THREAD_ALL = 0x0002 | 0x0008 | 0x0040;
    const uint WAIT_TIMEOUT = 0x102;
    const int CONTEXT_CONTROL_INTEGER = 0x00100003;
    const int CONTEXT_SIZE = 1232, OFF_RIP = 0xF8, OFF_RSP = 0x98, OFF_FLAGS = 0x30;

    // --- the engine build these were read from ------------------------------
    const long INTERP_LO = 0x2E01E0, VM_LO = 0x2C5000, VM_HI = 0x2E9000, CTX_GLOBAL = 0xF23610;
    static readonly byte[] INTERP_SHAPE = { 0x48, 0x8b, 0xc4, 0x48, 0x89, 0x58, 0x10, 0x44 };
    const int CTX_CALLSTACK = 0x2C8, CS_OWNER = 0x40, CS_DEPTH = 0x48, CS_FRAMES = 0x50, FRAME_SIZE = 0x30;
    const int FUNC_CODE = 0x08, FUNC_MODULE = 0x40, FUNC_NAME = 0x48, FUNC_FLAGS = 0x50, FUNC_FLAG_SCRIPT = 0x10;
    const int MOD_CLASSES = 0x68, MOD_CLASS_COUNT = 0x70, MOD_CODE = 0x78, MOD_DEBUG = 0x80, CODE_START = 0x20;
    const int DBG_FILES = 0x00, DBG_ENTRIES = 0x30, DBG_COUNT = 0x3C;
    const int CLS_NAME = 0x10, CLS_FUNCS = 0x68, CLS_FUNC_COUNT = 0x74;
    const int MAX_DEPTH = 256;
    static readonly Regex ModdedSuffix = new Regex(@"@\d+#\d+$");
    static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    // ---- process state -------------------------------------------------------
    IntPtr h;
    Process proc;
    int pid;
    IntPtr ctxRaw, ctxBuf;
    byte[] zeros = new byte[CONTEXT_SIZE];
    byte[] small = new byte[512];
    byte[] frames = new byte[MAX_DEPTH * FRAME_SIZE];
    Dictionary<uint, IntPtr> threads = new Dictionary<uint, IntPtr>();
    long exeBase, exeHi, vlo, vhi, cs;
    uint mainTid;
    long lastRsp;
    List<ProcessModule> mods = new List<ProcessModule>();
    IntPtr napTimer = IntPtr.Zero;
    static volatile bool stopRequested = false;
    static bool descriptionsWork = true;

    // ---- names --------------------------------------------------------------
    class Info { public string Name; public string Mod; public string File; public int Line; public bool IsScript; }
    class Dbg { public long Start; public uint[] Offs; public ushort[] Lines; public ushort[] Fidx; public long Files; public Dictionary<int, string> Cache = new Dictionary<int, string>(); }
    Dictionary<long, Info> infos = new Dictionary<long, Info>();
    Dictionary<long, Dictionary<long, KeyValuePair<uint, string>>> classMaps = new Dictionary<long, Dictionary<long, KeyValuePair<uint, string>>>();
    Dictionary<long, Dbg> dbgs = new Dictionary<long, Dbg>();
    Dictionary<long, bool> scriptFlag = new Dictionary<long, bool>();

    // ---- counters -----------------------------------------------------------
    class Counters
    {
        public Dictionary<long, int> Self = new Dictionary<long, int>(), Native = new Dictionary<long, int>(), Incl = new Dictionary<long, int>(),
            Owner = new Dictionary<long, int>(), OwnerNative = new Dictionary<long, int>(), EngineOff = new Dictionary<long, int>();
        public Dictionary<string, int> EngineMod = new Dictionary<string, int>();
        public Dictionary<long, Dictionary<long, int>> Callers = new Dictionary<long, Dictionary<long, int>>();
        public int Total, Engine, Interp, NativeN, VmEntry;
        public void Add(Counters o)
        {
            Merge(Self, o.Self); Merge(Native, o.Native); Merge(Incl, o.Incl); Merge(Owner, o.Owner); Merge(OwnerNative, o.OwnerNative); Merge(EngineOff, o.EngineOff);
            foreach (KeyValuePair<string, int> kv in o.EngineMod) Bump(EngineMod, kv.Key, kv.Value);
            foreach (KeyValuePair<long, Dictionary<long, int>> kv in o.Callers)
            {
                Dictionary<long, int> c;
                if (!Callers.TryGetValue(kv.Key, out c)) { c = new Dictionary<long, int>(); Callers[kv.Key] = c; }
                Merge(c, kv.Value);
            }
            Total += o.Total; Engine += o.Engine; Interp += o.Interp; NativeN += o.NativeN; VmEntry += o.VmEntry;
        }
        public double Pct(int n) { return 100.0 * n / Math.Max(1, Total); }
    }
    class Stretch { public string Kind; public long Key; public int N; public double First, Last, Ms; public DateTime At; public Dictionary<long, int> Spots = new Dictionary<long, int>(); }
    // What is known about one non-main thread: where it was, and the longest
    // time it stood at one exe address (a spin, a lock, one long call).
    class OtherThread
    {
        public int N, Exe;
        public Dictionary<long, int> Offs = new Dictionary<long, int>();
        public Dictionary<string, int> Mods = new Dictionary<string, int>();
        public long StallRip = -1, StallAtRip; public double StallFirst, StallMs; public DateTime StallAt;
        public void Add(OtherThread o)
        {
            N += o.N; Exe += o.Exe; Merge(Offs, o.Offs);
            foreach (KeyValuePair<string, int> kv in o.Mods) Bump(Mods, kv.Key, kv.Value);
            if (o.StallMs > StallMs) { StallMs = o.StallMs; StallAtRip = o.StallAtRip; StallAt = o.StallAt; }
        }
    }

    Counters win = new Counters(), cum = new Counters();
    Stretch run = null;
    List<Stretch> hitchesWin = new List<Stretch>();
    Dictionary<uint, OtherThread> others = new Dictionary<uint, OtherThread>(), othersCum = new Dictionary<uint, OtherThread>();
    Dictionary<uint, double> cpuPrev = new Dictionary<uint, double>();
    Dictionary<uint, string> threadNames = new Dictionary<uint, string>();
    double periodMs, minRunMs;
    int every, tick;

    static void Bump(Dictionary<long, int> d, long k) { int v; d.TryGetValue(k, out v); d[k] = v + 1; }
    static void Bump(Dictionary<string, int> d, string k, int by) { int v; d.TryGetValue(k, out v); d[k] = v + by; }
    static void Merge(Dictionary<long, int> d, Dictionary<long, int> o) { foreach (KeyValuePair<long, int> kv in o) { int v; d.TryGetValue(kv.Key, out v); d[kv.Key] = v + kv.Value; } }
    static List<KeyValuePair<long, int>> Sorted(Dictionary<long, int> d)
    {
        List<KeyValuePair<long, int>> l = new List<KeyValuePair<long, int>>(d);
        l.Sort(delegate (KeyValuePair<long, int> a, KeyValuePair<long, int> b) { return b.Value.CompareTo(a.Value); });
        return l;
    }
    static List<KeyValuePair<string, int>> SortedS(Dictionary<string, int> d)
    {
        List<KeyValuePair<string, int>> l = new List<KeyValuePair<string, int>>(d);
        l.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b) { return b.Value.CompareTo(a.Value); });
        return l;
    }
    static string Csv(string s)
    {
        if (s == null) return "";
        if (s.IndexOfAny(new char[] { ',', '"', '\n' }) < 0) return s;
        return "\"" + s.Replace("\"", "\"\"") + "\"";
    }
    static string F(string fmt, params object[] args) { return string.Format(Inv, fmt, args); }
    static string Stamp() { return DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", Inv); }

    // ---- process access ------------------------------------------------------
    bool Read(long addr, byte[] buf, int n)
    {
        if (addr == 0 || n <= 0 || n > buf.Length) return false;
        IntPtr got;
        if (!ReadProcessMemory(h, (IntPtr)addr, buf, (IntPtr)n, out got)) return false;
        return got.ToInt64() == n;
    }
    long Q(long addr) { return Read(addr, small, 8) ? BitConverter.ToInt64(small, 0) : 0; }
    uint U32(long addr) { return Read(addr, small, 4) ? BitConverter.ToUInt32(small, 0) : 0; }
    string CStr(long addr, int max)
    {
        if (addr == 0) return null;
        byte[] b = new byte[max];
        int n = max;
        while (n >= 16 && !Read(addr, b, n)) n /= 2;   // the string may end near an unmapped page
        if (n < 16) return null;
        int len = 0;
        while (len < n && b[len] != 0) { if (b[len] < 32 || b[len] >= 127) return null; len++; }
        if (len == 0) return null;
        return Encoding.ASCII.GetString(b, 0, len);
    }
    IntPtr ThreadHandle(uint tid)
    {
        IntPtr th;
        if (!threads.TryGetValue(tid, out th)) { th = OpenThread(THREAD_ALL, false, tid); threads[tid] = th; }
        return th;
    }
    void DropThread(uint tid)
    {
        IntPtr th;
        if (threads.TryGetValue(tid, out th)) { if (th != IntPtr.Zero) CloseHandle(th); threads.Remove(tid); }
    }
    // rip of a thread, or -1. With hold=true the thread stays suspended so the
    // VM's call stack can be read consistently; call Release afterwards.
    long Rip(uint tid, bool hold)
    {
        IntPtr th = ThreadHandle(tid);
        if (th == IntPtr.Zero) return -1;
        if (SuspendThread(th) == 0xFFFFFFFF) return -1;
        bool ok = false;
        try
        {
            Marshal.Copy(zeros, 0, ctxBuf, CONTEXT_SIZE);
            Marshal.WriteInt32(ctxBuf, OFF_FLAGS, CONTEXT_CONTROL_INTEGER);
            if (!GetThreadContext(th, ctxBuf)) return -1;
            ok = true;
            lastRsp = Marshal.ReadInt64(ctxBuf, OFF_RSP);
            return Marshal.ReadInt64(ctxBuf, OFF_RIP);
        }
        finally { if (!(ok && hold)) ResumeThread(th); }
    }
    void Release(uint tid) { IntPtr th; if (threads.TryGetValue(tid, out th) && th != IntPtr.Zero) ResumeThread(th); }
    bool Alive() { return WaitForSingleObject(h, 0) == WAIT_TIMEOUT; }
    // The process I/O counters include sockets: what the server sent to the
    // players and read from them, plus file and device traffic.
    double[] IoBytes() { IO_COUNTERS io; if (!GetProcessIoCounters(h, out io)) return new double[] { 0, 0, 0 }; return new double[] { io.WriteBytes, io.ReadBytes, io.OtherBytes }; }
    double ThreadCpu(uint tid)
    {
        IntPtr th = ThreadHandle(tid);
        long c, e, k, u;
        if (th == IntPtr.Zero || !GetThreadTimes(th, out c, out e, out k, out u)) return -1;
        return (k + u) / 1e7;
    }
    string ThreadName(uint tid)
    {
        if (!descriptionsWork) return "";
        IntPtr th = ThreadHandle(tid);
        if (th == IntPtr.Zero) return "";
        try
        {
            IntPtr s;
            if (GetThreadDescription(th, out s) < 0 || s == IntPtr.Zero) return "";
            string name = Marshal.PtrToStringUni(s);
            LocalFree(s);
            return name ?? "";
        }
        catch (EntryPointNotFoundException) { descriptionsWork = false; return ""; }
    }
    string ModuleOf(long addr)
    {
        foreach (ProcessModule m in mods)
        {
            long b = m.BaseAddress.ToInt64();
            if (addr >= b && addr < b + m.ModuleMemorySize) return m.ModuleName;
        }
        return "?";
    }
    long ExeCaller(long rsp)
    {
        byte[] b = new byte[0x400];
        if (!Read(rsp, b, b.Length)) return 0;
        for (int off = 0; off + 8 <= b.Length; off += 8)
        {
            long v = BitConverter.ToInt64(b, off);
            if (v >= exeBase && v < exeHi) return v - exeBase;
        }
        return 0;
    }
    void Nap(double ms)
    {
        if (napTimer != IntPtr.Zero)
        {
            long due = -(long)(ms * 10000.0);
            if (SetWaitableTimer(napTimer, ref due, 0, IntPtr.Zero, IntPtr.Zero, false)) { WaitForSingleObject(napTimer, 1000); return; }
        }
        System.Threading.Thread.Sleep((int)Math.Max(1.0, ms));
    }
    string TName(uint tid) { string n; return threadNames.TryGetValue(tid, out n) && n.Length > 0 ? " " + n : ""; }

    // The other threads come and go; keep the set current once a window.
    void RefreshThreads()
    {
        HashSet<uint> now = new HashSet<uint>();
        try { proc.Refresh(); foreach (ProcessThread t in proc.Threads) now.Add((uint)t.Id); } catch (Exception) { }
        now.Remove(mainTid);
        List<uint> gone = new List<uint>();
        foreach (uint tid in others.Keys) if (!now.Contains(tid)) gone.Add(tid);
        foreach (uint tid in gone) { others.Remove(tid); DropThread(tid); cpuPrev.Remove(tid); }
        foreach (uint tid in now)
            if (!others.ContainsKey(tid)) { others[tid] = new OtherThread(); threadNames[tid] = ThreadName(tid); cpuPrev[tid] = ThreadCpu(tid); }
    }

    // ---- names --------------------------------------------------------------
    static string ModOf(string path)
    {
        if (path == null) return "?";
        string[] parts = path.Replace('\\', '/').Split('/');
        if (parts[0] == "scripts") return "vanilla";
        if (parts[0] == "JM" && parts.Length > 1) return "JM/" + parts[1];
        return parts[0];
    }
    Dictionary<long, KeyValuePair<uint, string>> ClassMap(long M)
    {
        Dictionary<long, KeyValuePair<uint, string>> m;
        if (classMaps.TryGetValue(M, out m)) return m;
        m = new Dictionary<long, KeyValuePair<uint, string>>();
        classMaps[M] = m;
        long arr = Q(M + MOD_CLASSES);
        uint n = U32(M + MOD_CLASS_COUNT);
        if (arr == 0 || n == 0 || n >= 50000) return m;
        byte[] ptrs = new byte[n * 8];
        if (!Read(arr, ptrs, ptrs.Length)) return m;
        for (uint i = 0; i < n; i++)
        {
            long C = BitConverter.ToInt64(ptrs, (int)(i * 8));
            if (C == 0) continue;
            uint k = U32(C + CLS_FUNC_COUNT);
            long fa = Q(C + CLS_FUNCS);
            if (k == 0 || fa == 0 || k >= 20000) continue;
            byte[] fp = new byte[k * 8];
            if (!Read(fa, fp, fp.Length)) continue;
            string cname = CStr(Q(C + CLS_NAME), 200);
            if (cname == null) cname = "?";
            for (uint j = 0; j < k; j++)
            {
                long Fd = BitConverter.ToInt64(fp, (int)(j * 8));
                // A subclass's table repeats every inherited descriptor; the
                // defining class is the one with the FEWEST functions.
                KeyValuePair<uint, string> old;
                if (Fd != 0 && (!m.TryGetValue(Fd, out old) || k < old.Key)) m[Fd] = new KeyValuePair<uint, string>(k, cname);
            }
        }
        return m;
    }
    Dbg DebugTable(long M)
    {
        Dbg d;
        if (dbgs.TryGetValue(M, out d)) return d;
        dbgs[M] = null;
        long code = Q(M + MOD_CODE), dbg = Q(M + MOD_DEBUG);
        if (code == 0 || dbg == 0) return null;
        long start = Q(code + CODE_START), ents = Q(dbg + DBG_ENTRIES), files = Q(dbg + DBG_FILES);
        uint cnt = U32(dbg + DBG_COUNT);
        if (start == 0 || ents == 0 || files == 0 || cnt == 0 || cnt > 2000000) return null;
        byte[] raw = new byte[cnt * 8];
        if (!Read(ents, raw, raw.Length)) return null;
        d = new Dbg();
        d.Start = start; d.Files = files;
        d.Offs = new uint[cnt]; d.Lines = new ushort[cnt]; d.Fidx = new ushort[cnt];
        for (int i = 0; i < cnt; i++)
        {
            d.Offs[i] = BitConverter.ToUInt32(raw, i * 8);
            d.Lines[i] = BitConverter.ToUInt16(raw, i * 8 + 4);
            d.Fidx[i] = BitConverter.ToUInt16(raw, i * 8 + 6);
        }
        dbgs[M] = d;
        return d;
    }
    bool FileLine(long M, long code, out string file, out int line)
    {
        file = null; line = 0;
        Dbg d = DebugTable(M);
        if (d == null || code == 0) return false;
        long off = code - d.Start;
        if (off < 0 || off >= 0x7FFFFFFF) return false;
        int i = Array.BinarySearch(d.Offs, (uint)off);
        if (i < 0) i = ~i - 1;
        else { while (i + 1 < d.Offs.Length && d.Offs[i + 1] == (uint)off) i++; }
        if (i < 0) return false;
        int fi = d.Fidx[i];
        string s;
        if (!d.Cache.TryGetValue(fi, out s)) { s = CStr(Q(d.Files + fi * 8L), 260); d.Cache[fi] = s; }
        file = s; line = d.Lines[i];
        return true;
    }
    bool IsScript(long Fd)
    {
        bool v;
        if (!scriptFlag.TryGetValue(Fd, out v)) { v = (U32(Fd + FUNC_FLAGS) & FUNC_FLAG_SCRIPT) != 0; scriptFlag[Fd] = v; }
        return v;
    }
    Info Get(long Fd)
    {
        Info r;
        if (infos.TryGetValue(Fd, out r)) return r;
        r = new Info(); r.Name = "?"; r.Mod = "?"; r.Line = 0;
        infos[Fd] = r;
        if (Fd == 0) return r;
        string fname = CStr(Q(Fd + FUNC_NAME), 200);
        long M = fname != null ? Q(Fd + FUNC_MODULE) : 0;
        if (fname == null || M == 0) return r;
        KeyValuePair<uint, string> hit;
        string cname = ClassMap(M).TryGetValue(Fd, out hit) ? ModdedSuffix.Replace(hit.Value, "") : "";
        r.Name = cname.Length > 0 ? cname + "." + fname : fname;
        r.IsScript = IsScript(Fd);
        if (r.IsScript)
        {
            string file; int line;
            FileLine(M, Q(Fd + FUNC_CODE), out file, out line);
            r.File = file; r.Line = line; r.Mod = ModOf(file);
        }
        else r.Mod = "native";
        return r;
    }
    string Where(long Fd)
    {
        Info i = Get(Fd);
        if (i.Mod == "native") return "[engine native]";
        return i.Mod + "  " + (i.File == null ? "?" : i.File.Replace('\\', '/')) + ":" + i.Line;
    }
    string Describe(Stretch r)
    {
        List<KeyValuePair<long, int>> spots = Sorted(r.Spots);
        List<string> parts = new List<string>();
        if (r.Kind == "script")
        {
            Info root = Get(r.Key);
            for (int i = 0; i < spots.Count && i < 3; i++) parts.Add(F("{0} {1:F0}%", Get(spots[i].Key).Name, 100.0 * spots[i].Value / r.N));
            return F("script entered at {0} ({1}); inside: {2}", root.Name, root.Mod, string.Join(", ", parts.ToArray()));
        }
        if (r.Kind == "engine")
        {
            for (int i = 0; i < spots.Count && i < 3; i++) parts.Add(F("+0x{0:X} {1:F0}%", spots[i].Key, 100.0 * spots[i].Value / r.N));
            return "engine, no script on the stack; at " + string.Join(", ", parts.ToArray());
        }
        for (int i = 0; i < spots.Count && i < 2; i++) if (spots[i].Key != 0) parts.Add(F("+0x{0:X} {1:F0}%", spots[i].Key, 100.0 * spots[i].Value / r.N));
        return F("in {0}, a wait or a system call that did not return; called from {1}", r.Kind, parts.Count > 0 ? string.Join(", ", parts.ToArray()) : "?");
    }

    // ---- attach ---------------------------------------------------------------
    // "" on success, "fatal: ..." for a build that does not match, another
    // message when the process cannot be read yet (still loading).
    string Attach(int wantPid, string exeName, Action<string> say)
    {
        pid = wantPid;
        try
        {
            proc = Process.GetProcessById(pid);
            exeBase = proc.MainModule.BaseAddress.ToInt64();
            exeHi = exeBase + proc.MainModule.ModuleMemorySize;
            mods.Clear();
            foreach (ProcessModule m in proc.Modules) mods.Add(m);
        }
        catch (Exception e) { return "cannot open pid " + pid + " (is this window elevated, like the server?): " + e.Message; }
        h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | SYNCHRONIZE, false, pid);
        if (h == IntPtr.Zero) return "OpenProcess failed: " + Marshal.GetLastWin32Error();
        if (ctxRaw == IntPtr.Zero) { ctxRaw = Marshal.AllocHGlobal(CONTEXT_SIZE + 16); ctxBuf = (IntPtr)((ctxRaw.ToInt64() + 15) & ~15L); }
        byte[] shape = new byte[8];
        if (!Read(exeBase + INTERP_LO, shape, 8) || !SameBytes(shape, INTERP_SHAPE))
        { Detach(); return F("fatal: the interpreter at +0x{0:X} does not look like the build this was read from; refusing", INTERP_LO); }
        long ctx = Q(exeBase + CTX_GLOBAL);
        cs = ctx != 0 ? Q(ctx + CTX_CALLSTACK) : 0;
        if (cs == 0 || Q(cs + CS_OWNER) != ctx)
        { Detach(); return F("the script context at +0x{0:X} does not point at a call stack yet (still loading?)", CTX_GLOBAL); }
        say(F("pid {0}, {1} at 0x{2:X}; interpreter and script context match the known build", pid, exeName, exeBase));
        // the main thread: the one most often inside the exe during a short warm-up
        List<uint> tids = new List<uint>();
        foreach (ProcessThread t in proc.Threads) tids.Add((uint)t.Id);
        Dictionary<uint, int> warm = new Dictionary<uint, int>();
        for (int round = 0; round < 40; round++)
        {
            foreach (uint t in tids)
            {
                long r = Rip(t, false);
                if (r >= exeBase && r < exeHi) { int v; warm.TryGetValue(t, out v); warm[t] = v + 1; }
            }
            System.Threading.Thread.Sleep(5);
        }
        mainTid = 0; int best = 0;
        foreach (KeyValuePair<uint, int> kv in warm) if (kv.Value > best) { best = kv.Value; mainTid = kv.Key; }
        if (mainTid == 0) { Detach(); return "no thread is executing inside the exe (is the server still loading?)"; }
        say("main thread " + mainTid);
        vlo = exeBase + VM_LO; vhi = exeBase + VM_HI;
        infos.Clear(); classMaps.Clear(); dbgs.Clear(); scriptFlag.Clear();
        win = new Counters(); cum = new Counters(); run = null; hitchesWin.Clear();
        others.Clear(); othersCum.Clear(); cpuPrev.Clear(); threadNames.Clear(); tick = 0;
        RefreshThreads();
        return "";
    }
    void Detach()
    {
        foreach (KeyValuePair<uint, IntPtr> kv in threads) if (kv.Value != IntPtr.Zero) CloseHandle(kv.Value);
        threads.Clear();
        if (h != IntPtr.Zero) { CloseHandle(h); h = IntPtr.Zero; }
    }
    static bool SameBytes(byte[] a, byte[] b) { if (a.Length != b.Length) return false; for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false; return true; }

    // ---- one sample ---------------------------------------------------------
    void CloseRun()
    {
        Stretch r = run;
        if (r == null) return;
        r.Ms = (r.Last - r.First) + periodMs;
        if (r.Ms >= minRunMs) hitchesWin.Add(r);
        run = null;
    }
    void SampleOthers(double t0)
    {
        foreach (KeyValuePair<uint, OtherThread> kv in others)
        {
            OtherThread o = kv.Value;
            long rip = Rip(kv.Key, false);
            if (rip == -1) continue;
            o.N++;
            if (rip >= exeBase && rip < exeHi)
            {
                long off = rip - exeBase;
                o.Exe++;
                Bump(o.Offs, off);
                if (o.StallRip == off)
                {
                    double ms = (t0 - o.StallFirst) + periodMs * every;
                    if (ms > o.StallMs) { o.StallMs = ms; o.StallAtRip = off; }
                }
                else { o.StallRip = off; o.StallFirst = t0; o.StallAt = DateTime.Now; }
            }
            else { Bump(o.Mods, ModuleOf(rip), 1); o.StallRip = -1; }
        }
    }
    bool Sample(Stopwatch clock)
    {
        double t0 = clock.Elapsed.TotalMilliseconds;
        long rip = Rip(mainTid, true);
        if (rip == -1) return false;
        long rsp = lastRsp;
        uint depth = 0; bool have = false;
        try
        {
            depth = U32(cs + CS_DEPTH);
            have = depth > 0 && depth <= MAX_DEPTH && Read(cs + CS_FRAMES + FRAME_SIZE, frames, (int)depth * FRAME_SIZE);
        }
        finally { Release(mainTid); }
        Counters w = win;
        w.Total++;
        bool inVm = rip >= vlo && rip < vhi;
        bool inExe = rip >= exeBase && rip < exeHi;
        long[] stack = null;
        if (have)
        {
            List<long> fs = new List<long>();
            for (int i = 0; i < depth; i++) { long Fd = BitConverter.ToInt64(frames, i * FRAME_SIZE + 8); if (Fd != 0) fs.Add(Fd); }
            if (fs.Count > 0) stack = fs.ToArray();
        }
        string kind; long key, spot;
        if (stack != null)
        {
            long top = stack[stack.Length - 1];
            Bump(w.Self, top);
            long owner = top;
            for (int i = stack.Length - 1; i >= 0; i--) if (IsScript(stack[i])) { owner = stack[i]; break; }
            Bump(w.Owner, owner);
            if (inVm) w.Interp++;
            else { w.NativeN++; Bump(w.Native, top); Bump(w.OwnerNative, owner); }
            HashSet<long> seen = new HashSet<long>(stack);
            foreach (long Fd in seen) Bump(w.Incl, Fd);
            Dictionary<long, int> c;
            if (!w.Callers.TryGetValue(top, out c)) { c = new Dictionary<long, int>(); w.Callers[top] = c; }
            Bump(c, stack.Length > 1 ? stack[stack.Length - 2] : 0);
            kind = "script"; key = stack[0]; spot = top;
        }
        else
        {
            w.Engine++;
            if (inVm) w.VmEntry++;
            if (inExe) { Bump(w.EngineOff, rip - exeBase); kind = "engine"; key = 0; spot = rip - exeBase; }
            else { kind = ModuleOf(rip); Bump(w.EngineMod, kind, 1); key = 0; spot = ExeCaller(rsp); }
        }
        // A stretch is the main thread doing one thing without coming back to
        // the frame loop; a long one is what a player feels as a freeze.
        Stretch r = run;
        if (r != null && r.Kind == kind && r.Key == key) { r.N++; r.Last = t0; }
        else
        {
            CloseRun();
            run = r = new Stretch(); r.Kind = kind; r.Key = key; r.N = 1; r.First = t0; r.Last = t0; r.At = DateTime.Now;
        }
        Bump(r.Spots, spot);
        tick++;
        if (every > 0 && tick % every == 0) SampleOthers(t0);
        double left = periodMs - (clock.Elapsed.TotalMilliseconds - t0);
        if (left > 0.2) Nap(left);
        return true;
    }

    // ---- reports -------------------------------------------------------------
    void ByMod(Counters c, out List<KeyValuePair<string, int>> mods, out Dictionary<string, int> modsNative)
    {
        Dictionary<string, int> m = new Dictionary<string, int>();
        modsNative = new Dictionary<string, int>();
        foreach (KeyValuePair<long, int> kv in c.Owner)
        {
            string mod = Get(kv.Key).Mod;
            Bump(m, mod, kv.Value);
            int nv; c.OwnerNative.TryGetValue(kv.Key, out nv);
            Bump(modsNative, mod, nv);
        }
        mods = SortedS(m);
    }
    void WindowLines(string stamp, double seconds, List<Stretch> hitches, double cpuPct, double[] ioMb, out List<string> lines, out string row, out List<string> trows)
    {
        Counters w = win;
        proc.Refresh();
        double privMb = proc.PrivateMemorySize64 / 1048576.0, wsMb = proc.WorkingSet64 / 1048576.0;
        int handles = proc.HandleCount;
        double hitMs = 0, maxMs = 0;
        foreach (Stretch r in hitches) { hitMs += r.Ms; if (r.Ms > maxMs) maxMs = r.Ms; }
        List<KeyValuePair<string, int>> mods; Dictionary<string, int> modsNative;
        ByMod(w, out mods, out modsNative);
        lines = new List<string>();
        lines.Add(F("{0}  window {1:F0} s  {2} samples | engine {3:F1}%  script {4:F1}%  natives {5:F1}% | hitches {6}, {7:F0} ms, max {8:F0} ms | private {9:F0} MB  ws {10:F0} MB  handles {11}  threads {12}  cpu {13:F0}% | io out {14:F1} MB  in {15:F1} MB  other {16:F1} MB",
            stamp, seconds, w.Total, w.Pct(w.Engine), w.Pct(w.Interp), w.Pct(w.NativeN), hitches.Count, hitMs, maxMs, privMb, wsMb, handles, others.Count + 1, cpuPct, ioMb[0], ioMb[1], ioMb[2]));
        List<string> mt = new List<string>(), mc = new List<string>();
        for (int i = 0; i < mods.Count && i < 6; i++) { mt.Add(F("{0} {1:F1}%", mods[i].Key, w.Pct(mods[i].Value))); mc.Add(F("{0}={1:F1}", mods[i].Key, w.Pct(mods[i].Value))); }
        List<KeyValuePair<long, int>> tops = Sorted(w.Self);
        List<string> tt = new List<string>(), tc = new List<string>();
        for (int i = 0; i < tops.Count && i < 8; i++) { tt.Add(F("{0} {1:F1}%", Get(tops[i].Key).Name, w.Pct(tops[i].Value))); if (i < 5) tc.Add(F("{0}={1:F1}", Get(tops[i].Key).Name, w.Pct(tops[i].Value))); }
        lines.Add("   mods: " + (mt.Count > 0 ? string.Join("  ", mt.ToArray()) : "-"));
        lines.Add("   top:  " + (tt.Count > 0 ? string.Join(" | ", tt.ToArray()) : "-"));
        List<Stretch> hs = new List<Stretch>(hitches);
        hs.Sort(delegate (Stretch a, Stretch b) { return b.Ms.CompareTo(a.Ms); });
        for (int i = 0; i < hs.Count && i < 10; i++) lines.Add(F("   hitch {0}  {1,6:F0} ms  {2}", hs[i].At.ToString("HH:mm:ss", Inv), hs[i].Ms, Describe(hs[i])));
        // the other threads: their cpu this window, where they were, whether one stood still
        trows = new List<string>();
        List<KeyValuePair<double, uint>> byCpu = new List<KeyValuePair<double, uint>>();
        int busy = 0;
        foreach (KeyValuePair<uint, OtherThread> kv in others)
        {
            uint tid = kv.Key; OtherThread o = kv.Value;
            double cpu = ThreadCpu(tid), prev;
            double cpuMs = (cpu >= 0 && cpuPrev.TryGetValue(tid, out prev) && prev >= 0) ? (cpu - prev) * 1000.0 : 0.0;
            if (cpu >= 0) cpuPrev[tid] = cpu;
            double exePct = 100.0 * o.Exe / Math.Max(1, o.N);
            if (exePct >= 10) busy++;
            List<KeyValuePair<long, int>> offs = Sorted(o.Offs);
            List<string> ts = new List<string>();
            for (int i = 0; i < offs.Count && i < 3; i++) ts.Add(F("+0x{0:X}={1:F1}", offs[i].Key, 100.0 * offs[i].Value / Math.Max(1, o.N)));
            List<KeyValuePair<string, int>> ms = SortedS(o.Mods);
            List<string> msl = new List<string>();
            for (int i = 0; i < ms.Count && i < 2; i++) msl.Add(F("{0}={1:F1}", ms[i].Key, 100.0 * ms[i].Value / Math.Max(1, o.N)));
            string name; threadNames.TryGetValue(tid, out name);
            trows.Add(string.Join(",", new string[] { stamp, tid.ToString(), Csv(name ?? ""), o.N.ToString(), F("{0:F0}", exePct), F("{0:F0}", cpuMs),
                Csv(string.Join(";", ts.ToArray())), Csv(string.Join(";", msl.ToArray())), F("{0:F0}", o.StallMs) }));
            byCpu.Add(new KeyValuePair<double, uint>(cpuMs, tid));
        }
        byCpu.Sort(delegate (KeyValuePair<double, uint> a, KeyValuePair<double, uint> b) { return b.Key.CompareTo(a.Key); });
        List<string> parts = new List<string>();
        for (int i = 0; i < byCpu.Count && i < 3; i++)
        {
            OtherThread o = others[byCpu[i].Value];
            List<KeyValuePair<long, int>> offs = Sorted(o.Offs);
            parts.Add(F("tid {0}{1} cpu {2:F0} ms, exe {3:F0}%{4}", byCpu[i].Value, TName(byCpu[i].Value), byCpu[i].Key, 100.0 * o.Exe / Math.Max(1, o.N),
                offs.Count > 0 ? F(" at +0x{0:X}", offs[0].Key) : ""));
        }
        lines.Add(F("   threads: {0} others, {1} of them busy in the exe; top by cpu: {2}", others.Count, busy, parts.Count > 0 ? string.Join("; ", parts.ToArray()) : "-"));
        List<KeyValuePair<uint, OtherThread>> stalls = new List<KeyValuePair<uint, OtherThread>>();
        foreach (KeyValuePair<uint, OtherThread> kv in others) if (kv.Value.StallMs >= minRunMs) stalls.Add(kv);
        stalls.Sort(delegate (KeyValuePair<uint, OtherThread> a, KeyValuePair<uint, OtherThread> b) { return b.Value.StallMs.CompareTo(a.Value.StallMs); });
        for (int i = 0; i < stalls.Count && i < 5; i++)
            lines.Add(F("   thread {0}{1} stood at +0x{2:X} for {3:F0} ms (from {4})", stalls[i].Key, TName(stalls[i].Key), stalls[i].Value.StallAtRip, stalls[i].Value.StallMs, stalls[i].Value.StallAt.ToString("HH:mm:ss", Inv)));
        row = string.Join(",", new string[] { stamp, w.Total.ToString(), F("{0:F1}", w.Pct(w.Engine)), F("{0:F1}", w.Pct(w.Interp)), F("{0:F1}", w.Pct(w.NativeN)),
            hitches.Count.ToString(), F("{0:F0}", hitMs), F("{0:F0}", maxMs), F("{0:F0}", privMb), F("{0:F0}", wsMb), handles.ToString(), (others.Count + 1).ToString(), F("{0:F0}", cpuPct),
            Csv(string.Join(";", mc.ToArray())), Csv(string.Join(";", tc.ToArray())), F("{0:F1}", ioMb[0]), F("{0:F1}", ioMb[1]), F("{0:F1}", ioMb[2]) });
    }
    List<Stretch> RotateWindow()
    {
        cum.Add(win);
        win = new Counters();
        List<uint> keys = new List<uint>(others.Keys);
        foreach (uint tid in keys)
        {
            OtherThread c;
            if (!othersCum.TryGetValue(tid, out c)) { c = new OtherThread(); othersCum[tid] = c; }
            c.Add(others[tid]);
            others[tid] = new OtherThread();
        }
        RefreshThreads();
        List<Stretch> hs = hitchesWin;
        hitchesWin = new List<Stretch>();
        return hs;
    }
    List<string> ReportLines(Counters c, int top, List<Stretch> allHitches)
    {
        List<string> o = new List<string>();
        o.Add("main thread: " + c.Total + " samples");
        o.Add(F("  {0,5:F1}%  engine only, no script on the stack (of which {1:F1}% entering/leaving the VM)", c.Pct(c.Engine), c.Pct(c.VmEntry)));
        o.Add(F("  {0,5:F1}%  interpreting script", c.Pct(c.Interp)));
        o.Add(F("  {0,5:F1}%  engine natives called from script", c.Pct(c.NativeN)));
        List<KeyValuePair<string, int>> mods; Dictionary<string, int> modsNative;
        ByMod(c, out mods, out modsNative);
        o.Add("");
        o.Add("script time by mod (the innermost script function's file; natives count for the script that called them):");
        foreach (KeyValuePair<string, int> kv in mods) o.Add(F("  {0,6:F2}%  {1,6}  {2,-24} ({3:F2}% of it in engine code)", c.Pct(kv.Value), kv.Value, kv.Key, c.Pct(modsNative[kv.Key])));
        o.Add("");
        o.Add("top functions on the script stack, self time:");
        o.Add(F("  {0,7} {1,7} {2,7}  {3}", "self", "engine", "incl", "function  (mod  file:line)"));
        List<KeyValuePair<long, int>> selfSorted = Sorted(c.Self);
        for (int i = 0; i < selfSorted.Count && i < top; i++)
        {
            long Fd = selfSorted[i].Key; int nv, iv;
            c.Native.TryGetValue(Fd, out nv); c.Incl.TryGetValue(Fd, out iv);
            o.Add(F("  {0,6:F2}% {1,6:F2}% {2,6:F2}%  {3}  ({4})", c.Pct(selfSorted[i].Value), c.Pct(nv), c.Pct(iv), Get(Fd).Name, Where(Fd)));
        }
        o.Add("");
        o.Add("top script functions, inclusive (anywhere on the stack):");
        List<KeyValuePair<long, int>> inclSorted = Sorted(c.Incl);
        for (int i = 0; i < inclSorted.Count && i < top; i++) o.Add(F("  {0,6:F2}%  {1}  ({2})", c.Pct(inclSorted[i].Value), Get(inclSorted[i].Key).Name, Get(inclSorted[i].Key).Mod));
        o.Add("");
        o.Add("who calls the hottest functions:");
        for (int i = 0; i < selfSorted.Count && i < 10; i++)
        {
            long Fd = selfSorted[i].Key;
            List<string> parts = new List<string>();
            Dictionary<long, int> cc;
            if (c.Callers.TryGetValue(Fd, out cc))
            {
                List<KeyValuePair<long, int>> cs2 = Sorted(cc);
                for (int j = 0; j < cs2.Count && j < 3; j++) parts.Add(F("{0} {1:F0}%", cs2[j].Key == 0 ? "<engine>" : Get(cs2[j].Key).Name, 100.0 * cs2[j].Value / selfSorted[i].Value));
            }
            o.Add(F("  {0,-48} <- {1}", Get(Fd).Name, string.Join("; ", parts.ToArray())));
        }
        o.Add("");
        if (allHitches.Count > 0)
        {
            double tot = 0; foreach (Stretch r in allHitches) tot += r.Ms;
            o.Add(F("stretches >= {0:F0} ms where the main thread stayed in one piece of work (what a player feels as a freeze): {1}, {2:F0} ms in all", minRunMs, allHitches.Count, tot));
            List<Stretch> hs = new List<Stretch>(allHitches);
            hs.Sort(delegate (Stretch a, Stretch b) { return b.Ms.CompareTo(a.Ms); });
            for (int i = 0; i < hs.Count && i < 15; i++) o.Add(F("  {0}  {1,7:F0} ms  {2}", hs[i].At.ToString("yyyy-MM-dd HH:mm:ss", Inv), hs[i].Ms, Describe(hs[i])));
            o.Add("  (engine addresses are named by resolve-samples.py against the same exe)");
        }
        else o.Add(F("no stretch >= {0:F0} ms in one piece of work on the main thread: nothing here would be felt as a freeze", minRunMs));
        int engineOnly = 0;
        foreach (KeyValuePair<long, int> kv in c.EngineOff) engineOnly += kv.Value;
        foreach (KeyValuePair<string, int> kv in c.EngineMod) engineOnly += kv.Value;
        if (engineOnly > 0)
        {
            o.Add("");
            o.Add(F("main-thread engine time with no script on the stack ({0:F1}%), by place:", c.Pct(engineOnly)));
            List<KeyValuePair<string, int>> em = SortedS(c.EngineMod);
            for (int i = 0; i < em.Count && i < 4; i++) o.Add(F("  {0,6:F2}%  [module] {1}", c.Pct(em[i].Value), em[i].Key));
            List<KeyValuePair<long, int>> eo = Sorted(c.EngineOff);
            for (int i = 0; i < eo.Count && i < 8; i++) o.Add(F("  {0,6:F2}%  +0x{1:X}", c.Pct(eo[i].Value), eo[i].Key));
        }
        if (othersCum.Count > 0)
        {
            o.Add("");
            o.Add(F("other threads (samples at 1/{0} of the main thread's rate; 'exe' = busy in the engine, the rest is waiting in system code):", Math.Max(1, every)));
            List<KeyValuePair<uint, OtherThread>> ranked = new List<KeyValuePair<uint, OtherThread>>(othersCum);
            ranked.Sort(delegate (KeyValuePair<uint, OtherThread> a, KeyValuePair<uint, OtherThread> b) { return b.Value.Exe.CompareTo(a.Value.Exe); });
            for (int i = 0; i < ranked.Count && i < 10; i++)
            {
                OtherThread ot = ranked[i].Value;
                List<KeyValuePair<long, int>> offs = Sorted(ot.Offs);
                List<string> ts = new List<string>();
                for (int j = 0; j < offs.Count && j < 3; j++) ts.Add(F("+0x{0:X} {1:F1}%", offs[j].Key, 100.0 * offs[j].Value / Math.Max(1, ot.N)));
                List<KeyValuePair<string, int>> ms = SortedS(ot.Mods);
                string modTxt = ms.Count > 0 ? F("  | {0} {1:F0}%", ms[0].Key, 100.0 * ms[0].Value / Math.Max(1, ot.N)) : "";
                o.Add(F("  tid {0,-6}{1,-18} {2,6} samples  exe {3,5:F1}%  {4}{5}", ranked[i].Key, TName(ranked[i].Key), ot.N, 100.0 * ot.Exe / Math.Max(1, ot.N), ts.Count > 0 ? string.Join(", ", ts.ToArray()) : "-", modTxt));
            }
            List<KeyValuePair<uint, OtherThread>> stalls = new List<KeyValuePair<uint, OtherThread>>();
            foreach (KeyValuePair<uint, OtherThread> kv in othersCum) if (kv.Value.StallMs >= minRunMs) stalls.Add(kv);
            stalls.Sort(delegate (KeyValuePair<uint, OtherThread> a, KeyValuePair<uint, OtherThread> b) { return b.Value.StallMs.CompareTo(a.Value.StallMs); });
            for (int i = 0; i < stalls.Count && i < 8; i++)
                o.Add(F("  thread {0}{1} stood at +0x{2:X} for {3:F0} ms at {4}", stalls[i].Key, TName(stalls[i].Key), stalls[i].Value.StallAtRip, stalls[i].Value.StallMs, stalls[i].Value.StallAt.ToString("yyyy-MM-dd HH:mm:ss", Inv)));
        }
        return o;
    }
    void WriteCsvs(string prefix, Counters c, int seg, List<Stretch> allHitches)
    {
        List<Stretch> hs = new List<Stretch>(allHitches);
        hs.Sort(delegate (Stretch a, Stretch b) { return b.Ms.CompareTo(a.Ms); });
        using (StreamWriter w = new StreamWriter(prefix + ".functions.csv", false, new UTF8Encoding(false)))
        {
            w.WriteLine(F("# pid {0} segment {1} samples {2} engine {3} interp {4} native {5}", pid, seg, c.Total, c.Engine, c.Interp, c.NativeN));
            for (int i = 0; i < hs.Count && i < 40; i++) w.WriteLine(F("# hitch {0} {1:F0} ms: {2}", hs[i].At.ToString("HH:mm:ss", Inv), hs[i].Ms, Describe(hs[i])));
            w.WriteLine("function,mod,file,line,self,engine,inclusive,owner");
            foreach (KeyValuePair<long, int> kv in Sorted(c.Incl))
            {
                Info inf = Get(kv.Key); int sv, nv, ov;
                c.Self.TryGetValue(kv.Key, out sv); c.Native.TryGetValue(kv.Key, out nv); c.Owner.TryGetValue(kv.Key, out ov);
                w.WriteLine(string.Join(",", new string[] { Csv(inf.Name), Csv(inf.Mod), Csv(inf.File == null ? "" : inf.File.Replace('\\', '/')),
                    inf.Line.ToString(), sv.ToString(), nv.ToString(), kv.Value.ToString(), ov.ToString() }));
            }
        }
        using (StreamWriter w = new StreamWriter(prefix + ".engine.csv", false, new UTF8Encoding(false)))
        {
            // the collect-samples.ps1 format, so resolve-samples.py names these
            w.WriteLine(F("# dayz script-profile: the main thread's engine-only samples, then every other thread at 1/{0} of its rate", Math.Max(1, every)));
            w.WriteLine(F("# exe_base=0x{0:X} pid={1} segment={2} main_tid={3} samples={4}", exeBase, pid, seg, mainTid, c.Total));
            w.WriteLine("tid,kind,where,count");
            foreach (KeyValuePair<long, int> kv in Sorted(c.EngineOff)) w.WriteLine(F("{0},exe,{1:X},{2}", mainTid, kv.Key, kv.Value));
            foreach (KeyValuePair<string, int> kv in SortedS(c.EngineMod)) w.WriteLine(F("{0},module,{1},{2}", mainTid, kv.Key, kv.Value));
            foreach (KeyValuePair<uint, OtherThread> t in othersCum)
            {
                foreach (KeyValuePair<long, int> kv in Sorted(t.Value.Offs)) w.WriteLine(F("{0},exe,{1:X},{2}", t.Key, kv.Key, kv.Value));
                foreach (KeyValuePair<string, int> kv in SortedS(t.Value.Mods)) w.WriteLine(F("{0},module,{1},{2}", t.Key, kv.Key, kv.Value));
            }
        }
    }

    // ---- files -----------------------------------------------------------------
    static void Append(string path, string text) { File.AppendAllText(path, text + "\n", new UTF8Encoding(false)); }
    static void EnsureHeader(string path, string header) { if (!File.Exists(path)) File.WriteAllText(path, header + "\n", new UTF8Encoding(false)); }

    // ---- the runs -----------------------------------------------------------
    static int FindPid(string exeName)
    {
        string bare = exeName.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? exeName.Substring(0, exeName.Length - 4) : exeName;
        Process[] ps = Process.GetProcessesByName(bare);
        if (ps.Length == 0) return 0;
        // a Diag client uses the same exe name as its server; the server has no window
        foreach (Process p in ps) { try { if (p.MainWindowHandle == IntPtr.Zero) return p.Id; } catch (Exception) { } }
        return ps[0].Id;
    }

    // Returns "fatal", "retry", "exited" or "done".
    string RunSegment(int wantPid, string exeName, int seg, DateTime deadline, double windowSec, int top, string prefix)
    {
        Action<string> say = delegate (string t) { if (prefix != null) Append(prefix + ".log", t); Console.WriteLine(t); };
        string err = Attach(wantPid, exeName, say);
        if (err != "") { say(err); return err.StartsWith("fatal") ? "fatal" : "retry"; }
        List<Stretch> all = new List<Stretch>();
        Stopwatch clock = Stopwatch.StartNew();
        TimeSpan cpu0 = proc.TotalProcessorTime;
        double[] io0 = IoBytes();
        DateTime wall0 = DateTime.Now, nextFlush = wall0.AddSeconds(windowSec);
        bool exited = false;
        while (DateTime.Now < deadline && !stopRequested)
        {
            if (!Sample(clock))
            {
                if (!Alive()) { exited = true; break; }
                System.Threading.Thread.Sleep(50);
            }
            if (win.Total % 400 == 0 && !Alive()) { exited = true; break; }
            if (DateTime.Now >= nextFlush)
            {
                CloseRun();
                List<Stretch> hit = hitchesWin;
                DateTime wall = DateTime.Now;
                TimeSpan cpu = TimeSpan.Zero;
                try { proc.Refresh(); cpu = proc.TotalProcessorTime; } catch (Exception) { }
                double cpuPct = 100.0 * (cpu - cpu0).TotalSeconds / Math.Max(1e-9, (wall - wall0).TotalSeconds);
                double[] io1 = IoBytes();
                double[] ioMb = new double[] { (io1[0] - io0[0]) / 1048576.0, (io1[1] - io0[1]) / 1048576.0, (io1[2] - io0[2]) / 1048576.0 };
                string stamp = Stamp();
                List<string> lines, trows; string row;
                WindowLines(stamp, (wall - wall0).TotalSeconds, hit, cpuPct, ioMb, out lines, out row, out trows);
                if (prefix != null)
                {
                    Append(prefix + ".log", string.Join("\n", lines.ToArray()));
                    Append(prefix + ".windows.csv", stamp + "," + seg + "," + pid + "," + row.Substring(row.IndexOf(',') + 1));
                    foreach (Stretch r in hit) Append(prefix + ".hitches.csv", string.Join(",", new string[] { r.At.ToString("yyyy-MM-dd HH:mm:ss", Inv), seg.ToString(), pid.ToString(), F("{0:F0}", r.Ms), r.Kind, Csv(Describe(r)) }));
                    StringBuilder tb = new StringBuilder();
                    foreach (string t in trows) tb.Append(stamp + "," + seg + "," + pid + "," + t.Substring(t.IndexOf(',') + 1) + "\n");
                    File.AppendAllText(prefix + ".threads.csv", tb.ToString(), new UTF8Encoding(false));
                    Console.WriteLine(lines[0]);
                }
                all.AddRange(RotateWindow());
                if (prefix != null) WriteCsvs(prefix, cum, seg, all);
                cpu0 = cpu; io0 = io1; wall0 = wall; nextFlush = wall.AddSeconds(windowSec);
            }
        }
        CloseRun();
        all.AddRange(RotateWindow());
        List<string> report = ReportLines(cum, top, all);
        if (prefix != null)
        {
            Append(prefix + ".log", "");
            Append(prefix + ".log", F("==== segment {0}, pid {1}: {2} at {3} ====", seg, pid, exited ? "the server exited" : "end of run", Stamp()));
            Append(prefix + ".log", string.Join("\n", report.ToArray()));
            WriteCsvs(prefix, cum, seg, all);
            Console.WriteLine("segment " + seg + " written to " + prefix + ".*");
        }
        else
        {
            Console.WriteLine();
            Console.WriteLine(string.Join("\n", report.ToArray()));
        }
        Detach();
        if (stopRequested) return "done";
        return exited ? "exited" : "done";
    }

    public static int Run(string exeName, int wantPid, double seconds, double hours, double windowSec, double hz, double threadsHz, int top, double minRunMs, string prefix)
    {
        DzScriptProfiler p = new DzScriptProfiler();
        p.periodMs = 1000.0 / hz;
        p.every = threadsHz > 0 ? Math.Max(1, (int)Math.Round(hz / threadsHz)) : 0;
        p.minRunMs = minRunMs;
        bool shortMode = seconds > 0;
        if (shortMode) prefix = null;
        Console.CancelKeyPress += delegate (object s, ConsoleCancelEventArgs e) { e.Cancel = true; stopRequested = true; };
        timeBeginPeriod(1);
        p.napTimer = CreateWaitableTimerExW(IntPtr.Zero, IntPtr.Zero, 0x2 /* CREATE_WAITABLE_TIMER_HIGH_RESOLUTION */, 0x1F0003);
        try
        {
            if (prefix != null)
            {
                EnsureHeader(prefix + ".windows.csv", "time,segment,pid,samples,engine_pct,interp_pct,native_pct,hitches,hitch_ms,max_hitch_ms,private_mb,ws_mb,handles,threads,cpu_pct,mods,top,io_out_mb,io_in_mb,io_other_mb");
                EnsureHeader(prefix + ".hitches.csv", "time,segment,pid,ms,kind,description");
                EnsureHeader(prefix + ".threads.csv", "time,segment,pid,tid,name,samples,exe_pct,cpu_ms,top,module,stall_ms");
                Append(prefix + ".log", F("==== script-profile monitor started {0} (this machine's local time, UTC{1}): {2:F1} h, {3:F0} s windows, {4:F0} Hz main thread, {5:F0} Hz other threads, stretch threshold {6:F0} ms ====", Stamp(), DateTimeOffset.Now.ToString("zzz", Inv), hours, windowSec, hz, threadsHz, minRunMs));
                Console.WriteLine(F("monitoring {0} for {1:F1} h; files: {2}.log / .windows.csv / .threads.csv / .hitches.csv / .functions.csv / .engine.csv", exeName, hours, prefix));
                Console.WriteLine("close this window to stop; nothing is lost but the current minute");
            }
            DateTime deadline = DateTime.Now.AddSeconds(shortMode ? seconds : hours * 3600.0);
            double window = shortMode ? Math.Max(1.0, seconds) : windowSec;
            int seg = 0;
            bool waiting = false;
            while (DateTime.Now < deadline && !stopRequested)
            {
                int pid = (wantPid != 0 && seg == 0) ? wantPid : FindPid(exeName);
                if (pid == 0)
                {
                    if (shortMode) { Console.WriteLine("no " + exeName + " running"); return 1; }
                    if (!waiting) { Append(prefix + ".log", Stamp() + "  waiting for " + exeName + " to start"); Console.WriteLine("waiting for " + exeName + " ..."); waiting = true; }
                    System.Threading.Thread.Sleep(10000);
                    continue;
                }
                waiting = false;
                string rc = p.RunSegment(pid, exeName, seg + 1, deadline, window, top, prefix);
                if (rc == "fatal" || (shortMode && rc != "done")) return 1;
                if (rc == "done") return 0;
                if (rc == "retry") { System.Threading.Thread.Sleep(10000); continue; }
                seg++;
                Append(prefix + ".log", Stamp() + "  the server (pid " + pid + ") is gone; waiting for the next one");
                Console.WriteLine("server pid " + pid + " gone; waiting for the next one ...");
                System.Threading.Thread.Sleep(15000);
            }
            return 0;
        }
        finally
        {
            timeEndPeriod(1);
            if (p.napTimer != IntPtr.Zero) CloseHandle(p.napTimer);
            if (p.ctxRaw != IntPtr.Zero) Marshal.FreeHGlobal(p.ctxRaw);
        }
    }
}
'@

if (-not ("DzScriptProfiler" -as [type])) {
    Add-Type -TypeDefinition $src -Language CSharp
}

if ($Seconds -le 0 -and $Out -eq "") {
    $Out = Join-Path (Split-Path -Parent $PSCommandPath) ("script-profile-" + (Get-Date -Format "yyyyMMdd-HHmm"))
}
$rc = [DzScriptProfiler]::Run($Exe, $ProcessIdToSample, $Seconds, $Hours, $Window, $Hz, $ThreadsHz, $Top, $MinRunMs, $Out)
exit $rc
