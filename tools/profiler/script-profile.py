"""Script-level profiler and long-run monitor for the retail DayZ server.

Samples the server's main thread and, on every sample, reads the Enforce VM's
own call stack. Each sample therefore says which script function was running,
in which mod's file, and whether the time went into interpreting script or
into an engine native that the script called. Every other thread of the
process is sampled too (at a lower rate, addresses only), so a freeze that
does not live on the main thread -- a stuck network thread, say -- still
shows up, by thread, with the address it stood at and the CPU it used. No
debug build, no EnProfiler, no mod change: the process is only read, never
written.

Two ways to run it:

    python script-profile.py --seconds 60 --out lag-script
        one window, the report on the screen: for a problem that is
        happening right now.

    python script-profile.py --hours 24
        a monitor, for a problem nobody can be at the keyboard for. Every
        minute it appends one window to <out>.log and <out>.windows.csv,
        every thread's minute to <out>.threads.csv, every freeze of the main
        thread to <out>.hitches.csv, and rewrites the cumulative
        <out>.functions.csv and <out>.engine.csv. When the server restarts
        it waits for the new process and carries on. Closing it at any
        moment loses at most the current minute.

Only Python 3 is needed (ctypes from the standard library). The structures
below were read from DayZServer_x64.exe of 2026-08-13 (16,965,176 bytes); the
script checks two of them at start and refuses a build that does not match.

What is read (all offsets relative to the exe or to the objects named):
  [exe+0xF23610]          -> script context (the engine's own DumpStack reads it)
  [ctx+0x2C8]             -> call stack object; [cs+0x48] = depth
  frame i (1..depth)      pc = [cs+0x50+i*0x30], function = [cs+0x58+i*0x30]
  function F              [F+0x08] bytecode start, [F+0x40] module, [F+0x48] name,
                          [F+0x50] flags (bit 0x10: script, else engine native)
  module M                [M+0x28] name, [M+0x68]/[M+0x70] class table,
                          [M+0x78]->[+0x20] code start, [M+0x80] debug table
  debug table D           [D+0x00] file-name table, [D+0x30] entries
                          {u32 code offset, u16 line, u16 file}, [D+0x3C] count
"""

import argparse
import bisect
import collections
import csv
import ctypes
import ctypes.wintypes as wt
import os
import re
import struct
import subprocess
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
try:
    _GetThreadDescription = k32.GetThreadDescription      # Windows 10 1607+
    _GetThreadDescription.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    _GetThreadDescription.restype = ctypes.c_long
except AttributeError:
    _GetThreadDescription = None

TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPTHREAD = 0x4
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10
THREAD_ALL = 0x0002 | 0x0008 | 0x0040
PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400
SYNCHRONIZE = 0x100000
WAIT_TIMEOUT = 0x102
CONTEXT_CONTROL_INTEGER = 0x00100003
CONTEXT_SIZE = 1232
OFF_RIP = 0xF8
OFF_RSP = 0x98

# --- the engine build these were read from -------------------------------
INTERP_LO, INTERP_HI = 0x2E01E0, 0x2E3F66     # the interpreter loop
VM_LO, VM_HI = 0x2C5000, 0x2E9000             # the whole script VM
INTERP_SHAPE = bytes.fromhex("488bc44889581044")
CTX_GLOBAL = 0xF23610
CTX_CALLSTACK = 0x2C8
CS_OWNER = 0x40          # the call stack points back at its context
CS_DEPTH = 0x48
CS_FRAMES = 0x50         # frame i: pc at +0x50+i*0x30, F at +0x58+i*0x30
FRAME_SIZE = 0x30
FUNC_CODE = 0x08
FUNC_MODULE = 0x40
FUNC_NAME = 0x48
FUNC_FLAGS = 0x50
FUNC_FLAG_SCRIPT = 0x10  # clear on engine natives, whose [F+0x08] is C++ code
MOD_NAME = 0x28
MOD_CLASSES = 0x68
MOD_CLASS_COUNT = 0x70
MOD_CODE = 0x78
MOD_DEBUG = 0x80
CODE_START = 0x20
DBG_FILES = 0x00
DBG_ENTRIES = 0x30
DBG_COUNT = 0x3C
CLS_NAME = 0x10
CLS_FUNCS = 0x68
CLS_FUNC_COUNT = 0x74
MAX_DEPTH = 256
# When a mod says `modded class X`, the engine renames the class it replaces
# to 'X@<file index>#<line>' of the modding file. Cosmetic here: drop it.
MODDED_SUFFIX = re.compile(r"@\d+#\d+$")


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", wt.LONG),
                ("tpDeltaPri", wt.LONG), ("dwFlags", wt.DWORD)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", wt.LONG), ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", ctypes.c_void_p), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]


def _secs(f):
    return ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7


