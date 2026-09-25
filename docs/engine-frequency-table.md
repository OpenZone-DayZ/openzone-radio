# The engine's radio frequency table

Measured, not assumed. Everything below was read out of the shipped binaries and
cross-checked against a running server; nothing here is inferred from forum lore.

Binaries examined:

| Role   | File                                        | Notes                       |
|--------|---------------------------------------------|-----------------------------|
| server | `E:\dayzmod\dayzserver-retail\DayZServer_x64.exe` | 16 965 176 bytes       |
| client | `<Steam>\common\DayZ\DayZ_x64.exe`          | 17 851 448 bytes            |
| diag   | `<Steam>\common\DayZ\DayZDiag_x64.exe`      | 20 245 560 bytes            |

`ImageBase` is `0x140000000` in all three.

## The table

Eight `float32`, contiguous, occurring exactly once per binary:

```
87.8  89.5  91.3  91.9  94.6  96.6  99.7  102.5
```

as bytes: `9a99af42 0000b342 9a99b642 cdccb742 3333bd42 3333c142 6666c742 0000cd42`

| Binary | file offset | RVA        | default VA    | section        |
|--------|-------------|------------|---------------|----------------|
| server | `0xE53D70`  | `0xE55570` | `0x140E55570` | `.data`  **RW** |
| client | `0xF208A0`  | `0xF21AA0` | `0x140F21AA0` | `.data`  **RW** |
| diag   | `0x114BF30` | —          | —             | —              |

**Eight, not seven.** The community repeats seven everywhere; the binary and
`OZR_Bands.Probe` both say eight. The probe's log line agrees exactly with the
bytes above.

The table sits in `.data`, which is mapped read/write. Rewriting the eight values
in a live process needs no `VirtualProtect`. It cannot be *grown* in place: the
32 bytes are immediately followed by unrelated data (`ffffffff 00000000 …`).

## The only limit: one instruction

Exactly one code reference points at the table, in each binary, and it is a
five-instruction leaf function:

```asm
; server 0x140502D10   client 0x140581AF0
mov   eax, edx                  ; edx = index (arg 2)
lea   rcx, [rip + <table>]
and   eax, 7                    ; <-- the entire limit
movss xmm0, dword ptr [rcx+rax*4]
ret
```

`and eax, 7` is encoded `83 E0 07` — the `83 /4 ib` form. `0x0F`, `0x1F`, `0x3F`
and `0x7F` all encode in the same three bytes, so masks for 16, 32, 64 and 128
entries are drop-in replacements requiring no code cave.

## There is no bound check anywhere else

`SetFrequencyByIndex` stores the index **raw** and never validates it:

```asm
; server 0x1405685C0   client 0x1405EEF90
rbx = [rcx + 0x650]        ; radio state block (client: +0x6C0)
[rbx+0x18] = edx           ; index stored verbatim -- no clamp, no mask
call <diagnostics>         ; server 0x140502EA0 / client 0x140053940
edx = [rbx+0x18]           ; re-read only because the call clobbers edx
rcx = [rbx+0x08]
call <table lookup>        ; freq = table[idx & 7]
[rbx+0x1c] = xmm0          ; cache the float
[rbx+0x15] = 1             ; dirty flag
ret
```

The function called in the middle is **not** a normaliser. It opens with a
predicate (`call 0x1400459A0; test al,al; je <tail>`) and, when that passes,
walks a list formatting the cached float into a message — it is a diagnostics
logger, inert on a normal build. It reads `[+0x1c]` and never writes `[+0x18]`.

Consequence, and it is the important one:

> `SetFrequencyByIndex(9)` stores 9. `GetTunedFrequencyIndex()` returns 9.
> Only `GetTunedFrequency()` wraps, to `table[9 & 7]`.

`OZR_Bands.Probe` stops at eight because of its own `hz == first` wrap check, not
because the engine refused index 8. Its count of eight distinct frequencies is
correct, and the comment in that file says so.

## Radio state block

Reached as `[this + 0x650]` on the server, `[this + 0x6C0]` on the client.

| Offset  | Type    | Meaning                                              |
|---------|---------|------------------------------------------------------|
| `+0x08` | pointer | passed to the table lookup, which ignores it         |
| `+0x15` | byte    | dirty flag, set to 1 on every tune                   |
| `+0x18` | int32   | tuned index — **unbounded**                          |
| `+0x1c` | float   | cached frequency, `= table[index & 7]`               |

`GetTunedFrequencyIndex` is `mov rax,[rcx+0x650]; mov eax,[rax+0x18]; ret`.
`GetTunedFrequency` is `mov rax,[rcx+0x650]; movss xmm0,[rax+0x1c]; ret`.

