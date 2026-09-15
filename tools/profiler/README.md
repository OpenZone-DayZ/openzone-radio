# Server sampling profiler

Answers one question: **where is `DayZServer_x64.exe` spending its time, per
thread?**

The server's own FPS number cannot answer it. It is an average, so a stall of a
second every few seconds barely moves it, and it watches the frame loop only —
if a different thread is the one standing still, the counter stays cheerful
while players see other players freeze in place.

This samples the instruction pointer of every thread a few hundred times a
second and buckets the addresses by the function ranges in the executable's own
`.pdata`. The answer comes out as "thread N spent X% inside this function",
which is a measurement, not a theory.

## Files

| file | runs where | needs |
|---|---|---|
| `script-profile.ps1` + `profile-server.bat` | the machine running the server | nothing (Windows PowerShell) |
| `script-profile.py` | the machine running the server | Python 3, standard library only |
| `collect-samples.ps1` | the machine running the server | nothing (Windows PowerShell) |
| `collect-memory.ps1` | the machine running the server | nothing (Windows PowerShell) |
| `resolve-samples.py` | anywhere the server exe is available | Python 3, `pefile`, `capstone` |
| `profile-live.py` | one box that has both | Python 3, `pefile`, `capstone` |
| `dayz_image.py` | library for the two Python tools | — |

Two profilers, two questions:

- **`script-profile`** — *which script function, from which mod, is the main
  thread running?* It reads the Enforce VM's own call stack on every sample,
  so the answer is `PluginManager.MainOnUpdate (vanilla scripts/4_World/plugins/pluginmanager.c:144)`
  and a table of time per mod. Start here: on a busy server most of the main
  thread is script, and this says whose.
- **`collect-samples` + `resolve-samples`** — *which engine function is any
  thread running?* Addresses only; the naming happens elsewhere, so the
  server's machine needs nothing installed. Use it when the script profiler
  says the time is not in script.

## Script profiler

### As a monitor, for a problem nobody can be at the keyboard for

Copy `script-profile.ps1` and `profile-server.bat` to the server's machine and
double-click the `.bat` (it asks for elevation, because the server runs
elevated). It watches `DayZServer_x64.exe` for 24 hours, survives the server's
restarts, and writes next to itself:

| file | what |
|---|---|
| `script-profile-<date>.log` | one block per minute: the engine/script split, time per mod, the top functions, every freeze with its time; a full report at the end of each server run |
| `…windows.csv` | the same minute by minute as numbers: memory, handles, threads, CPU, hitches, top functions |
| `…hitches.csv` | every stretch where the main thread stayed in one piece of work for 150 ms or more, with the time, the function it was in or the engine address |
| `…functions.csv` | every function's counts for the current server run, rewritten each minute |
| `…engine.csv` | engine-only samples in `collect-samples` format, so `resolve-samples.py` names them |

Closing the window at any moment loses at most the current minute. Ask for
the whole folder back; the `.log` alone already answers "was the server
freezing, when, and in whose code".

### On the spot

From an elevated PowerShell, while the problem is happening:

```powershell
powershell -ExecutionPolicy Bypass -File script-profile.ps1 -Seconds 60 -Out lag-script
```

or, where Python 3 exists, `python script-profile.py --seconds 60 --out lag-script`
(same output; the `.ps1` is a port for machines without Python, and
`python script-profile.py --hours 24` is the same monitor). Then the same
once more in a calm state, for the comparison. The report has:

- the split of the main thread into *engine only*, *interpreting script*, and
  *engine natives called from script* — the last one is engine work done on
  behalf of script (`GetObjectsAtPosition`, map lookups, RPC sends) and counts
  for the script that asked;
- **time per mod**, from the file the compiler recorded for each function:
  `vanilla`, `JM/CF`, `VPPAdminTools`, `OpenZone_Radio`, ...;
- the hottest functions, self and inclusive, with file and line;
- who calls the hottest ones;
- **stretches where the main thread stayed in one piece of work** for 150 ms
  or more: script entered from one root function, engine code with no script
  on the stack, or a system call that did not return. A frame loop comes back
  to its top many times a second; one piece of work lasting a second *is* the
  freeze players feel, and the report names it — the script function, or the
  engine address for `resolve-samples.py`.

The profiler reads the process and never writes to it. Its offsets are for one
build of `DayZServer_x64.exe` (2026-08-13, 16,965,176 bytes); it checks two of
them at start and refuses another build instead of guessing. After a game
update they have to be re-read; the header of `script-profile.py` lists what.

## Engine profiler

## Procedure

### 1. Collect, while the problem is happening

On the server's machine:

```powershell
.\collect-samples.ps1 -Seconds 30 -Hz 200 -Out lag.csv
```

Thirty seconds of a bad moment is worth more than ten minutes of a good one.
The process is not modified and nothing is written into the game folder.

### 2. Collect a control run

The same command again in the state where the problem is absent — the previous
build, the DLL removed, fewer players, whatever the known-good configuration
is:

```powershell
.\collect-samples.ps1 -Seconds 30 -Hz 200 -Out calm.csv
```

**The control run is the point.** An absolute profile shows what a DayZ server
always does; the difference between two profiles shows what went wrong.

### 3. Resolve

```bash
python resolve-samples.py lag.csv --exe E:/dayzmod/dayzserver-retail/DayZServer_x64.exe
python resolve-samples.py calm.csv --exe E:/dayzmod/dayzserver-retail/DayZServer_x64.exe
```

The `--exe` must be **the same build** that produced the samples. A game update
moves every function, and resolving against the wrong binary produces confident
nonsense rather than an error.

On a **diag** stand the server is `DayZDiag_x64.exe`, a different binary with its
own addresses: collect with `-Exe DayZDiag_x64.exe` and resolve with
`--exe .../DayZDiag_x64.exe`. The hand-named functions in `KNOWN` are retail
addresses and will not apply there; the ranges from `.pdata` still do.

### All on one machine

If the box running the server also has Python, skip the CSV:

```bash
python profile-live.py --seconds 30 --hz 200 --out profile.txt
```

## Reading the output

```
thread 20524: 411 samples, 87% doing work
     10.71%      44  [module] ntdll.dll
      7.54%      31  +0x2E01E0
      7.06%      29  +0x87363B
```

Two things to look at, in this order:

1. **Which thread is busy.** Threads that only ever wait are omitted. If the
   busy one is not the frame loop, the frame counter was never going to show
   the problem.
2. **Whether a name appears.** Functions established by reading the
   disassembly print with a description instead of an address, e.g.
   `VON: update one transmitter against ALL players`. Anything else is an
   address, which is still useful: it can be looked up in the binary.

Percentages are of that thread's own samples, so a thread parked in `ntdll` at
99% is idle, not hot.

## Adding names

`KNOWN` at the top of `resolve-samples.py` maps a function's RVA to a
description. Entries are added only after the function has actually been read
in the disassembler — a guessed name is worse than an address, because an
address invites checking and a name invites belief.

The VoN chain currently named there was established while investigating the
radio mod; see `docs/engine-frequency-table.md` for the frequency lookup and
how it was located.

## Caveats

- The collector must be able to open the process: same user, or elevated.
- Sampling suspends each thread for a few microseconds. At 200 Hz that is well
  under a percent of wall clock. Do not run it at thousands of hertz against a
  live server.
- Addresses are recorded relative to the module base, so ASLR does not matter
  and two runs are comparable.
- A sample lands on the function that was executing, not on whoever called it.
  This says *where* the time went, not *why*; the call graph still has to be
  read out of the binary.