def processes_named(name):
    """pids of every process running `name`, from the process snapshot."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    out = []
    ok = k32.Process32FirstW(snap, ctypes.byref(pe))
    while ok:
        if pe.szExeFile.lower() == name.lower():
            out.append(pe.th32ProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(pe))
    k32.CloseHandle(snap)
    return out


def find_pids(name):
    """Every process running `name`; the one started with -server first (a
    Diag client uses the same exe name as its server)."""
    pids = processes_named(name)
    if len(pids) < 2:
        return pids
    ranked = {pid: 1 for pid in pids}
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='%s'\" | ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }" % name],
            stderr=subprocess.DEVNULL, timeout=30).decode("utf-8", "replace")
        for line in out.splitlines():
            pid, _, cmd = line.strip().partition("|")
            if pid.isdigit() and int(pid) in ranked and "-server" in cmd.lower():
                ranked[int(pid)] = 0
    except Exception:
        pass
    return sorted(pids, key=lambda pid: ranked[pid])


def modules_of(pid):
    """(base, size, name) of every module the process has loaded."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    out = []
    if snap == ctypes.c_void_p(-1).value:
        return out
    me = MODULEENTRY32W()
    me.dwSize = ctypes.sizeof(me)
    ok = k32.Module32FirstW(snap, ctypes.byref(me))
    while ok:
        out.append((me.modBaseAddr, me.modBaseSize, me.szModule))
        ok = k32.Module32NextW(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return out


def exe_base(pid, name):
    for base, size, mod in modules_of(pid):
        if mod.lower() == name.lower():
            return base
    return None


def threads_of(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32()
    te.dwSize = ctypes.sizeof(te)
    out = []
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            out.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    k32.CloseHandle(snap)
    return out


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | SYNCHRONIZE, False, pid)
        if not self.h:
            raise OSError("OpenProcess failed: %d" % ctypes.get_last_error())
        self.buf = ctypes.create_string_buffer(512)
        raw = ctypes.create_string_buffer(CONTEXT_SIZE + 16)
        a = ctypes.addressof(raw)
        self._raw = raw
        self.ctx = a + ((16 - a % 16) % 16)
        self.handles = {}
        self.rsp = 0

    def alive(self):
        return k32.WaitForSingleObject(self.h, 0) == WAIT_TIMEOUT

    def stats(self):
        pm = PROCESS_MEMORY_COUNTERS_EX()
        pm.cb = ctypes.sizeof(pm)
        psapi.GetProcessMemoryInfo(self.h, ctypes.byref(pm), pm.cb)
        hc = wt.DWORD(0)
        k32.GetProcessHandleCount(self.h, ctypes.byref(hc))
        ft = [wt.FILETIME() for _ in range(4)]
        k32.GetProcessTimes(self.h, *[ctypes.byref(f) for f in ft])
        return {"private_mb": pm.PrivateUsage / 1048576.0, "ws_mb": pm.WorkingSetSize / 1048576.0,
                "handles": hc.value, "cpu_s": _secs(ft[2]) + _secs(ft[3])}

    def read(self, addr, n):
        """Up to the shared buffer's size; readn() for anything larger."""
        got = ctypes.c_size_t(0)
        if not addr or n > len(self.buf) or not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), self.buf, n, ctypes.byref(got)) or got.value != n:
            return None
        return self.buf.raw[:n]

    def readn(self, addr, n):
        """Any size; a fresh buffer, for tables and frame windows."""
        if not addr or n <= 0:
            return None
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) or got.value != n:
            return None
        return buf.raw

    def q(self, addr):
        b = self.read(addr, 8)
        return struct.unpack("<Q", b)[0] if b else None

    def u32(self, addr):
        b = self.read(addr, 4)
        return struct.unpack("<I", b)[0] if b else None

    def cstr(self, addr, n=200):
        b = self.read(addr, n)
        if not b:
            return None
        s = b.split(b"\x00")[0]
        if not s or not all(32 <= c < 127 for c in s):
            return None
        return s.decode()

    def thread(self, tid):
        h = self.handles.get(tid)
        if h is None:
            h = k32.OpenThread(THREAD_ALL, False, tid) or 0
            self.handles[tid] = h
        return h

    def drop_thread(self, tid):
        h = self.handles.pop(tid, None)
        if h:
            k32.CloseHandle(h)

    def rip(self, tid, hold=False):
        """The thread's rip. With hold=True the thread stays suspended so the
        VM's call stack can be read consistently; call release() afterwards.
        The stack pointer of the last call is left in self.rsp."""
        h = self.thread(tid)
        if not h or k32.SuspendThread(h) == 0xFFFFFFFF:
            return None
        ok = False
        try:
            ctypes.memset(self.ctx, 0, CONTEXT_SIZE)
            ctypes.c_uint32.from_address(self.ctx + 0x30).value = CONTEXT_CONTROL_INTEGER
            if not k32.GetThreadContext(h, ctypes.c_void_p(self.ctx)):
                return None
            ok = True
            self.rsp = ctypes.c_uint64.from_address(self.ctx + OFF_RSP).value
            return ctypes.c_uint64.from_address(self.ctx + OFF_RIP).value
        finally:
            if not (ok and hold):
                k32.ResumeThread(h)

    def release(self, tid):
        h = self.handles.get(tid)
        if h:
            k32.ResumeThread(h)

    def thread_cpu(self, tid):
        """Kernel plus user seconds of a thread, or None."""
        h = self.thread(tid)
        if not h:
            return None
        ft = [wt.FILETIME() for _ in range(4)]
        if not k32.GetThreadTimes(h, *[ctypes.byref(f) for f in ft]):
            return None
        return _secs(ft[2]) + _secs(ft[3])

    def thread_name(self, tid):
        """The description a thread was given, if any (the engine names few)."""
        h = self.thread(tid)
        if not h or not _GetThreadDescription:
            return ""
        s = ctypes.c_wchar_p()
        if _GetThreadDescription(h, ctypes.byref(s)) < 0 or not s.value:
            return ""
        name = s.value
        k32.LocalFree(s)
        return name

    def close(self):
        for h in self.handles.values():
            if h:
                k32.CloseHandle(h)
        self.handles = {}
        k32.CloseHandle(self.h)


