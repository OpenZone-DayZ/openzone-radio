<#
.SYNOPSIS
Script-level profiler for the retail DayZ server: which script function, in
which mod's file, the main thread is running -- without Python.

.DESCRIPTION
Same method as script-profile.py: samples the main thread of
DayZServer_x64.exe and on every sample reads the Enforce VM's own call stack.
Each sample says which script function was running, from which mod's file,
and whether the time went into interpreting script or into an engine native
the script called. Nothing is installed; the game process is only read.

Run it from an elevated PowerShell (the server usually runs elevated too):

    powershell -ExecutionPolicy Bypass -File script-profile.ps1 -Seconds 60 -Out lag-script.csv

Offsets are for DayZServer_x64.exe of 2026-08-13 (16,965,176 bytes). The
script checks the interpreter's code and the script context at start and
refuses another build. See script-profile.py for the structures it reads.

.PARAMETER ProcessIdToSample
Process id of the server. Default: the DayZServer_x64.exe started with -server.

.PARAMETER Seconds
How long to sample (default 60).

.PARAMETER Hz
Samples per second (default 200).

.PARAMETER Out
Optional CSV with every function's counts, for a later comparison.
#>
param(
    [int]$ProcessIdToSample = 0,
    [string]$Exe = "DayZServer_x64.exe",
    [double]$Seconds = 60,
    [double]$Hz = 200,
    [int]$Top = 30,
    [double]$MinRunMs = 100,
    [string]$Out = ""
)

