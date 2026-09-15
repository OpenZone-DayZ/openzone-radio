"""Script-level profiler for the retail DayZ server (DayZServer_x64.exe).

Samples the server's main thread and, on every sample, reads the Enforce VM's
own call stack. Each sample therefore says which script function was running,
in which mod's file, and whether the time went into interpreting script or
into an engine native that the script called. No debug build, no EnProfiler,
no mod change: the process is only read, never written.

    python script-profile.py --seconds 60 --hz 200 --out script-profile.csv

Only Python 3 is needed (ctypes from the standard library). The structures
below were read from DayZServer_x64.exe of 2026-08-13 (16,965,176 bytes); the
script checks two of them at start and refuses a build that does not match.

What is read (all offsets relative to the exe or to the objects named):
  [exe+0xF23610]          -> script context (the engine's own DumpStack reads it)
  [ctx+0x2C8]             -> call stack object; [cs+0x48] = depth
  frame i (1..depth)      pc = [cs+0x50+i*0x30], function = [cs+0x58+i*0x30]
  function F              [F+0x08] bytecode start, [F+0x40] module, [F+0x48] name
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
import re
import struct
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPTHREAD = 0x4
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10
THREAD_ALL = 0x0002 | 0x0008 | 0x0040
PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400
CONTEXT_CONTROL_INTEGER = 0x00100003
CONTEXT_SIZE = 1232
OFF_RIP = 0xF8

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


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", ctypes.c_void_p), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


def find_pids(name):
    """Every process running `name`; the one started with -server first."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["wmic", "process", "where", "name='%s'" % name, "get", "ProcessId,CommandLine", "/format:csv"],
            stderr=subprocess.DEVNULL).decode("utf-8", "replace")
    except Exception:
        out = ""
    ranked = []
    for line in out.splitlines():
        parts = line.strip().split(",")
        if len(parts) < 3 or not parts[-1].isdigit():
            continue
        cmd = ",".join(parts[1:-1]).lower()
        ranked.append((0 if "-server" in cmd else 1, int(parts[-1])))
    return [pid for _, pid in sorted(ranked)]


