# OpenZone frequency proxy

A server-side native mod that raises DayZ's nine radio channels (DayZ 1.30; eight
before it) to a number set in JSON. Loads as a proxy `hid.dll` beside the game
executable and replaces the one engine function that turns a tuned index into a frequency. For the native
Linux server the same replacement is a shared object, `oz_frequencies.so`,
loaded with `LD_PRELOAD`; see "The native Linux server" below.

Background: [engine-frequency-table](../docs/engine-frequency-table.md) — what was
measured in the binaries, and why the design looks like this.

## What it does

The engine computes a frequency as `table[index % 9]` — nine floats in `.data`
and a modulo by a magic multiply, in a fifty-byte leaf function, with the same
arithmetic inlined once more into the transmitter initialiser. This replaces both
with `base + index * step`, which removes the table, the modulo and the fixed
count at once. Indices wrap within `count`, so `SetNextChannel` still cycles the
way the vanilla modulo made it.

Delivery is decided only on the server, so **stock clients need no native code**
— see the research notes for the call-graph evidence.

## Server only, by design

The proxy patches nothing unless the process was launched with `-server`, or is
named `DayZServer_x64.exe` — a dedicated server needs no such flag. On a Diag
stand the client and the server are the same executable in the same directory,
so an ungated proxy would patch both — and the whole question this exists to
answer is whether an unpatched client works against a patched server.

**A rejected process says so.** The gate used to return in silence for everything
it turned away, and that made two opposite faults look identical: a DLL that was
never there and a DLL that loaded and was refused both left no log at all. Since
2026-09-02 a process that is none of the game's own — `DayZ_x64.exe`,
`DayZDiag_x64.exe`, `DayZ_BE.exe`, `DayZLauncher.exe`, `CrashReporter.exe`,
`DayZUninstaller.exe` — gets a line naming itself:

```
NOT PATCHED: loaded into "somewrapper.exe", which is neither DayZServer_x64.exe
nor one of the game's own executables, and its command line carries no -server.
If this IS the server, launch it with -server.
```

The game's own six stay silent, because the launcher and the BattlEye shim run on
every ordinary start and a line each would bury the file. That is the whole
difference: silence for the game, a name for a stranger. **A renamed or wrapped
server binary is the one shape in which this gate can be wrong about a real
server, and it is now the one shape that reports itself.**

## Build

Needs the MSVC C++ toolchain (Visual Studio or the standalone Build Tools, with
the "Desktop development with C++" workload — the Windows SDK comes with it).
`build.ps1` finds it through `vswhere` and imports the x64 environment itself, so
no developer prompt is required.

```powershell
.\build.ps1                 # build into .\build
.\build.ps1 -Deploy         # build, then install beside the game executable
.\build.ps1 -Deploy -GameDir 'D:\somewhere\DayZ'
```

Deploying refuses while the game or server is running, because a loaded DLL
cannot be overwritten.

## Configuration

Two places are looked at, in this order:

1. `<profiles>/OpenZone/OZ_Radio_Frequencies.json` -- the `-profiles` directory named on
   the server's own command line. **This is normally the live one, and it is
   not written by hand:** the mod derives it from the radio profiles an admin
   edits in game (lowest band bottom, highest band top, and the greatest common
   divisor of every step and every bound offset), so the ether is always exactly
   what the radios ask for. Script file access in DayZ is confined to
   `$profile:`, which is why this path exists at all -- it is the only one an
   in-game admin panel can reach.
2. `oz_frequencies.json`, beside the DLL -- the fallback and the shipped
   default, used when the first is absent.

Either file holds the same three numbers:

```json
{
  "base_mhz": 136.0,
  "step_mhz": 0.05,
  "count": 400
}
```

Those are also the numbers the mod's built-in radio profiles derive when an admin
has described none, and the ones compiled into the DLL as the last fallback: one
band for every radio, 400 channels. Three copies of one default; they change
together.

Read once, at process start, because that is when the patch is applied: a change
takes effect on the NEXT server start, and the mod says so in its own log rather
than leaving the delay to be discovered.

Only distinctness matters to the engine — it keys channels on the four bytes of
the `float`, so any step that keeps values apart in `float32` works. A missing
field keeps its default and is reported; `count < 1` and `step_mhz == 0` are
refused and replaced, because both would silently collapse every channel into
one.

## Log