$src = @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
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
    [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint ms);
    [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint ms);
    [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr CreateWaitableTimerExW(IntPtr attrs, IntPtr name, uint flags, uint access);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetWaitableTimer(IntPtr h, ref long due, int period, IntPtr routine, IntPtr arg, bool resume);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr h, uint ms);

    // Thread.Sleep rounds to the scheduler tick (15.6 ms for a background
    // process on Windows 10+), which would cap the rate at ~70 Hz. A
    // high-resolution waitable timer keeps 200 Hz honest.
    IntPtr napTimer = IntPtr.Zero;
    void Nap(double ms)
    {
        if (napTimer != IntPtr.Zero)
        {
            long due = -(long)(ms * 10000.0);
            if (SetWaitableTimer(napTimer, ref due, 0, IntPtr.Zero, IntPtr.Zero, false)) { WaitForSingleObject(napTimer, 1000); return; }
        }
        System.Threading.Thread.Sleep((int)Math.Max(1.0, ms));
    }

    const uint PROCESS_VM_READ = 0x10, PROCESS_QUERY_INFORMATION = 0x400;
    const uint THREAD_ALL = 0x0002 | 0x0008 | 0x0040;
    const int CONTEXT_CONTROL_INTEGER = 0x00100003;
    const int CONTEXT_SIZE = 1232, OFF_RIP = 0xF8, OFF_FLAGS = 0x30;

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

    IntPtr h;
    IntPtr ctxRaw, ctxBuf;
    byte[] zeros = new byte[CONTEXT_SIZE];
    byte[] small = new byte[512];
    Dictionary<uint, IntPtr> threads = new Dictionary<uint, IntPtr>();

    class Info { public string Name; public string Mod; public string File; public int Line; public bool IsScript; }
    class Dbg { public long Start; public uint[] Offs; public ushort[] Lines; public ushort[] Fidx; public long Files; public Dictionary<int, string> Cache = new Dictionary<int, string>(); }
    Dictionary<long, Info> infos = new Dictionary<long, Info>();
    Dictionary<long, Dictionary<long, KeyValuePair<uint, string>>> classMaps = new Dictionary<long, Dictionary<long, KeyValuePair<uint, string>>>();
    Dictionary<long, Dbg> dbgs = new Dictionary<long, Dbg>();
    Dictionary<long, bool> scriptFlag = new Dictionary<long, bool>();

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
        if (!threads.TryGetValue(tid, out th))
        {
            th = OpenThread(THREAD_ALL, false, tid);
            threads[tid] = th;
        }
        return th;
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
            return Marshal.ReadInt64(ctxBuf, OFF_RIP);
        }
        finally
        {
            if (!(ok && hold)) ResumeThread(th);
        }
    }
    void Release(uint tid)
    {
        IntPtr th;
        if (threads.TryGetValue(tid, out th) && th != IntPtr.Zero) ResumeThread(th);
    }

    // ---- names ---------------------------------------------------------------
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
                long F = BitConverter.ToInt64(fp, (int)(j * 8));
                // A subclass's table repeats every inherited descriptor, so a
                // function appears in its defining class and in every class
                // below it. The defining class has the FEWEST functions.
                KeyValuePair<uint, string> old;
                if (F != 0 && (!m.TryGetValue(F, out old) || k < old.Key))
                    m[F] = new KeyValuePair<uint, string>(k, cname);
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
    bool IsScript(long F)
    {
        bool v;
        if (!scriptFlag.TryGetValue(F, out v)) { v = (U32(F + FUNC_FLAGS) & FUNC_FLAG_SCRIPT) != 0; scriptFlag[F] = v; }
        return v;
    }
    Info Get(long F)
    {
        Info r;
        if (infos.TryGetValue(F, out r)) return r;
        r = new Info(); r.Name = "?"; r.Mod = "?"; r.Line = 0;
        infos[F] = r;
        if (F == 0) return r;
        string fname = CStr(Q(F + FUNC_NAME), 200);
        long M = fname != null ? Q(F + FUNC_MODULE) : 0;
        if (fname == null || M == 0) return r;
        KeyValuePair<uint, string> hit;
        string cname = ClassMap(M).TryGetValue(F, out hit) ? ModdedSuffix.Replace(hit.Value, "") : "";
        r.Name = cname.Length > 0 ? cname + "." + fname : fname;
        r.IsScript = IsScript(F);
        if (r.IsScript)
        {
            string file; int line;
            FileLine(M, Q(F + FUNC_CODE), out file, out line);
            r.File = file; r.Line = line; r.Mod = ModOf(file);
        }
        else r.Mod = "native";
        return r;
    }
    string Where(long F)
    {
        Info i = Get(F);
        if (i.Mod == "native") return "[engine native]";
        return i.Mod + "  " + (i.File == null ? "?" : i.File.Replace('\\', '/')) + ":" + i.Line;
    }
    static void Bump(Dictionary<long, int> d, long k) { int v; d.TryGetValue(k, out v); d[k] = v + 1; }
    static void Bump(Dictionary<string, int> d, string k) { int v; d.TryGetValue(k, out v); d[k] = v + 1; }
    static List<KeyValuePair<long, int>> Sorted(Dictionary<long, int> d)
    {
        List<KeyValuePair<long, int>> l = new List<KeyValuePair<long, int>>(d);
        l.Sort(delegate (KeyValuePair<long, int> a, KeyValuePair<long, int> b) { return b.Value.CompareTo(a.Value); });
        return l;
    }
    static string Csv(string s)
    {
        if (s == null) return "";
        if (s.IndexOfAny(new char[] { ',', '"', '\n' }) < 0) return s;
        return "\"" + s.Replace("\"", "\"\"") + "\"";
    }

    // ---- the run --------------------------------------------------------------
    public static string Run(int pid, string exeName, double seconds, double hz, int top, double minRunMs, string outCsv)
    {
        DzScriptProfiler p = new DzScriptProfiler();
        return p.RunInner(pid, exeName, seconds, hz, top, minRunMs, outCsv);
    }

    string RunInner(int pid, string exeName, double seconds, double hz, int top, double minRunMs, string outCsv)
    {
        StringBuilder o = new StringBuilder();
        Process proc;
        long exeBase;
        try
        {
            proc = Process.GetProcessById(pid);
            exeBase = proc.MainModule.BaseAddress.ToInt64();
        }
        catch (Exception e)
        {
            return "cannot open pid " + pid + " (run this from an elevated PowerShell?): " + e.Message;
        }
        h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, false, pid);
        if (h == IntPtr.Zero) return "OpenProcess failed: " + Marshal.GetLastWin32Error();
        ctxRaw = Marshal.AllocHGlobal(CONTEXT_SIZE + 16);
        ctxBuf = (IntPtr)((ctxRaw.ToInt64() + 15) & ~15L);

        byte[] shape = new byte[8];
        if (!Read(exeBase + INTERP_LO, shape, 8) || !StructuralEq(shape, INTERP_SHAPE))
            return string.Format("the interpreter at +0x{0:X} does not look like the build this was read from; refusing", INTERP_LO);
        long ctx = Q(exeBase + CTX_GLOBAL);
        long cs = ctx != 0 ? Q(ctx + CTX_CALLSTACK) : 0;
        if (cs == 0 || Q(cs + CS_OWNER) != ctx)
            return string.Format("the script context at +0x{0:X} does not point at a call stack; refusing", CTX_GLOBAL);
        o.AppendFormat("pid {0}, {1} at 0x{2:X}; interpreter and script context match the known build\n", pid, exeName, exeBase);

        // the main thread: the one most often inside the exe during a short warm-up
        List<uint> tids = new List<uint>();
        foreach (ProcessThread t in proc.Threads) tids.Add((uint)t.Id);
        Dictionary<uint, int> warm = new Dictionary<uint, int>();
        for (int round = 0; round < 40; round++)
        {
            foreach (uint t in tids)
            {
                long r = Rip(t, false);
                if (r >= exeBase && r < exeBase + 0x1200000) { int v; warm.TryGetValue(t, out v); warm[t] = v + 1; }
            }
            System.Threading.Thread.Sleep(5);
        }
        uint mainTid = 0; int best = 0;
        foreach (KeyValuePair<uint, int> kv in warm) if (kv.Value > best) { best = kv.Value; mainTid = kv.Key; }
        foreach (uint t in tids)
            if (!warm.ContainsKey(t) && threads.ContainsKey(t) && threads[t] != IntPtr.Zero) { CloseHandle(threads[t]); threads[t] = IntPtr.Zero; }
        if (mainTid == 0) return "no thread is executing inside the exe";
        o.AppendFormat("main thread {0}; sampling {1:F0} s at {2:F0} Hz\n", mainTid, seconds, hz);

        long vlo = exeBase + VM_LO, vhi = exeBase + VM_HI;
        Dictionary<long, int> selfCnt = new Dictionary<long, int>(), nativeCnt = new Dictionary<long, int>(),
            inclCnt = new Dictionary<long, int>(), ownerCnt = new Dictionary<long, int>(), ownerNative = new Dictionary<long, int>();
        Dictionary<long, Dictionary<long, int>> callers = new Dictionary<long, Dictionary<long, int>>();
        List<KeyValuePair<int, long[]>> runs = new List<KeyValuePair<int, long[]>>();
        long[] runStack = null; int runN = 0;
        int total = 0, engine = 0, interp = 0, native = 0, vmEntry = 0;
        byte[] frames = new byte[MAX_DEPTH * FRAME_SIZE];
        double periodMs = 1000.0 / hz;
        timeBeginPeriod(1);
        napTimer = CreateWaitableTimerExW(IntPtr.Zero, IntPtr.Zero, 0x2 /* CREATE_WAITABLE_TIMER_HIGH_RESOLUTION */, 0x1F0003);
        Stopwatch all = Stopwatch.StartNew();
        Stopwatch one = new Stopwatch();
        try
        {
            while (all.Elapsed.TotalSeconds < seconds)
            {
                one.Restart();
                long rip = Rip(mainTid, true);
                long[] stack = null;
                if (rip != -1)
                {
                    uint depth = 0; bool have = false;
                    try
                    {
                        depth = U32(cs + CS_DEPTH);
                        have = depth > 0 && depth <= MAX_DEPTH && Read(cs + CS_FRAMES + FRAME_SIZE, frames, (int)depth * FRAME_SIZE);
                    }
                    finally { Release(mainTid); }
                    total++;
                    bool inVm = rip >= vlo && rip < vhi;
                    if (have)
                    {
                        List<long> fs = new List<long>();
                        for (int i = 0; i < depth; i++) { long F = BitConverter.ToInt64(frames, i * FRAME_SIZE + 8); if (F != 0) fs.Add(F); }
                        if (fs.Count > 0) stack = fs.ToArray();
                    }
                    if (stack != null)
                    {
                        long topF = stack[stack.Length - 1];
                        Bump(selfCnt, topF);
                        long owner = topF;
                        for (int i = stack.Length - 1; i >= 0; i--) if (IsScript(stack[i])) { owner = stack[i]; break; }
                        Bump(ownerCnt, owner);
                        if (inVm) interp++;
                        else { native++; Bump(nativeCnt, topF); Bump(ownerNative, owner); }
                        HashSet<long> seen = new HashSet<long>(stack);
                        foreach (long F in seen) Bump(inclCnt, F);
                        Dictionary<long, int> c;
                        if (!callers.TryGetValue(topF, out c)) { c = new Dictionary<long, int>(); callers[topF] = c; }
                        Bump(c, stack.Length > 1 ? stack[stack.Length - 2] : 0);
                    }
                    else
                    {
                        engine++;
                        if (inVm) vmEntry++;
                    }
                }
                if (SameStack(stack, runStack)) runN++;
                else
                {
                    if (runStack != null) runs.Add(new KeyValuePair<int, long[]>(runN, runStack));
                    runStack = stack; runN = 1;
                }
                double left = periodMs - one.Elapsed.TotalMilliseconds;
                if (left > 0.2) Nap(left);
            }
        }
        finally { timeEndPeriod(1); if (napTimer != IntPtr.Zero) CloseHandle(napTimer); }
        if (runStack != null) runs.Add(new KeyValuePair<int, long[]>(runN, runStack));
        double secs = all.Elapsed.TotalSeconds;

        o.AppendLine();
        o.AppendFormat("samples {0} over {1:F0} s ({2:F0}/s)\n", total, secs, total / Math.Max(1e-9, secs));
        o.AppendFormat("  {0,5:F1}%  engine only, no script on the stack (of which {1:F1}% entering/leaving the VM)\n", Pct(engine, total), Pct(vmEntry, total));
        o.AppendFormat("  {0,5:F1}%  interpreting script\n", Pct(interp, total));
        o.AppendFormat("  {0,5:F1}%  engine natives called from script\n", Pct(native, total));

        Dictionary<string, int> byMod = new Dictionary<string, int>(), byModNative = new Dictionary<string, int>();
        foreach (KeyValuePair<long, int> kv in ownerCnt)
        {
            string mod = Get(kv.Key).Mod;
            int v; byMod.TryGetValue(mod, out v); byMod[mod] = v + kv.Value;
            int nv; ownerNative.TryGetValue(kv.Key, out nv);
            int w; byModNative.TryGetValue(mod, out w); byModNative[mod] = w + nv;
        }
        List<KeyValuePair<string, int>> mods = new List<KeyValuePair<string, int>>(byMod);
        mods.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b) { return b.Value.CompareTo(a.Value); });
        o.AppendLine();
        o.AppendLine("script time by mod (the innermost script function's file; natives count for the script that called them):");
        foreach (KeyValuePair<string, int> kv in mods)
            o.AppendFormat("  {0,6:F2}%  {1,6}  {2,-24} ({3:F2}% of it in engine code)\n", Pct(kv.Value, total), kv.Value, kv.Key, Pct(byModNative[kv.Key], total));

        o.AppendLine();
        o.AppendLine("top functions on the script stack, self time:");
        o.AppendFormat("  {0,7} {1,7} {2,7}  {3}\n", "self", "engine", "incl", "function  (mod  file:line)");
        List<KeyValuePair<long, int>> selfSorted = Sorted(selfCnt);
        for (int i = 0; i < selfSorted.Count && i < top; i++)
        {
            long F = selfSorted[i].Key; int nv, iv;
            nativeCnt.TryGetValue(F, out nv); inclCnt.TryGetValue(F, out iv);
            o.AppendFormat("  {0,6:F2}% {1,6:F2}% {2,6:F2}%  {3}  ({4})\n", Pct(selfSorted[i].Value, total), Pct(nv, total), Pct(iv, total), Get(F).Name, Where(F));
        }

        o.AppendLine();
        o.AppendLine("top script functions, inclusive (anywhere on the stack):");
        List<KeyValuePair<long, int>> inclSorted = Sorted(inclCnt);
        for (int i = 0; i < inclSorted.Count && i < top; i++)
            o.AppendFormat("  {0,6:F2}%  {1}  ({2})\n", Pct(inclSorted[i].Value, total), Get(inclSorted[i].Key).Name, Get(inclSorted[i].Key).Mod);

        o.AppendLine();
        o.AppendLine("who calls the hottest functions:");
        for (int i = 0; i < selfSorted.Count && i < 10; i++)
        {
            long F = selfSorted[i].Key;
            List<string> parts = new List<string>();
            Dictionary<long, int> c;
            if (callers.TryGetValue(F, out c))
            {
                List<KeyValuePair<long, int>> cs2 = Sorted(c);
                for (int j = 0; j < cs2.Count && j < 3; j++)
                    parts.Add(string.Format("{0} {1:F0}%", cs2[j].Key == 0 ? "<engine>" : Get(cs2[j].Key).Name, 100.0 * cs2[j].Value / selfSorted[i].Value));
            }
            o.AppendFormat("  {0,-48} <- {1}\n", Get(F).Name, string.Join("; ", parts.ToArray()));
        }

        List<KeyValuePair<int, long[]>> longRuns = new List<KeyValuePair<int, long[]>>();
        foreach (KeyValuePair<int, long[]> r in runs) if (r.Key * periodMs >= minRunMs) longRuns.Add(r);
        longRuns.Sort(delegate (KeyValuePair<int, long[]> a, KeyValuePair<int, long[]> b) { return b.Key.CompareTo(a.Key); });
        o.AppendLine();
        if (longRuns.Count > 0)
        {
            o.AppendFormat("stretches where the script stack did not change for >= {0:F0} ms (a stall looks like this):\n", minRunMs);
            for (int i = 0; i < longRuns.Count && i < 10; i++)
            {
                long[] st = longRuns[i].Value;
                List<string> chain = new List<string>();
                for (int j = Math.Max(0, st.Length - 4); j < st.Length; j++) chain.Add(Get(st[j]).Name);
                o.AppendFormat("  {0,7:F0} ms  {1}\n", longRuns[i].Key * periodMs, string.Join(" > ", chain.ToArray()));
            }
        }
        else o.AppendFormat("no stretch >= {0:F0} ms with an unchanged script stack\n", minRunMs);

        if (!string.IsNullOrEmpty(outCsv))
        {
            using (StreamWriter w = new StreamWriter(outCsv, false, new UTF8Encoding(false)))
            {
                w.WriteLine(string.Format("# pid {0} samples {1} seconds {2:F0} hz {3:F0} engine {4} interp {5} native {6}", pid, total, secs, hz, engine, interp, native));
                w.WriteLine("function,mod,file,line,self,engine,inclusive,owner");
                foreach (KeyValuePair<long, int> kv in inclSorted)
                {
                    Info inf = Get(kv.Key); int sv, nv, ov;
                    selfCnt.TryGetValue(kv.Key, out sv); nativeCnt.TryGetValue(kv.Key, out nv); ownerCnt.TryGetValue(kv.Key, out ov);
                    w.WriteLine(string.Join(",", new string[] { Csv(inf.Name), Csv(inf.Mod), Csv(inf.File == null ? "" : inf.File.Replace('\\', '/')),
                        inf.Line.ToString(), sv.ToString(), nv.ToString(), kv.Value.ToString(), ov.ToString() }));
                }
            }
            o.AppendLine();
            o.AppendLine("written: " + outCsv);
        }
        foreach (KeyValuePair<uint, IntPtr> kv in threads) if (kv.Value != IntPtr.Zero) CloseHandle(kv.Value);
        CloseHandle(h);
        Marshal.FreeHGlobal(ctxRaw);
        return o.ToString();
    }
    static double Pct(int n, int total) { return 100.0 * n / Math.Max(1, total); }
    static bool StructuralEq(byte[] a, byte[] b) { if (a.Length != b.Length) return false; for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false; return true; }
    static bool SameStack(long[] a, long[] b)
    {
        if (a == null || b == null) return a == null && b == null;
        if (a.Length != b.Length) return false;
        for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
        return true;
    }
}
'@

if (-not ("DzScriptProfiler" -as [type])) {
    Add-Type -TypeDefinition $src -Language CSharp
}

if ($ProcessIdToSample -eq 0) {
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='$Exe'" -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) {
        Write-Host "no $Exe running"
        exit 1
    }
    # the server started with -server first (a diag client uses the same exe name)
    $pick = $procs | Sort-Object { if ($_.CommandLine -match '-server') { 0 } else { 1 } } | Select-Object -First 1
    $ProcessIdToSample = [int]$pick.ProcessId
}

$report = [DzScriptProfiler]::Run($ProcessIdToSample, $Exe, $Seconds, $Hz, $Top, $MinRunMs, $Out)
Write-Host $report
