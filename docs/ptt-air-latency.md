# Push-to-talk and the start of every phrase

Read out of `DayZServer_x64.exe` and `DayZ_x64.exe` (build of 2026-08-13) on
2026-09-25, after players reported "one talks, the others do not hear". The
engine facts are also in the `dayz-modding` skill (persistence-networking.md,
"VoN routing"); this note is about what they mean for this mod.

## How a word travels

1. **Who can talk into a radio.** Every frame the server walks each switched-on
   transmitter (`+0x503070`) and registers it in the map of every player whose
   own voice-level range (`VoNRanges`: whisper / talk / shout, 1 m hysteresis)
   reaches the radio's position. A radio on the player's body is at distance
   zero and always qualifies; one on the ground or in a vehicle qualifies only
   within the speaker's current voice range.
2. **Who hears it.** When a player speaks, each of their registered radios with
   *broadcast* on (`EnableBroadcast`, state byte `+0x13`) is matched against
   every radio with *receive* on (`EnableReceive`, `+0x14`) tuned to the same
   frequency float (`+0x9A6040`). The listeners are the players those receiving
   radios reach; their tables (`+0x9AA800`) are rebuilt whenever a radio
   registers or unregisters. Nothing in this chain counts frequencies: the keys
   are floats and entity ids, so any number of frequencies can be busy at once.
3. **What the client sends.** One voice packet per frame: one encoded audio
   frame plus a header with the kinds it goes to (direct, megaphone,
   transmitters, PAS) and a short list of the client's *own* transmitters. The
   client starts a stream per transmitter ("(Self) Start transmitter %d") only
   for radios whose *client-side* broadcast flag is set, and re-evaluates that
   set whenever its local radio map changes (VoNSystemXA2 slots 14/28 →
   `+0x752130` → `+0x74F410`). The server checks its *own* flags for every
   listed transmitter and drops the entries whose flag is off.

## Where the beginning of a phrase goes

Vanilla has no push-to-talk: `TransmitterBase.OnWorkStart` opens broadcast
together with power, so a switched-on radio always carries its owner's voice.
This mod holds the air shut and opens it by key (commits 6800b59, 7789942):

    key down → one bit to the server → OZR_PickSpeaker chooses ONE radio by rank
    → EnableBroadcast(true) on the server → the flag is synced to the client
    → the client's map changes → the client starts its stream into that radio

Until the last step the client's packets carry no transmitter, so the server
has nothing to route. The loss at the start of every press is one round trip
plus about two frames: 0.2–0.4 s at 100–150 ms ping. A short "copy" vanishes
entirely, and the speaker does not notice, because direct voice from the same
(mirrored) key starts at once.

## Why the server decides, and why that stays

Recorded in the sources and commits, all still valid:

- the client sends one bit; **which** radio opens is decided server-side by
  walking that player's own inventory (hands, then worn, then cargo if the
  server allows it, freshest-held among equals), so the packet cannot open
  somebody else's set and three radios do not talk into three airs at once;
- the squelch click plays on the radio for everyone nearby, so the air state
  is the mod's own synced variable (`m_OZR_Air` / `m_OZR_AirSeq`), because
  `EnableBroadcast` is engine state that `SetSynchDirty` does not know;
- power is judged on the server (`OZR_SpeakRank` returns 0 for a dead set);
- a dropped radio shuts its own air on the server; a latch travels with the bit;
- edges are sent, not per-frame state.

## The change that keeps all of that: open the client's side too

At key down the client additionally calls `EnableBroadcast(true)` **locally**
on its top place tier of live profiled radios (hands; else worn; else cargo if
`PttFromCargo`), and `false` at release, latch excepted. Effects:

- the client's own stream starts immediately; its packets list the radio;
- the server still opens exactly one radio by rank and delivers only that one;
  the other listed entries fail the server's flag check and are dropped, so
  listeners get the same single air as today;
- audio is encoded once per packet whatever the list length; extra entries
  cost a few bytes each;
- the server's sync then rewrites the client's flag of the chosen radio with the
  same value; the client's flags on unchosen radios stay set until release, which
  the server ignores;
- squelch, HUD icon (it reads the synced air state, 6fcb6e5), latch, drop
  handling and the power check are untouched.

Expected gain: the loss at the start of a press drops from a round trip plus
two frames to half a round trip. A second, server-side half: keep the air open
300–500 ms after release (`CallLater` on the release edge) so tails are not cut.

Status 2026-09-25: analysed, not implemented; the owner decides. The
measurement is a stopwatch on a one-word phrase between two people on the stand,
before and after.

## Other reasons a listener hears nothing

Engine side:

- the server froze (measured on the live server: 0.5–2.5 s stalls from a
  storage mod's JSON loads; voice of that interval is lost for everyone,
  radio and direct alike);
- the speaker's radio is outside their voice-level range: whispering with the
  radio on the ground or in a vehicle, not on the body;
- the listener muted the speaker or "muted all" (the engine keeps per-player
  mute lists; `[VON]: player: %d has muted all players`);
- UDP loss on a bad link drops voice frames; there is no retransmission;
- a listener who connected during a long latched transmission is added to the
  speaker's listener table only at the next registration event.

Mod side:

- the key found no radio it may open: only a stashed one with `PttFromCargo`
  off, or a dead set; the HUD icon stays dark in both cases;
- the client's look-up of a usable radio is cached (`LOOK_EVERY_MS`); a radio
  switched on and keyed within that window is missed once;
- the PTT edge rides a guaranteed RPC: it is not lost, but under congestion it
  arrives late and the whole delay is cut from the phrase;
- the receiving radio lost power mid-conversation (`OnWorkStop` turns receive
  off) and its owner did not notice;
- radios from profiles with different bands or steps can show the same channel
  label on different frequencies; since 4a6b9db every profile shares one band,
  which a live server must actually be running.

How to tell them apart: with the server's debug log on, every press logs
`ptt gate: <radio> air OPEN` (or the refusal) and every release `shut`; the
client logs `ptt: key DOWN/up`. Presses that reach the server and open the
intended radio while listeners still hear nothing point at the engine side;
the monitor's `.hitches.csv` says whether the server was frozen at that second.