`oz_frequencies.log`, beside the DLL. Every path through start-up writes a line,
including the ones that patch nothing — the failure this file exists to prevent
is a mod that quietly does nothing while appearing installed.

**So the absence of this file is itself a reading**, and since the gate learned to
name a stranger there are only two ways to get no log at all: the DLL is not
beside the executable that ran, or the process was one of the game's own. Neither
of those is "it loaded and something went wrong inside" — that case always writes.

```
08:41:02  found: lookup at +0x5C7790, table at +0x114DF30, table is the known vanilla eight
08:41:02  patched: redirected 12 bytes
08:41:02  channels: 64, from 87.800 MHz in steps of 0.200 MHz (index 0 = 87.800, index 63 = 100.400)
```

## Layout

```
src/forwards.h    47 pragmas forwarding hid.dll's exports to the real one
src/patch.h/.cpp  finding the lookup by its code shape, and redirecting it
src/dllmain.cpp   the -server gate, the JSON, the log, the replacement function
build.ps1         toolchain discovery, build, deploy

linux/oz_frequencies.c    the whole Linux library: gate, JSON, log, finding, redirect
linux/build.sh            cc -shared, and `build.sh test` to run the checks
linux/test/fake_server.c  a stand-in for the engine, one variant per code shape
linux/test/run.sh         the library against the stand-in
```

`forwards.h` is generated from the real `hid.dll`'s export table rather than
written by hand. Regenerate it if a future Windows adds an export.

## Finding the function

No address is compiled in. At start-up the DLL scans the host image's executable
sections for the lookup's own machine code, with the `lea`'s displacement
wildcarded, then follows that displacement and checks what it points at. A game
update therefore moves the function without breaking anything.

Two refusals are deliberate:

- **No match** — the game changed how it compiles this. Nothing is patched.
- **More than one match** — patching the wrong one of two identical leaves would
  be silent and very hard to trace, so it refuses rather than guess.

Both are written to the log.

This code is 1.30's. The 18-byte shape of 1.29 and earlier (`and eax, 7` over an
eight-entry table) is gone from it; the last build that knows it is the
`proxy-v1.1.0` release. Two shapes are known here (`src/patch.cpp`), and the LEAF
shape must match exactly once:

| shape | build | what it is |
|---|---|---|
| `1.30 leaf` | 1.30.164014, 1.30.164078 | 50 bytes: the index reduced modulo 9 with a magic multiply, nine-entry table (80.0 MHz in front of the old eight); the same calling convention, eight `call` sites |
| `1.30 inlined copy` | 1.30.164014, 1.30.164078 | the same arithmetic inlined into the transmitter initialiser, reading the index from the object; patched with a `call` to the replacement when it is unique and reads the same table, otherwise reported and left alone |

With `OZ_FREQUENCIES_SELFTEST=1` in the environment the DLL calls the engine's
lookup through its own entry right after patching and logs what it answers, the
same check the Linux library offers.

## Status

**1.30 stable (1.30.164078), measured 2026-10-15.** Both shapes found again, moved by
the update, against `DayZServer_x64.exe` 1.30.164078 from Steam app 223350 (no mods,
`OZ_FREQUENCIES_SELFTEST=1`), the server alive through world load and the central
economy's init:

```
found: lookup at +0x92E9C0 (1.30 leaf, 50 bytes), table at +0x1644170, table is the known vanilla nine; 1.30 inlined copy at +0x92E8F7 reads the same table
patched: redirected 12 bytes
patched: inlined copy: replaced 50 bytes with a call
self-test: the engine's lookup now answers index 0 = 136.000, 1 = 136.050, 9 = 136.450, 399 = 155.950, 400 = 136.000 (wraps), -1 = 155.950 (wraps)
channels: 400, from 136.000 MHz in steps of 0.0500 MHz (index 0 = 136.000, index 399 = 155.950)
```

The same server with the full OpenZone set (CF, VPP, core, factions, PDA, radio and
their glue) took its grid from the profile and the radio mod measured it:
`radio loaded: bands=400 profiles=7`, no script errors.

**1.30 Experimental (1.30.164014), measured 2026-10-11.** The builds before this
code refused on it by design (`NOT PATCHED: the frequency lookup's code shape
is not present`): the game now ships nine channels and compiles the lookup as a
50-byte leaf with a modulo-9 reduction, plus an inlined copy in the transmitter
initialiser. Both shapes are in `src/patch.cpp` now. Measured against
`DayZServer_x64.exe` 1.30.164014 (a second instance beside a running stand, no mods,
`OZ_FREQUENCIES_SELFTEST=1`), the server alive through world load and the central
economy's init:

```
found: lookup at +0x90FA30 (1.30 leaf, 50 bytes), table at +0x16114C0, table is the known vanilla nine; 1.30 inlined copy at +0x90F967 reads the same table
patched: redirected 12 bytes
patched: inlined copy: replaced 50 bytes with a call
self-test: the engine's lookup now answers index 0 = 136.000, 1 = 136.050, 9 = 136.450, 399 = 155.950, 400 = 136.000 (wraps), -1 = 155.950 (wraps)
channels: 400, from 136.000 MHz in steps of 0.0500 MHz (index 0 = 136.000, index 399 = 155.950)
```

In game on the same build, with the full stand: `radio loaded: bands=400 profiles=7`,
and a freshly spawned radio in a client's hands showed 136.000 MHz, a value it can only
get through the patched inlined copy.

### History: 1.29 and earlier (the shape `proxy-v1.1.0` patches)

**The patch works on a live server.** Measured 2026-08-30 against
`DayZDiag_x64.exe -server` with `count: 16`:

```
found: lookup at +0x5C7790, table at +0x114DF30, table is the known vanilla eight
patched: redirected 12 bytes
channels: 16, from 87.800 MHz in steps of 0.200 MHz (index 0 = 87.800, index 15 = 90.800)
```

Confirmed independently by `OZR_Bands.Probe`, which predates this work and knows
nothing about it. It drives the engine's own `SetFrequencyByIndex` /
`GetTunedFrequency` and reads back what the engine actually returned:

```
band table measured: 16 frequencies  87.8 88 88.2 88.4 88.6 88.8 89 89.2
                                     89.4 89.6 89.8 90 90.2 90.4 90.6 90.8
```

Sixteen distinct frequencies where the engine had eight, matching the JSON
exactly — so both the patch and the config reader are doing what they claim.

The `-server` gate was verified in the same session: the game client loaded the
same `hid.dll` from the same directory and added no line to the log, leaving its
own table vanilla. That is the shipping configuration — patched server, stock
client — and the client connected and played normally in it.

## Linux: the Windows server under Wine or Proton

Measured 2026-10-05 with Wine 9.0 on Ubuntu 24.04 (WSL2): `DayZServer_x64.exe` (build of
2026-08-13), `hid.dll` and `oz_frequencies.json` in one folder, started with
`wine DayZServer_x64.exe -profiles=prof`. The proxy is loaded and patches exactly as on Windows:

```
found: lookup at +0x502D10, table at +0xE55570, table is the known vanilla eight
patched: redirected 12 bytes
channels: 400, from 136.000 MHz in steps of 0.0500 MHz (index 0 = 136.000, index 399 = 155.950)
```

| `WINEDLLOVERRIDES` | what Wine loads | result |
|---|---|---|
| not set | the proxy beside the executable (native), then `C:\Windows\System32\hid.dll` (builtin) for the forwards | patched |
| `hid=n,b` | the same | patched |
| `hid=n` | the proxy, but the forwards to System32 are refused: `module not found for forward` | patched, every HID export unresolved; do not use |

Wine 9.0 prefers the copy beside the executable on its own, so no override is needed there.
Setting `WINEDLLOVERRIDES="hid=n,b"` anyway costs nothing and removes the dependence on that
default, which other Wine or Proton builds need not share. Never `hid=n`: the proxy forwards
every export to the System32 library, and in a Wine prefix that library is Wine's builtin one.

The same three runs through Proton's own launcher, outside Steam (GE-Proton11-7, Wine 11.0
Staging; `python3 proton run DayZServer_x64.exe -profiles=prof` with `STEAM_COMPAT_DATA_PATH`
and `STEAM_COMPAT_CLIENT_INSTALL_PATH` set to empty folders) gave the same three answers:
patched with no override, patched with `hid=n,b`, and with `hid=n` the forwards fail and
Proton's own `lsteamclient.dll` loses its `XINPUT1_3.dll`, which needs the builtin `hid.dll`.

What these runs do not cover: a full boot with mods (the folder held no game data, so the
server never got to its config). The native Linux server binary cannot load the proxy at all,
it is a Windows DLL patching a Windows image; that server has a library of its own, next.