def mod_of(path):
    """Which mod a script file belongs to, from the path the compiler kept."""
    if not path:
        return "?"
    parts = path.replace("\\", "/").split("/")
    if parts[0] == "scripts":
        return "vanilla"
    if parts[0] == "JM" and len(parts) > 1:
        return "JM/" + parts[1]
    return parts[0]


class Names:
    """Function descriptor -> (Class.Function, mod, file, line), from the
    module's class tables and its debug table."""

    def __init__(self, p):
        self.p = p
        self.by_func = {}
        self.classes = {}
        self.debug = {}

    def class_map(self, M):
        if M in self.classes:
            return self.classes[M]
        p = self.p
        m = {}
        self.classes[M] = m
        arr = p.q(M + MOD_CLASSES)
        n = p.u32(M + MOD_CLASS_COUNT)
        if not arr or not n or not 0 < n < 50000:
            return m
        ptrs = p.readn(arr, n * 8)
        if not ptrs:
            return m
        for i in range(n):
            C = struct.unpack_from("<Q", ptrs, i * 8)[0]
            if not C:
                continue
            k = p.u32(C + CLS_FUNC_COUNT)
            fa = p.q(C + CLS_FUNCS)
            if not k or not fa or not 0 < k < 20000:
                continue
            fp = p.readn(fa, k * 8)
            if not fp:
                continue
            cname = p.cstr(p.q(C + CLS_NAME) or 0) or "?"
            for j in range(k):
                F = struct.unpack_from("<Q", fp, j * 8)[0]
                # A subclass's table repeats every inherited descriptor, so a
                # function appears in its defining class and in every class
                # below it. The defining class is the one with the FEWEST
                # functions among them: a subclass can only add.
                if F and (F not in m or k < m[F][0]):
                    m[F] = (k, cname)
        return m

    def debug_table(self, M):
        if M in self.debug:
            return self.debug[M]
        p = self.p
        entry = None
        self.debug[M] = entry
        code = p.q(M + MOD_CODE)
        dbg = p.q(M + MOD_DEBUG)
        if not code or not dbg:
            return None
        start = p.q(code + CODE_START)
        ents = p.q(dbg + DBG_ENTRIES)
        cnt = p.u32(dbg + DBG_COUNT)
        files = p.q(dbg + DBG_FILES)
        if not start or not ents or not cnt or not files or cnt > 2000000:
            return None
        raw = p.readn(ents, cnt * 8)
        if not raw:
            return None
        offs = [struct.unpack_from("<I", raw, i * 8)[0] for i in range(cnt)]
        lines = [struct.unpack_from("<H", raw, i * 8 + 4)[0] for i in range(cnt)]
        fidx = [struct.unpack_from("<H", raw, i * 8 + 6)[0] for i in range(cnt)]
        entry = (start, offs, lines, fidx, files, {})
        self.debug[M] = entry
        return entry

    def file_line(self, M, code):
        d = self.debug_table(M)
        if not d or not code:
            return None, 0
        start, offs, lines, fidx, files, fcache = d
        off = code - start
        if not 0 <= off < 0x7FFFFFFF:
            return None, 0
        i = bisect.bisect_right(offs, off) - 1
        if i < 0:
            return None, 0
        fi = fidx[i]
        if fi not in fcache:
            fcache[fi] = self.p.cstr(self.p.q(files + fi * 8) or 0, 260)
        return fcache[fi], lines[i]

    def get(self, F):
        if F in self.by_func:
            return self.by_func[F]
        p = self.p
        fname = p.cstr(p.q(F + FUNC_NAME) or 0) if F else None
        M = p.q(F + FUNC_MODULE) if fname else None
        if not fname or not M:
            r = ("?", "?", None, 0)
            self.by_func[F] = r
            return r
        hit = self.class_map(M).get(F)
        cname = MODDED_SUFFIX.sub("", hit[1]) if hit else ""   # no class: a global function
        full = "%s.%s" % (cname, fname) if cname else fname
        if (p.u32(F + FUNC_FLAGS) or 0) & FUNC_FLAG_SCRIPT:
            path, line = self.file_line(M, p.q(F + FUNC_CODE))
            r = (full, mod_of(path), path, line)
        else:
            r = (full, "native", None, 0)
        self.by_func[F] = r
        return r


class Counters:
    def __init__(self):
        self.self_cnt = collections.Counter()      # innermost function on the script stack
        self.native_cnt = collections.Counter()    # ... while the CPU was in engine code
        self.incl_cnt = collections.Counter()      # anywhere on the stack
        self.owner_cnt = collections.Counter()     # innermost SCRIPT function: natives count for their caller
        self.owner_native = collections.Counter()
        self.callers = collections.defaultdict(collections.Counter)
        self.engine_off = collections.Counter()    # exe offsets of samples with no script on the stack
        self.engine_mod = collections.Counter()    # ... and the module when they were outside the exe
        self.total = self.engine = self.interp = self.native = self.vm_entry = 0

    def add(self, o):
        for name in ("self_cnt", "native_cnt", "incl_cnt", "owner_cnt", "owner_native", "engine_off", "engine_mod"):
            getattr(self, name).update(getattr(o, name))
        for F, c in o.callers.items():
            self.callers[F].update(c)
        for name in ("total", "engine", "interp", "native", "vm_entry"):
            setattr(self, name, getattr(self, name) + getattr(o, name))

    def pct(self, n):
        return 100.0 * n / max(1, self.total)