def exe_base(pid, name):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == ctypes.c_void_p(-1).value:
        return None
    me = MODULEENTRY32W()
    me.dwSize = ctypes.sizeof(me)
    base = None
    ok = k32.Module32FirstW(snap, ctypes.byref(me))
    while ok:
        if me.szModule.lower() == name.lower():
            base = me.modBaseAddr
            break
        ok = k32.Module32NextW(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return base


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
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.h:
            raise OSError("OpenProcess failed: %d" % ctypes.get_last_error())
        self.buf = ctypes.create_string_buffer(256)
        raw = ctypes.create_string_buffer(CONTEXT_SIZE + 16)
        a = ctypes.addressof(raw)
        self._raw = raw
        self.ctx = a + ((16 - a % 16) % 16)
        self.handles = {}

    def read(self, addr, n):
        got = ctypes.c_size_t(0)
        if not addr or not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), self.buf, n, ctypes.byref(got)) or got.value != n:
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

    def rip(self, tid, hold=False):
        """The thread's rip. With hold=True the thread stays suspended so the
        VM's call stack can be read consistently; call release() afterwards."""
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
            return ctypes.c_uint64.from_address(self.ctx + OFF_RIP).value
        finally:
            if not (ok and hold):
                k32.ResumeThread(h)

    def release(self, tid):
        h = self.handles.get(tid)
        if h:
            k32.ResumeThread(h)


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
        fname = p.cstr(p.q(F + FUNC_NAME) or 0)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pid", type=int, default=0, help="server process id (default: the DayZServer_x64.exe started with -server)")
    ap.add_argument("--exe", default="DayZServer_x64.exe")
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--hz", type=float, default=200)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--min-run-ms", type=float, default=100, help="report stretches where the script stack did not change for at least this long")
    ap.add_argument("--out", default="", help="write every function's counts to this CSV")
    a = ap.parse_args()

    pid = a.pid or (find_pids(a.exe) or [0])[0]
    if not pid:
        print("no %s running" % a.exe)
        return 1
    base = exe_base(pid, a.exe)
    if not base:
        print("cannot see the modules of pid %d (run as administrator?)" % pid)
        return 1
    p = Proc(pid)
    shape = p.read(base + INTERP_LO, 8)
    if shape != INTERP_SHAPE:
        print("the interpreter at +0x%X does not look like the build this was read from (%s); refusing" % (INTERP_LO, shape.hex() if shape else None))
        return 1
    ctx = p.q(base + CTX_GLOBAL)
    cs = p.q(ctx + CTX_CALLSTACK) if ctx else None
    if not cs or p.q(cs + CS_OWNER) != ctx:
        print("the script context at +0x%X does not point at a call stack; refusing" % CTX_GLOBAL)
        return 1
    print("pid %d, %s at 0x%X; interpreter and script context match the known build" % (pid, a.exe, base))

    # the main thread: the one most often inside the exe during a short warm-up
    tids = threads_of(pid)
    warm = collections.Counter()
    for _ in range(40):
        for t in tids:
            r = p.rip(t)
            if r and base <= r < base + 0x1200000:
                warm[t] += 1
        time.sleep(0.005)
    for t in tids:
        if t not in warm:
            h = p.handles.get(t)
            if h:
                k32.CloseHandle(h)
                p.handles[t] = None
    if not warm:
        print("no thread is executing inside the exe")
        return 1
    main_tid = warm.most_common(1)[0][0]
    print("main thread %d; sampling %.0f s at %.0f Hz" % (main_tid, a.seconds, a.hz))

    vlo, vhi = base + VM_LO, base + VM_HI
    try:
        ctypes.WinDLL("winmm").timeBeginPeriod(1)
    except Exception:
        pass

    self_cnt = collections.Counter()      # innermost function on the script stack
    native_cnt = collections.Counter()    # ... while the CPU was in engine code
    incl_cnt = collections.Counter()      # anywhere on the stack
    owner_cnt = collections.Counter()     # innermost SCRIPT function: natives count for their caller
    owner_native = collections.Counter()
    callers = collections.defaultdict(collections.Counter)
    script_flag = {}

    def is_script(F):
        v = script_flag.get(F)
        if v is None:
            v = script_flag[F] = bool((p.u32(F + FUNC_FLAGS) or 0) & FUNC_FLAG_SCRIPT)
        return v

    total = engine = interp = native = vm_entry = 0
    runs = []                             # (samples, stack) stretches with an unchanged stack
    run_stack, run_n = None, 0
    period = 1.0 / a.hz
    end = time.time() + a.seconds
    while time.time() < end:
        t0 = time.perf_counter()
        rip = p.rip(main_tid, hold=True)
        stack = ()
        if rip is not None:
            try:
                depth = p.u32(cs + CS_DEPTH) or 0
                frames = p.readn(cs + CS_FRAMES + FRAME_SIZE, depth * FRAME_SIZE) if 0 < depth <= MAX_DEPTH else None
            finally:
                p.release(main_tid)
            total += 1
            in_vm = vlo <= rip < vhi
            if frames:
                stack = tuple(f for f in (struct.unpack_from("<Q", frames, i * FRAME_SIZE + 8)[0] for i in range(depth)) if f)
            if stack:
                top = stack[-1]
                self_cnt[top] += 1
                owner = top
                for F in reversed(stack):
                    if is_script(F):
                        owner = F
                        break
                owner_cnt[owner] += 1
                if in_vm:
                    interp += 1
                else:
                    native += 1
                    native_cnt[top] += 1
                    owner_native[owner] += 1
                for F in set(stack):
                    incl_cnt[F] += 1
                callers[top][stack[-2] if len(stack) > 1 else 0] += 1
            else:
                engine += 1
                if in_vm:
                    vm_entry += 1
        if stack == run_stack:
            run_n += 1
        else:
            if run_stack:
                runs.append((run_n, run_stack))
            run_stack, run_n = stack, 1
        dt = time.perf_counter() - t0
        if dt < period:
            time.sleep(period - dt)
    if run_stack:
        runs.append((run_n, run_stack))

    names = Names(p)

    def pct(n):
        return 100.0 * n / max(1, total)

    print()
    print("samples %d over %.0f s (%.0f/s)" % (total, a.seconds, total / max(1e-9, a.seconds)))
    print("  %5.1f%%  engine only, no script on the stack (of which %.1f%% entering/leaving the VM)" % (pct(engine), pct(vm_entry)))
    print("  %5.1f%%  interpreting script" % pct(interp))
    print("  %5.1f%%  engine natives called from script" % pct(native))

    by_mod = collections.Counter()
    by_mod_native = collections.Counter()
    for F, c in owner_cnt.items():
        by_mod[names.get(F)[1]] += c
        by_mod_native[names.get(F)[1]] += owner_native.get(F, 0)
    print()
    print("script time by mod (the innermost script function's file; natives count for the script that called them):")
    for mod, c in by_mod.most_common():
        print("  %6.2f%%  %6d  %-24s (%.2f%% of it in engine code)" % (pct(c), c, mod, pct(by_mod_native[mod])))

    def where(F):
        nm, mod, path, line = names.get(F)
        if mod == "native":
            return "[engine native]"
        return "%s  %s:%d" % (mod, (path or "?").replace("\\", "/"), line)

    print()
    print("top functions on the script stack, self time:")
    print("  %7s %7s %7s  %s" % ("self", "engine", "incl", "function  (mod  file:line)"))
    for F, c in self_cnt.most_common(a.top):
        print("  %6.2f%% %6.2f%% %6.2f%%  %s  (%s)" % (
            pct(c), pct(native_cnt.get(F, 0)), pct(incl_cnt.get(F, 0)), names.get(F)[0], where(F)))

    print()
    print("top script functions, inclusive (anywhere on the stack):")
    for F, c in incl_cnt.most_common(a.top):
        nm, mod, path, line = names.get(F)
        print("  %6.2f%%  %s  (%s)" % (pct(c), nm, mod))

    print()
    print("who calls the hottest functions:")
    for F, c in self_cnt.most_common(10):
        nm = names.get(F)[0]
        parts = []
        for C, k in callers[F].most_common(3):
            parts.append("%s %.0f%%" % (names.get(C)[0] if C else "<engine>", 100.0 * k / c))
        print("  %-48s <- %s" % (nm, "; ".join(parts)))

    long_runs = sorted((r for r in runs if r[0] * period * 1000 >= a.min_run_ms), reverse=True)[:10]
    print()
    if long_runs:
        print("stretches where the script stack did not change for >= %.0f ms (a stall looks like this):" % a.min_run_ms)
        for n, st in long_runs:
            chain = " > ".join(names.get(F)[0] for F in st[-4:])
            print("  %7.0f ms  %s" % (n * period * 1000, chain))
    else:
        print("no stretch >= %.0f ms with an unchanged script stack" % a.min_run_ms)

    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            fh.write("# pid %d samples %d seconds %.0f hz %.0f engine %d interp %d native %d\n" % (pid, total, a.seconds, a.hz, engine, interp, native))
            w = csv.writer(fh)
            w.writerow(["function", "mod", "file", "line", "self", "engine", "inclusive", "owner"])
            for F, c in incl_cnt.most_common():
                nm, mod, path, line = names.get(F)
                w.writerow([nm, mod, (path or "").replace("\\", "/"), line, self_cnt.get(F, 0), native_cnt.get(F, 0), c, owner_cnt.get(F, 0)])
        print()
        print("written: %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