## The native Linux server

`DayZServer`, the ELF build of the server, imports no library a proxy could stand in for,
so the replacement is delivered the way Linux offers one:

```
LD_PRELOAD=/home/dayz/server/oz_frequencies.so ./DayZServer -config=serverDZ.cfg -port=2302 -profiles=profiles
```

or `Environment=LD_PRELOAD=/home/dayz/server/oz_frequencies.so` in the systemd unit. Give
the full path. `oz_frequencies.json` and the log sit beside the library, and the grid in
`<profiles>/OpenZone/OZ_Radio_Frequencies.json` wins over that file, exactly as for the DLL.
The library acts only in a process whose executable is named `DayZServer`; anything else
started with the same environment (the launching shell, steamcmd) is left alone and silent.
Where the log file cannot be written, because the library sits in a directory the server's
user may not write to, its lines go to the server's standard error instead, after one line
saying why.

**1.30.** `DayZServer` 1.30.164014 (Steam app 1042420, Linux depot
1042422; GCC, a fixed-base executable at `0x400000`) carries the same change as the
Windows build: nine channels and a modulo-9 reduction. The library finds the table by its
nine floats, then every reference to it, and accepts the one that sits inside the 1.30
leaf -- a sign-extended argument, the multiplier `0xE38E38E38E38E38F`, a `mul`, the table
instruction, a `movss` through it and a `ret` -- in whichever order the compiler put the
first two. The jump goes to the function's ENTRY, found as the address the image's
`call rel32` instructions land on (eight of them on the real server), so no instruction of
the leaf runs before the stub saves the registers. The inlined copy in the transmitter
initialiser is matched byte for byte (`[rbx + 0x18]` in, `[rbx + 0x1C]` out, the caller's
`mov byte [rbx + 0x15], 1` in the middle) and replaced with a call that keeps that
instruction; a copy that differs is reported and left alone. `sh native/linux/build.sh
test` covers the leaf under GCC 13 at -O1, -O2 and -O3, PIE and fixed base, with and
without ENDBR64, with all 24 clobberable registers checked, plus the profile grid, the
self-test, the no-log-file path and the stranger gate.

**1.30 on the real server.** Measured 2026-10-11 against `DayZServer` 1.30.164014 (depot
1042422) on Ubuntu 24.04 under WSL2, with the game data of the Experimental Windows server,
`BattlEye = 0`, `verifySignatures = 0` and `-mod=@CF;@OpenZone_Core;@OpenZone_Radio`. The
library's log:

```
found: lookup at +0xDEC850 (46 bytes to its return, index in esi, the second argument), table at +0x1C2C360, table is the known vanilla nine; inlined copy at +0xDEC8CA reads the same table
patched: redirected 5 bytes through a relay at 0x3f0000
patched: inlined copy: replaced 50 bytes with a call
channels: 400, from 136.000 MHz in steps of 0.0500 MHz (index 0 = 136.000, index 399 = 155.950)
self-test: the engine's lookup now answers index 0 = 136.000, 1 = 136.050, 9 = 136.450, 399 = 155.950, 400 = 136.000 (wraps), -1 = 155.950 (wraps)
```

and the mod's own probe in the server's script log:

```
[OpenZone/Radio] band table measured: 400 frequencies  136 ..  155.95
[OpenZone/Radio] ether derived from profiles: 136.000 to 155.950 MHz, step 0.0500, 400 divisions (in effect)
[OpenZone/Radio] radio loaded: bands=400 profiles=7
```

The server reached `core loaded` and was stopped on SIGINT as usual.

### History: 1.29 and earlier (the shape `proxy-v1.1.0` patches)

**Status: works on the real server.** Measured 2026-10-05 against `DayZServer` 1.29.163709
(Steam depot 223352) on Ubuntu 24.04 under WSL2, with the game data of the Windows server of
the same build, `BattlEye = 1`, `verifySignatures = 2` and
`-mod=@CF;@OpenZone_Core;@OpenZone_Radio`. The library's log:

```
grid read from beside the library: /root/dzfull/oz_frequencies.json
found: lookup at +0x15BA5F0 (16 bytes to its return, index in esi, the second argument), table at +0x1FCAD00, table is the known vanilla eight
patched: redirected 5 bytes through a relay at 0x24b0000
channels: 400, from 136.000 MHz in steps of 0.0500 MHz (index 0 = 136.000, index 399 = 155.950)
```