class OtherThread:
    """What is known about one non-main thread: where it was, and the longest
    time it stood at one exe address (a spin, a lock, one long call)."""

    def __init__(self):
        self.n = 0
        self.exe = 0
        self.offs = collections.Counter()
        self.mods = collections.Counter()
        self.stall_rip = None
        self.stall_first = 0.0
        self.stall_ms = 0.0
        self.stall_at_rip = 0
        self.stall_at = 0.0

    def add(self, o):
        self.n += o.n
        self.exe += o.exe
        self.offs.update(o.offs)
        self.mods.update(o.mods)
        if o.stall_ms > self.stall_ms:
            self.stall_ms, self.stall_at_rip, self.stall_at = o.stall_ms, o.stall_at_rip, o.stall_at


class Sampler:
    """One server process: samples, window and cumulative counters, and the
    stretches of uninterrupted work that a player feels as a freeze."""

    def __init__(self, p, pid, base, exe_size, mods, cs, main_tid, hz, threads_hz, min_run_ms):
        self.p = p
        self.pid = pid
        self.base = base
        self.exe_hi = base + exe_size
        self.mods = mods
        self.cs = cs
        self.main_tid = main_tid
        self.period = 1.0 / hz
        self.every = int(round(hz / threads_hz)) if threads_hz > 0 else 0
        self.tick = 0
        self.min_run_ms = min_run_ms
        self.vlo, self.vhi = base + VM_LO, base + VM_HI
        self.names = Names(p)
        self.win = Counters()
        self.cum = Counters()
        self.script_flag = {}
        self.run = None
        self.hitches_win = []
        self.others = {}          # tid -> OtherThread, this window
        self.others_cum = {}      # tid -> OtherThread, the whole segment
        self.cpu_prev = {}
        self.thread_names = {}
        self.refresh_threads()

    def refresh_threads(self):
        """The other threads come and go; keep the set current once a window."""
        now = set(threads_of(self.pid))
        now.discard(self.main_tid)
        for tid in list(self.others):
            if tid not in now:
                del self.others[tid]
                self.p.drop_thread(tid)
                self.cpu_prev.pop(tid, None)
        for tid in now:
            if tid not in self.others:
                self.others[tid] = OtherThread()
                self.thread_names[tid] = self.p.thread_name(tid)
                self.cpu_prev[tid] = self.p.thread_cpu(tid)

    def module_of(self, addr):
        for b, s, n in self.mods:
            if b <= addr < b + s:
                return n
        return "?"

    def is_script(self, F):
        v = self.script_flag.get(F)
        if v is None:
            v = self.script_flag[F] = bool((self.p.u32(F + FUNC_FLAGS) or 0) & FUNC_FLAG_SCRIPT)
        return v

    def exe_caller(self, rsp):
        """For a sample outside the exe: the nearest exe address on the stack,
        i.e. who made the call that has not come back."""
        b = self.p.readn(rsp, 0x400)
        if not b:
            return 0
        for off in range(0, len(b) - 7, 8):
            v = struct.unpack_from("<Q", b, off)[0]
            if self.base <= v < self.exe_hi:
                return v - self.base
        return 0

    def close_run(self):
        r = self.run
        if r is None:
            return
        r["ms"] = (r["last"] - r["first"] + self.period) * 1000.0
        if r["ms"] >= self.min_run_ms:
            self.hitches_win.append(r)
        self.run = None

    def sample_others(self, t0):
        p = self.p
        for tid, o in self.others.items():
            rip = p.rip(tid)
            if rip is None:
                continue
            o.n += 1
            if self.base <= rip < self.exe_hi:
                off = rip - self.base
                o.exe += 1
                o.offs[off] += 1
                if o.stall_rip == off:
                    ms = (t0 - o.stall_first + self.period * self.every) * 1000.0
                    if ms > o.stall_ms:
                        o.stall_ms, o.stall_at_rip = ms, off
                else:
                    o.stall_rip, o.stall_first, o.stall_at = off, t0, time.time()
            else:
                o.mods[self.module_of(rip)] += 1
                o.stall_rip = None

    def sample(self):
        """One sample. False when the main thread could not be read (process gone)."""
        p = self.p
        t0 = time.perf_counter()
        rip = p.rip(self.main_tid, hold=True)
        if rip is None:
            return False
        rsp = p.rsp
        try:
            depth = p.u32(self.cs + CS_DEPTH) or 0
            frames = p.readn(self.cs + CS_FRAMES + FRAME_SIZE, depth * FRAME_SIZE) if 0 < depth <= MAX_DEPTH else None
        finally:
            p.release(self.main_tid)
        w = self.win
        w.total += 1
        in_vm = self.vlo <= rip < self.vhi
        in_exe = self.base <= rip < self.exe_hi
        stack = ()
        if frames:
            stack = tuple(f for f in (struct.unpack_from("<Q", frames, i * FRAME_SIZE + 8)[0] for i in range(depth)) if f)
        if stack:
            top = stack[-1]
            w.self_cnt[top] += 1
            owner = top
            for F in reversed(stack):
                if self.is_script(F):
                    owner = F
                    break
            w.owner_cnt[owner] += 1
            if in_vm:
                w.interp += 1
            else:
                w.native += 1
                w.native_cnt[top] += 1
                w.owner_native[owner] += 1
            for F in set(stack):
                w.incl_cnt[F] += 1
            w.callers[top][stack[-2] if len(stack) > 1 else 0] += 1
            kind, key, spot = "script", stack[0], top
        else:
            w.engine += 1
            if in_vm:
                w.vm_entry += 1
            if in_exe:
                w.engine_off[rip - self.base] += 1
                kind, key, spot = "engine", None, rip - self.base
            else:
                kind = self.module_of(rip)
                w.engine_mod[kind] += 1
                key, spot = None, self.exe_caller(rsp)
        # A stretch is the main thread doing one thing without coming back to
        # the frame loop: script entered from one root function, engine code
        # with no script on the stack, or a call into another module that has
        # not returned. A long one is what a player feels as a freeze.
        r = self.run
        if r and r["kind"] == kind and r["key"] == key:
            r["n"] += 1
            r["last"] = t0
        else:
            self.close_run()
            self.run = r = {"kind": kind, "key": key, "n": 1, "first": t0, "last": t0,
                            "at": time.time(), "spots": collections.Counter()}
        r["spots"][spot] += 1
        self.tick += 1
        if self.every and self.tick % self.every == 0:
            self.sample_others(t0)
        dt = time.perf_counter() - t0
        if dt < self.period:
            time.sleep(self.period - dt)
        return True

    def describe(self, r):
        names = self.names
        if r["kind"] == "script":
            root = names.get(r["key"])
            inner = ", ".join("%s %.0f%%" % (names.get(F)[0], 100.0 * c / r["n"]) for F, c in r["spots"].most_common(3))
            return "script entered at %s (%s); inside: %s" % (root[0], root[1], inner)
        if r["kind"] == "engine":
            offs = ", ".join("+0x%X %.0f%%" % (o, 100.0 * c / r["n"]) for o, c in r["spots"].most_common(3))
            return "engine, no script on the stack; at %s" % offs
        offs = ", ".join("+0x%X %.0f%%" % (o, 100.0 * c / r["n"]) for o, c in r["spots"].most_common(2) if o)
        return "in %s, a wait or a system call that did not return; called from %s" % (r["kind"], offs or "?")

    def where(self, F):
        nm, mod, path, line = self.names.get(F)
        if mod == "native":
            return "[engine native]"
        return "%s  %s:%d" % (mod, (path or "?").replace("\\", "/"), line)

    def by_mod(self, c):
        mods = collections.Counter()
        mods_native = collections.Counter()
        for F, n in c.owner_cnt.items():
            mod = self.names.get(F)[1]
            mods[mod] += n
            mods_native[mod] += c.owner_native.get(F, 0)
        return mods, mods_native

    def tname(self, tid):
        n = self.thread_names.get(tid) or ""
        return " " + n if n else ""

    # ---- reports ----------------------------------------------------------
    def window_lines(self, stamp, seconds, hitches, stats, cpu_pct, top=8):
        """The one-minute block for the log, the row for windows.csv and the
        rows for threads.csv."""
        w = self.win
        pct = w.pct
        hit_ms = sum(r["ms"] for r in hitches)
        max_ms = max([r["ms"] for r in hitches] or [0])
        mods, _ = self.by_mod(w)
        head = ("%s  window %.0f s  %d samples | engine %.1f%%  script %.1f%%  natives %.1f%% | "
                "hitches %d, %.0f ms, max %.0f ms | private %.0f MB  ws %.0f MB  handles %d  threads %d  cpu %.0f%%" % (
                    stamp, seconds, w.total, pct(w.engine), pct(w.interp), pct(w.native),
                    len(hitches), hit_ms, max_ms, stats["private_mb"], stats["ws_mb"], stats["handles"], len(self.others) + 1, cpu_pct))
        mod_txt = "  ".join("%s %.1f%%" % (m, pct(c)) for m, c in mods.most_common(6))
        tops = w.self_cnt.most_common(top)
        top_txt = " | ".join("%s %.1f%%" % (self.names.get(F)[0], pct(c)) for F, c in tops)
        lines = [head, "   mods: " + (mod_txt or "-"), "   top:  " + (top_txt or "-")]
        for r in sorted(hitches, key=lambda r: -r["ms"])[:10]:
            lines.append("   hitch %s  %6.0f ms  %s" % (time.strftime("%H:%M:%S", time.localtime(r["at"])), r["ms"], self.describe(r)))
        # the other threads: their cpu this window, where they were, whether one stood still
        trows = []
        entries = []
        for tid, o in self.others.items():
            cpu = self.p.thread_cpu(tid)
            prev = self.cpu_prev.get(tid)
            cpu_ms = (cpu - prev) * 1000.0 if (cpu is not None and prev is not None) else 0.0
            if cpu is not None:
                self.cpu_prev[tid] = cpu
            exe_pct = 100.0 * o.exe / max(1, o.n)
            top_s = ";".join("+0x%X=%.1f" % (off, 100.0 * c / max(1, o.n)) for off, c in o.offs.most_common(3))
            mod_s = ";".join("%s=%.1f" % (m, 100.0 * c / max(1, o.n)) for m, c in o.mods.most_common(2))
            trows.append([stamp, tid, self.thread_names.get(tid, ""), o.n, "%.0f" % exe_pct, "%.0f" % cpu_ms, top_s, mod_s, "%.0f" % o.stall_ms])
            entries.append((cpu_ms, tid, exe_pct, o))
        entries.sort(key=lambda e: -e[0])
        busy = sum(1 for e in entries if e[2] >= 10)
        parts = []
        for cpu_ms, tid, exe_pct, o in entries[:3]:
            top1 = o.offs.most_common(1)
            parts.append("tid %d%s cpu %.0f ms, exe %.0f%%%s" % (tid, self.tname(tid), cpu_ms, exe_pct, (" at +0x%X" % top1[0][0]) if top1 else ""))
        lines.append("   threads: %d others, %d of them busy in the exe; top by cpu: %s" % (len(entries), busy, "; ".join(parts) or "-"))
        for tid, o in sorted(self.others.items(), key=lambda kv: -kv[1].stall_ms)[:5]:
            if o.stall_ms >= self.min_run_ms:
                lines.append("   thread %d%s stood at +0x%X for %.0f ms (from %s)" % (
                    tid, self.tname(tid), o.stall_at_rip, o.stall_ms, time.strftime("%H:%M:%S", time.localtime(o.stall_at))))
        row = [stamp, w.total, "%.1f" % pct(w.engine), "%.1f" % pct(w.interp), "%.1f" % pct(w.native),
               len(hitches), "%.0f" % hit_ms, "%.0f" % max_ms, "%.0f" % stats["private_mb"], "%.0f" % stats["ws_mb"],
               stats["handles"], len(self.others) + 1, "%.0f" % cpu_pct,
               ";".join("%s=%.1f" % (m, pct(c)) for m, c in mods.most_common(6)),
               ";".join("%s=%.1f" % (self.names.get(F)[0], pct(c)) for F, c in tops[:5])]
        return lines, row, trows

    def rotate_window(self):
        """Fold the window into the cumulative counters; return the window's hitches."""
        self.cum.add(self.win)
        self.win = Counters()
        for tid, o in self.others.items():
            self.others_cum.setdefault(tid, OtherThread()).add(o)
            self.others[tid] = OtherThread()
        self.refresh_threads()
        hitches, self.hitches_win = self.hitches_win, []
        return hitches

    def report_lines(self, c, top, all_hitches):
        pct = c.pct
        names = self.names
        out = []
        out.append("main thread: %d samples" % c.total)
        out.append("  %5.1f%%  engine only, no script on the stack (of which %.1f%% entering/leaving the VM)" % (pct(c.engine), pct(c.vm_entry)))
        out.append("  %5.1f%%  interpreting script" % pct(c.interp))
        out.append("  %5.1f%%  engine natives called from script" % pct(c.native))
        mods, mods_native = self.by_mod(c)
        out.append("")
        out.append("script time by mod (the innermost script function's file; natives count for the script that called them):")
        for m, n in mods.most_common():
            out.append("  %6.2f%%  %6d  %-24s (%.2f%% of it in engine code)" % (pct(n), n, m, pct(mods_native[m])))
        out.append("")
        out.append("top functions on the script stack, self time:")
        out.append("  %7s %7s %7s  %s" % ("self", "engine", "incl", "function  (mod  file:line)"))
        for F, n in c.self_cnt.most_common(top):
            out.append("  %6.2f%% %6.2f%% %6.2f%%  %s  (%s)" % (pct(n), pct(c.native_cnt.get(F, 0)), pct(c.incl_cnt.get(F, 0)), names.get(F)[0], self.where(F)))
        out.append("")
        out.append("top script functions, inclusive (anywhere on the stack):")
        for F, n in c.incl_cnt.most_common(top):
            out.append("  %6.2f%%  %s  (%s)" % (pct(n), names.get(F)[0], names.get(F)[1]))
        out.append("")
        out.append("who calls the hottest functions:")
        for F, n in c.self_cnt.most_common(10):
            parts = ["%s %.0f%%" % (names.get(C)[0] if C else "<engine>", 100.0 * k / n) for C, k in c.callers[F].most_common(3)]
            out.append("  %-48s <- %s" % (names.get(F)[0], "; ".join(parts)))
        out.append("")
        if all_hitches:
            out.append("stretches >= %.0f ms where the main thread stayed in one piece of work (what a player feels as a freeze): %d, %.0f ms in all" % (
                self.min_run_ms, len(all_hitches), sum(r["ms"] for r in all_hitches)))
            for r in sorted(all_hitches, key=lambda r: -r["ms"])[:15]:
                out.append("  %s  %7.0f ms  %s" % (time.strftime("%H:%M:%S", time.localtime(r["at"])), r["ms"], self.describe(r)))
            out.append("  (engine addresses are named by resolve-samples.py against the same exe)")
        else:
            out.append("no stretch >= %.0f ms in one piece of work on the main thread: nothing here would be felt as a freeze" % self.min_run_ms)
        engine_only = sum(c.engine_off.values()) + sum(c.engine_mod.values())
        if engine_only:
            out.append("")
            out.append("main-thread engine time with no script on the stack (%.1f%%), by place:" % pct(engine_only))
            for m, n in c.engine_mod.most_common(4):
                out.append("  %6.2f%%  [module] %s" % (pct(n), m))
            for o, n in c.engine_off.most_common(8):
                out.append("  %6.2f%%  +0x%X" % (pct(n), o))
        if self.others_cum:
            out.append("")
            out.append("other threads (samples at 1/%d of the main thread's rate; 'exe' = busy in the engine, the rest is waiting in system code):" % max(1, self.every))
            ranked = sorted(self.others_cum.items(), key=lambda kv: -kv[1].exe)
            for tid, o in ranked[:10]:
                top_s = ", ".join("+0x%X %.1f%%" % (off, 100.0 * n / max(1, o.n)) for off, n in o.offs.most_common(3))
                mod_s = ", ".join("%s %.0f%%" % (m, 100.0 * n / max(1, o.n)) for m, n in o.mods.most_common(1))
                out.append("  tid %-6d%-18s %6d samples  exe %5.1f%%  %s%s" % (
                    tid, self.tname(tid), o.n, 100.0 * o.exe / max(1, o.n), top_s or "-", ("  | " + mod_s) if mod_s else ""))
            stalls = [(o.stall_ms, tid, o) for tid, o in self.others_cum.items() if o.stall_ms >= self.min_run_ms]
            for ms, tid, o in sorted(stalls, key=lambda s: -s[0])[:8]:
                out.append("  thread %d%s stood at +0x%X for %.0f ms at %s" % (
                    tid, self.tname(tid), o.stall_at_rip, ms, time.strftime("%H:%M:%S", time.localtime(o.stall_at))))
        return out

    def write_csvs(self, prefix, c, seg, all_hitches):
        names = self.names
        with open(prefix + ".functions.csv", "w", encoding="utf-8", newline="") as fh:
            fh.write("# pid %d segment %d samples %d engine %d interp %d native %d\n" % (self.pid, seg, c.total, c.engine, c.interp, c.native))
            for r in sorted(all_hitches, key=lambda r: -r["ms"])[:40]:
                fh.write("# hitch %s %.0f ms: %s\n" % (time.strftime("%H:%M:%S", time.localtime(r["at"])), r["ms"], self.describe(r)))
            w = csv.writer(fh)
            w.writerow(["function", "mod", "file", "line", "self", "engine", "inclusive", "owner"])
            for F, n in c.incl_cnt.most_common():
                nm, mod, path, line = names.get(F)
                w.writerow([nm, mod, (path or "").replace("\\", "/"), line, c.self_cnt.get(F, 0), c.native_cnt.get(F, 0), n, c.owner_cnt.get(F, 0)])
        with open(prefix + ".engine.csv", "w", encoding="utf-8", newline="") as fh:
            # the collect-samples.ps1 format, so resolve-samples.py names these
            fh.write("# dayz script-profile: the main thread's engine-only samples, then every other thread at 1/%d of its rate\n" % max(1, self.every))
            fh.write("# exe_base=0x%X pid=%d segment=%d main_tid=%d samples=%d\n" % (self.base, self.pid, seg, self.main_tid, c.total))
            fh.write("tid,kind,where,count\n")
            for o, n in c.engine_off.most_common():
                fh.write("%d,exe,%X,%d\n" % (self.main_tid, o, n))
            for m, n in c.engine_mod.most_common():
                fh.write("%d,module,%s,%d\n" % (self.main_tid, m, n))
            for tid, o in self.others_cum.items():
                for off, n in o.offs.most_common():
                    fh.write("%d,exe,%X,%d\n" % (tid, off, n))
                for m, n in o.mods.most_common():
                    fh.write("%d,module,%s,%d\n" % (tid, m, n))