`SetNextChannel` is `inc dword [rbx+0x18]` followed by the same tail, then a tail
call into `0x14066CEF0` (server) — unexamined, presumed the change notification.

## Native implementations (server / client VA)

Each native is registered **twice**: once for `ItemTransmitter`, once for
`StaticTransmitter`, matching the two script declarations.

| Native                   | server                    | client                    |
|--------------------------|---------------------------|---------------------------|
| `SetNextChannel`         | `0x140568600` `0x140766660` | `0x1405EEFD0` `0x1407DA820` |
| `SetPrevChannel`         | `0x140568660` `0x1407666C0` | `0x1405EF030` `0x1407DA880` |
| `GetTunedFrequency`      | `0x140568430` `0x140766580` | `0x1405EEE00` `0x1407DA740` |
| `EnableBroadcast`        | `0x1405683C0` `0x140766510` | `0x1405EED90` `0x1407DA6D0` |
| `EnableReceive`          | `0x1405683F0` `0x140766540` | `0x1405EEDC0` `0x1407DA700` |
| `IsBroadcasting`         | `0x1405684F0` `0x1407665A0` | `0x1405EEEC0` `0x1407DA760` |
| `IsReceiving`            | `0x140568570` `0x140766610` | `0x1405EEF40` `0x1407DA7D0` |
| `SetFrequencyByIndex`    | `0x1405685C0` `0x140766620` | `0x1405EEF90` `0x1407DA7E0` |
| `GetTunedFrequencyIndex` | `0x140568440` `0x140766590` | —                          |

## How these were found, so they can be re-found after a patch

No address above is a magic constant; each came out of a chain that can be re-run
against a new build, using the concrete steps below. The one-off scripts that ran this
chain lived only in a scratch directory and are gone now (`forwards.h` records that the
scratch generator no longer exists); the steps themselves are what carries forward.

1. Boot the stand, read the measured frequencies out of `OZR_Bands` in the log.
2. Pack them as little-endian `float32` and search the binaries. One hit each.
3. Parse the PE, map file offset to RVA, identify the section.
4. Sweep executable sections treating every 4-byte window as a `rel32`; keep
   those whose `next_rva + rel` lands on the table. That finds the reader without
   guessing opcodes.
5. The native *names* are plain C strings in `.rdata`, laid out contiguously in
   the same order the script file declares them. Anchor on those.
6. Registration shape, `RegisterMethod` at server `0x1402CAB40`:

   ```asm
   lea  r9,  [rip + impl]      ; arg 4
   mov  [rsp+0x20], esi        ; arg 5 -- flags
   lea  r8,  [rip + name]      ; arg 3
   mov  rdx, rbx               ; arg 2 -- class descriptor
   mov  rcx, rdi               ; arg 1
   call RegisterMethod
   ```

   So: find the `lea r8` pointing at a name, walk back to the nearest `lea r9`,
   and that is the implementation.

This mirrors the method KR_GRAFTED uses in its own `RESEARCH/` — string anchors
and headless scripts rather than recorded addresses. Their notes cover the script
compiler, the native ABI and object lifetime, and contain **nothing** about radio;
their independently-found `RegisterMethod` agrees with the address above.

## Routing keys on the float, not on the index

Server `0x140503070` walks the player registry and reads the transmitting radio's
cached float — `movss xmm2, [rdi+0x1c]` — five times over. It never touches
`+0x18`. The frequency is passed by value into two helpers, `0x1409A4FB0` (find)
and `0x1409A69A0` (find-or-insert), and both are hash-map lookups **keyed on the
float**:

```asm
movabs r14, 0xCBF29CE484222325   ; FNV-1a 64 offset basis
movabs rbp, 0x00000100000001B3   ; FNV-1a 64 prime
ucomiss xmm6, xmm7 / jne         ; normalise -0.0 to +0.0 so the hash is stable
movzx eax, byte ptr [rsp+0x70]   ; hash the four BYTES of the float,
xor r8, rax / imul r8, rbp       ; one at a time -- textbook FNV-1a
shr rcx, 7 / and rcx, r9         ; then Swiss-table probing:
and r8b, 0x7f / cmp dl, r8b      ; 7-bit control byte against the group
```

`0x1400459A0`, which each of these functions opens with, is `mov al,1; ret` — an
always-true stub, so this is live code and not a diagnostics-only path.

Consequence: index 0 and index 8 both yield `87.8`, hence the same hash, hence the
same bucket. **They are one channel.** Setting an out-of-range index buys nothing
on stock binaries, and the two-radio listening test is unnecessary — the answer is
already known.

The encouraging half of the same finding: the router contains no notion of "8"
anywhere. Its channel space is the space of `float` values, and a hash map does
not care how many keys it holds. The only thing capping DayZ at eight channels is
that `table[idx & 7]` can produce just eight distinct floats.