and, in the server's script log, the mod's own probe, which drives `SetFrequencyByIndex` /
`GetTunedFrequency` and reads back what the engine returned:

```
[OpenZone/Radio] band table measured: 400 frequencies  136 ..  155.95
[OpenZone/Radio] ether derived from profiles: 136.000 to 155.950 MHz, step 0.0500, 400 divisions (in effect)
[OpenZone/Radio] radio loaded: bands=400 profiles=7
```

| start | where the grid came from | what the mod measured |
|---|---|---|
| with the library, first boot | the file beside the library | 400 frequencies, 136 .. 155.95 |
| without the library | | 8 frequencies, 87.8 .. 102.5, and the mod's warning that this is what an unpatched server looks like |
| with the library, second boot | the profile's copy, which the mod wrote on the first boot | 400 frequencies |
| with the library, the profile's copy edited by hand to 140.0 / 0.025 / 800 | the profile's copy | 800 frequencies, 140 .. 159.975 |
| with the library, the boot after that | the profile's copy, which the mod wrote again from its radio profiles | 400 frequencies again |

BattlEye initialised and the server registered with Steam with the library loaded; it sat
idle and stopped on SIGINT as it does without it. The mod's profiler, two million calls
each: `SetFrequencyByIndex` costs about 82 ns with the library against 52 ns without, so the
stub adds some 30 ns to a tune; `GetTunedFrequency` is 32 ns either way.

The same server also boots the radio stand's full set with the library loaded and no script
errors: CF, VPP Admin Tools, the core, factions, the PDA and the glue pbos, twelve mod folders.

What this does not cover is voice between two players on a Linux server: that needs two
people.

**To check another build of the server in a few seconds**, put the three files of the
Linux depot, the library and `oz_frequencies.json` in an empty folder and start it with
`OZ_FREQUENCIES_SELFTEST=1` as well: right after patching the library calls the engine's
lookup itself and logs what it answers. (The server then dies for want of game data, which
it does without the library too.)

```
self-test: the engine's lookup now answers index 0 = 136.000, 1 = 136.050, 9 = 136.450, 399 = 155.950, 400 = 136.000 (wraps), -1 = 155.950 (wraps)
```

**How the lookup is found (1.29, for the record).** The 1.29 library was
written before anyone here had the Linux binary, which comes from a different compiler
than the Windows one, so it did not match fixed bytes: it found the eight vanilla
frequencies as data, then the one instruction that addressed them with a mask by 7 beside
it and a return after it, wrote every reference to the table into the log with the bytes
around it, and said `NOT PATCHED` when the lookup was inlined into its callers. This
code keeps the data-first approach and the logging, and replaces the mask rule with the
1.30 leaf described above.

The real server (GCC 7.5, a fixed-base executable at `0x400000`) has it as
`lea rax, [rip + table]; and esi, 7; movss xmm0, [rax + rsi*4]; ret`, the mask after the
table's address where the Windows build has it before, and was found and patched on first
contact with nothing changed for it.

**Why five bytes and a relay, where the DLL writes twelve.** A compiler that sees a
three-instruction leaf knows which registers it touches and may keep its own values in all
the others across the call (GCC does at `-O2`, `-fipa-ra`). The DLL's `mov rax, imm64; jmp
rax` into a C function clobbers `rax` and whatever else the calling convention allows;
tried here first, it turned every frequency of the stand-in into `0.000` without crashing
anything. So the lookup gets a five-byte relative jump, which touches no register, to a
relay page mapped within its reach; the relay jumps to an assembly stub that saves the flags,
the caller-saved general registers and `xmm1`..`xmm15`, calls the C function and restores
them. Only `xmm0`, the result, comes back changed, and the test checks all 24 registers.
The relay page is taken below the end of the executable, where the heap never grows: on the
real server it lands in the gap between the code and the data segment.

`sh native/linux/build.sh test` builds the library and runs it against
`linux/test/fake_server.c` compiled seven ways. The result needs glibc 2.14 or newer.

## Note on a shared game directory

The proxy is deployed beside the game executable, which on this machine is the
one every DayZ project shares. **Every server started from that directory is
patched**, not only this project's. Delete `hid.dll` there to undo it.