WINDOW_COLUMNS = ["time", "segment", "pid", "samples", "engine_pct", "interp_pct", "native_pct", "hitches", "hitch_ms",
                  "max_hitch_ms", "private_mb", "ws_mb", "handles", "threads", "cpu_pct", "mods", "top"]
THREAD_COLUMNS = ["time", "segment", "pid", "tid", "name", "samples", "exe_pct", "cpu_ms", "top", "module", "stall_ms"]


class Files:
    """The monitor's output files; every write is a full open/append/close so
    a closed window loses nothing."""

    def __init__(self, prefix):
        self.prefix = prefix
        self.log = prefix + ".log"
        self.windows = prefix + ".windows.csv"
        self.hitches = prefix + ".hitches.csv"
        self.threads = prefix + ".threads.csv"
        for path, header in ((self.windows, WINDOW_COLUMNS), (self.hitches, ["time", "segment", "pid", "ms", "kind", "description"]),
                             (self.threads, THREAD_COLUMNS)):
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    csv.writer(fh).writerow(header)

    def say(self, text):
        with open(self.log, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")

    def rows(self, path, rows):
        with open(path, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            for row in rows:
                w.writerow(row)


def attach(pid, exe_name, out):
    """Open the process, check the build, find the main thread. Returns the
    pieces a Sampler needs, or a string saying why not ('fatal: ...' for a
    build that does not match; anything else is worth retrying)."""
    base = exe_base(pid, exe_name)
    if not base:
        return "cannot see the modules of pid %d (run this elevated, like the server)" % pid
    p = Proc(pid)
    shape = p.read(base + INTERP_LO, 8)
    if shape != INTERP_SHAPE:
        p.close()
        return "fatal: the interpreter at +0x%X does not look like the build this was read from (%s); refusing" % (INTERP_LO, shape.hex() if shape else None)
    ctx = p.q(base + CTX_GLOBAL)
    cs = p.q(ctx + CTX_CALLSTACK) if ctx else None
    if not cs or p.q(cs + CS_OWNER) != ctx:
        # For the first half-minute after the server reports ready the
        # context is not wired up yet; a monitor simply comes back later.
        p.close()
        return "the script context at +0x%X does not point at a call stack yet (still loading?)" % CTX_GLOBAL
    out("pid %d, %s at 0x%X; interpreter and script context match the known build" % (pid, exe_name, base))
    # the main thread: the one most often inside the exe during a short warm-up
    mods = modules_of(pid)
    exe_size = next((s for b, s, n in mods if b == base), 0x1200000)
    tids = threads_of(pid)
    warm = collections.Counter()
    for _ in range(40):
        for t in tids:
            r = p.rip(t)
            if r and base <= r < base + exe_size:
                warm[t] += 1
        time.sleep(0.005)
    if not warm:
        p.close()
        return "no thread is executing inside the exe (is the server still loading?)"
    main_tid = warm.most_common(1)[0][0]
    out("main thread %d" % main_tid)
    return p, base, exe_size, mods, cs, main_tid


def run_segment(a, pid, seg, deadline, files):
    """Sample one server process until it exits or the deadline passes.
    Returns 'fatal', 'retry', 'exited' or 'done'."""
    def out(text):
        if files:
            files.say(text)
        print(text, flush=True)

    got = attach(pid, a.exe, out)
    if isinstance(got, str):
        out(got)
        return "fatal" if got.startswith("fatal") else "retry"
    p, base, exe_size, mods, cs, main_tid = got
    s = Sampler(p, pid, base, exe_size, mods, cs, main_tid, a.hz, a.threads_hz, a.min_run_ms)
    window = a.window if files else max(1.0, a.seconds)
    all_hitches = []
    stats0 = p.stats()
    wall0 = time.time()
    next_flush = wall0 + window
    exited = False
    stopped = False
    try:
        while time.time() < deadline:
            if not s.sample():
                if not p.alive():
                    exited = True
                    break
                time.sleep(0.05)
            if s.win.total % 400 == 0 and not p.alive():
                exited = True
                break
            if time.time() >= next_flush:
                s.close_run()
                hit = s.hitches_win
                stats = p.stats()
                wall = time.time()
                cpu_pct = 100.0 * (stats["cpu_s"] - stats0["cpu_s"]) / max(1e-9, wall - wall0)
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                lines, row, trows = s.window_lines(stamp, wall - wall0, hit, stats, cpu_pct)
                if files:
                    files.say("\n".join(lines))
                    files.rows(files.windows, [[stamp, seg, pid] + row[1:]])
                    files.rows(files.hitches, [[time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["at"])), seg, pid, "%.0f" % r["ms"], r["kind"], s.describe(r)] for r in hit])
                    files.rows(files.threads, [[t[0], seg, pid] + t[1:] for t in trows])
                    print(lines[0], flush=True)
                all_hitches.extend(s.rotate_window())
                if files:
                    s.write_csvs(files.prefix, s.cum, seg, all_hitches)
                stats0, wall0 = stats, wall
                next_flush = wall + window
    except KeyboardInterrupt:
        out("stopped by the user")
        stopped = True
    s.close_run()
    all_hitches.extend(s.rotate_window())
    c = s.cum
    report = s.report_lines(c, a.top, all_hitches)
    if files:
        files.say("")
        files.say("==== segment %d, pid %d: %s ====" % (seg, pid, "the server exited" if exited else "end of run"))
        files.say("\n".join(report))
        s.write_csvs(files.prefix, c, seg, all_hitches)
        print("segment %d written to %s.*" % (seg, files.prefix), flush=True)
    else:
        print()
        print("\n".join(report))
        if a.out:
            s.write_csvs(a.out, c, seg, all_hitches)
            print()
            print("written: %s.functions.csv and %s.engine.csv" % (a.out, a.out))
    p.close()
    if stopped:
        return "done"
    return "exited" if exited else "done"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pid", type=int, default=0, help="server process id (default: the DayZServer_x64.exe started with -server)")
    ap.add_argument("--exe", default="DayZServer_x64.exe")
    ap.add_argument("--seconds", type=float, default=0, help="sample this long and report on the screen (a one-window run)")
    ap.add_argument("--hours", type=float, default=24, help="monitor this long, one window per minute into files (the default mode)")
    ap.add_argument("--window", type=float, default=60, help="seconds per window in monitor mode")
    ap.add_argument("--hz", type=float, default=200, help="main-thread samples per second")
    ap.add_argument("--threads-hz", type=float, default=50, help="samples per second of every other thread (0 = only the main thread)")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--min-run-ms", type=float, default=150, help="report stretches where a thread stayed in one piece of work at least this long")
    ap.add_argument("--out", default="", help="file prefix; monitor mode default: script-profile-<date> in the current directory")
    a = ap.parse_args()

    try:
        ctypes.WinDLL("winmm").timeBeginPeriod(1)
    except Exception:
        pass

    short = a.seconds > 0
    files = None
    if not short:
        prefix = a.out or ("script-profile-" + time.strftime("%Y%m%d-%H%M"))
        files = Files(prefix)
        files.say("==== script-profile monitor started %s: %.1f h, %.0f s windows, %.0f Hz main thread, %.0f Hz other threads, stretch threshold %.0f ms ====" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), a.hours, a.window, a.hz, a.threads_hz, a.min_run_ms))
        print("monitoring %s for %.1f h; files: %s.log / .windows.csv / .threads.csv / .hitches.csv / .functions.csv / .engine.csv" % (a.exe, a.hours, prefix), flush=True)
        print("close this window to stop; nothing is lost but the current minute", flush=True)
    deadline = time.time() + (a.seconds if short else a.hours * 3600)
    seg = 0
    waiting = False
    while time.time() < deadline:
        pid = a.pid if (a.pid and seg == 0) else (find_pids(a.exe) or [0])[0]
        if not pid:
            if short:
                print("no %s running" % a.exe)
                return 1
            if not waiting:
                files.say("%s  waiting for %s to start" % (time.strftime("%Y-%m-%d %H:%M:%S"), a.exe))
                print("waiting for %s ..." % a.exe, flush=True)
                waiting = True
            time.sleep(10)
            continue
        waiting = False
        try:
            rc = run_segment(a, pid, seg + 1, deadline, files)
        except OSError as e:
            rc = "retry"
            (files.say if files else print)("pid %d: %s" % (pid, e))
        if rc == "fatal" or (short and rc != "done"):
            return 1
        if rc == "done":
            return 0
        if rc == "retry":
            # not attachable yet (loading, or a Diag client took the name): try again in a bit
            time.sleep(10)
            continue
        seg += 1
        files.say("%s  the server (pid %d) is gone; waiting for the next one" % (time.strftime("%Y-%m-%d %H:%M:%S"), pid))
        print("server pid %d gone; waiting for the next one ..." % pid, flush=True)
        time.sleep(15)
    return 0


if __name__ == "__main__":
    sys.exit(main())