## The client keeps its own channel map

The matcher is byte-identical in both binaries — server `0x1409A4FB0`, client
`0x140A56930` — and in each it is the **only** float-keyed hash lookup in the
whole image, so it belongs to the radio subsystem and nothing else.

Its callers differ, and that is the whole story:

| Caller | server | client | what it is |
|---|---|---|---|
| registry walk, range math | `0x140503070` | *absent* | transmission routing |
| map register / unregister | `0x140870220` | `0x1408F3940` | membership upkeep |

The membership function is the same code on both sides, down to the instruction
(only the map's offset in its owner differs, `+0x2998` server / `+0x29A0` client):

```c
st   = GetRadioState(radio);
map  = this + 0x29A0;
freq = st[0x1c];                       // the LOCALLY computed float
found = Find(map, radio, freq);
if (st[0x10] && st[0x12] && st[0x14] && on) { if (!found) Insert(map, radio, freq); }
else                                        { if  (found) Remove(map, radio, freq); }
```

So the client is not a passive player of whatever the server sends. It maintains
its own frequency→radios map, keyed by a float it derives itself from its own
copy of the eight-entry table.

The transmission-side walk (`0x140503070`) exists only on the server, and the
function `SetFrequencyByIndex` calls to update the map is a live registry walk on
the server but `ret 0` — an empty stub — on the client (`0x140053940`).

## Routing is server-authoritative, so the client's map does not matter

Maintaining a map is not the same as consulting one. Counting callers of every
float-keyed hash primitive — a function is one if it contains the FNV-1a basis
`0xCBF29CE484222325` and normalises `-0.0` with a `ucomiss` — settles it:

| Binary | primitive | callers |
|---|---|---|
| server | `0x1409A4FB0` (find)   | `0x140503070` router, `0x140870220` register |
| server | `0x1409A69A0` (insert) | `0x140502EA0`, `0x140503070`, `0x140870220`  |
| client | `0x140A56930` (find)   | `0x1408F3940` register — **only** |
| client | `0x140A56090`          | `0x1408F3940` — only |
| client | `0x140A58270`          | `0x1408F3940` — only |

On the client every one of them is reached from the register/unregister function
and from nowhere else. **Nothing on the client ever queries the map by frequency.**
There is no client counterpart to the router `0x140503070`, and the registry walk
that the server's `SetFrequencyByIndex` performs is `ret 0` on the client
(`0x140053940`).

So the client's local map is bookkeeping that no delivery path reads. Which side
a radio ends up on is decided entirely by the server.

## Consequence: a server-side mod is enough

A native mod on the server plus an ordinary PBO on the client extends the channel
count on a public server with stock client binaries. Division of labour:

**Server, native.** The index arrives from the client unbounded and unclamped. All
that is needed is for it to produce a distinct float per channel. Rather than grow
the table — it cannot grow in place, the 32 bytes have unrelated data right behind
them — replace the one function that reads it. `0x140502D10` is an 18-byte leaf
with a single caller path, so a detour can drop the table entirely:

```
frequency(index) = base + index * step      // both from JSON
```

That removes the array, the mask and any power-of-two constraint at once, and the
channel count is then bounded only by the int32 index. Keeping the table instead
works too, but then a relocated array has to sit within ±2 GB of the image so the
`lea`'s rel32 still reaches.

**Client, plain PBO.** Two jobs, both script:

- set indices past 7 — already possible, the field is unbounded and never clamped;
- draw the frequency label itself, because `GetTunedFrequency()` on the client
  still returns `table[index & 7]` and will be wrong. Vanilla shows that value in
  `ItemActionsWidget`, which the mod overrides (`OZR_ItemActionsWidget.c`). It also
  shows it in `ActionTuneFrequencyOnGround`, and that one needs **no** override.

  Settled 2026-09-07 (task 64), by the game's own sources and by the stand. The action
  casts its target to `Land_Radio_PanelBig` in all three of `ActionCondition`,
  `OnActionInfoUpdate` and `OnExecuteServer`, so a static panel is the only thing it can
  ever describe. That panel is `Land_Radio_PanelBig : StaticTransmitter :
  AdvancedCommunication : EntityAI` — a different branch from `TransmitterBase :
  ItemTransmitter`, which is what this mod modifies — so the widened band never reaches
  it whatever we do. And the mod does not profile it: the stand's own
  `OZ_Radio_Profiles.json` holds exactly the seven classes the boot counts
  (`profiles=7`), all six `OZ_Radio_*` handhelds plus `OZ_Module_Radio`, and no static
  transmitter. An override would have nothing to correct.

The client's wrong local float is harmless: it only mis-keys an entry in a map
nothing reads.

**And the patch must gate on `-server`.** A Diag stand runs the client and the
server out of the same directory and from the same `DayZDiag_x64.exe`, so a proxy
that does not check the command line patches both — which makes every test
meaningless, because the whole question is whether a *stock* client works against
a patched server. `GetCommandLineW()` answers it for a Diag build; a bare
`DayZServer_x64.exe` is accepted by executable name (`GetModuleFileNameW`) as well,
because the dedicated server needs no `-server` flag to run and would otherwise never
pass the gate. (This paragraph and the one above are what survived of
`docs/more-frequencies-plan.md`, an executed plan document deleted 2026-09-06 under
the series' rule that plans do not outlive their execution.)

## Still unverified

The claim above rests on static call-graph evidence, which is strong for "the
client never looks up by frequency" but says nothing about how the voice packet
is addressed on the wire. Before building on it, confirm on the stand that two
radios on indices 0 and 8 with a patched server are genuinely separate channels.
That test needs live voice, and it is the one place in this work where a second
person is required.


## What it looks like when the patch is NOT in effect

Observed on a live server with players, 2026-09-01. A restart brought the server up
without the native library, and every radio on it started reporting frequencies
around 2100 MHz — `2108.000`, then `2124.8`, `2126.9`, `2129.0` as the player
turned the knob. The keypad accepted a frequency and did nothing.

Every number above is the eight-entry table doing exactly what it is documented to
do here, plus one mod defect on top.

`OZR_Grid` derives base, step and count from whatever `OZR_Bands.Probe` measured.
On an unpatched engine that measurement is the vanilla eight, so:

```
base = 87.8            step = (102.5 - 87.8) / 7 = 2.1            count = 8
```

Those three numbers are arithmetically correct and completely meaningless: the
vanilla eight are not evenly spaced, and `base + i*step` describes no frequency the
engine has. `OZR_Grid.Ready()` exists to say precisely that, and it correctly
returned false — but the RPC that ships the grid to clients did not ask it. The
client received `8 divisions from 87.800 MHz by 2.1000` (its own log said so), and
its cheaper `OZR_ClientGrid.Ready()` cannot detect unevenness from three numbers, so
it believed it.

The radio itself was still on index 962 — saved from the previous session, where a
1281-division grid made that 148.025 MHz. So the label read `87.8 + 962 * 2.1 =
2108.000`, and each vanilla `SetNextChannel` (+1 index) moved the label 2.1 MHz.
Physically the radio was on `table[962 & 7]` = index 2 = 91.3 MHz the whole time.

The keypad refused for a second, independent reason: the server's own tune handler
checks `OZR_Grid.Ready()` and rejected every request with a `Dbg` line, which retail
clients never display.

**Fixed 2026-09-02** by making the server's verdict travel with the numbers: when
`OZR_Grid.Ready()` is false the grid RPC now sends zeros, `OZR_ClientGrid.Ready()`
is false on the client, and the existing fallbacks take over — the label reverts to
the engine's own honest value and the keypad refuses to open at all. A saved index
that no longer fits its band is also brought back into range on load, since `EEInit`
runs *before* `super.OnStoreLoad` restores it and could never see it.

The lesson generalises: a grid is four facts, and evenness is one of them. Shipping
three of the four across the wire let the receiver reconstruct a grid that the
sender had already judged unusable.

### Verified on the stand, 2026-09-02

The stand reproduces the condition exactly when the native library is absent, so
both states were driven end to end with a live client.

**Without the patch** — `band table measured: 8 frequencies 87.8 .. 102.5`:

| what | before the fix | measured after |
|---|---|---|
| radio at engine index 18 | `87.8 + 18 × 2.1` = 125.6 | **91.3** — the engine's own `table[18 & 7]` |
| client log | `ether received: 8 divisions from 87.800 MHz by 2.1000` | `no ether: the server reports no even frequency grid` |
| keypad on K | opened, then every TUNE was refused server-side | does not open |

The masking is worth seeing plainly: the radio had been stepped 18 times, and the
vanilla engine drew `table[18 & 7]` = index 2 = 91.3 MHz. That is exactly why the
live server's 962 read as vanilla channel 2 while the label claimed 2108.

**With the patch** — `band table measured: 5281 frequencies 86 .. 152`, the same
radio still on index 18 read **86.225** = `86 + 18 × 0.0125`; the keypad opened
showing the band `86.000 - 150.000 step 0.500`; typing 145.5 and pressing TUNE
moved it to index 4760, which is 145.5 MHz to the digit.

**The load-time clamp** was then proved with that same radio: narrowing its profile
to 86–100 and restarting produced

```
OZ_Radio_1000m woke up on index 4760, outside its band 0..1120 - brought back to 0
```

which is also the receipt for the keypad — 4760 is the index the tune had written
and storage had kept.
