# OpenZone Radio radio models — working rules

Sources of the radio models for the OpenZone Radio mod (Workshop 3794105144). As of 2026-09-25
the models are part of the mod itself, not a separate addon: what goes into the game lives in the
main mod, `OpenZone_Radio/` (see "Where things live"), and this folder holds the scripts it's
built from. The rules are shared between Claude and Codex; `CLAUDE.md` only points here.

## Where things live

```
OpenZone_Radio/model/<radio>/          p3d (ODOL), model.cfg, data/ (_co/_nohq/_smdi .paa, three .rvmat)
OpenZone_Radio/gui/faces/oz_face_*     frequency window faces (.edds)
OpenZone_Radio/gui/layouts/oz_face_*   radio-face window layout (.layout)
OpenZone_Radio/scripts/5_Mission/OpenZone_Radio/OZR_FreqMenuFace.c   radio-face window
OpenZone_Radio/scripts/4_World/OpenZone_Radio/OZR_PowerGesture.c     power button gesture (Шептун)
OpenZone_Radio/config.cpp              in the OZ_Radio_* classes: model, ozrFace*, ozrPowerGesture, DamageSystem
OpenZone_Radio/stringtable.csv         STR_OZR_RADIO_* (names), STR_OZR_HINT_* (face hints)
models/assets/, models/tools/          sources (this file is about them)
```

Every path baked into the p3d and rvmat starts with `OpenZone_Radio\model\`. Relocating the model
folder means rebuilding it (`build_all.sh` + `asset_build`), not just moving it.

## Before starting and after finishing work

- **Commit before the session ends.** Anything uncommitted doesn't exist for anyone but this
  machine. There's no remote repository yet — create one only with the owner's agreement.
- The commit message should give *why*, not *what*.

## Which model belongs to which class

| folder | OZ-COM name | modeled after | radio mod classes |
|---|---|---|---|
| `pmr_t388` | Шептун | children's PMR T-388 | `OZ_Radio_250m` |
| `lxt` | Базар | Midland LXT600 | `OZ_Radio_500m` |
| `uv5r` | Балаболка | Baofeng UV-5R | `OZ_Radio_1000m` |
| `uvs9` | Скриня | Baofeng UV-S9 (olive) | `OZ_Radio_2000m` |
| `xts` | Терран | Motorola XTS5000 | `OZ_Radio_5000m` |
| `prc152` | Кристал | AN/PRC-152 | `OZ_Radio_10000m` |

Latin transliteration, for reference: Sheptun, Bazar, Balabolka, Skrynia, Terran, Crystal.

**Brand and names (the owner's choice, 2026-09-24 to 2026-09-25).** All the radios share one
in-universe brand, **OZ-COM** — like BIS-COM on the vanilla radio. It's drawn by
`texkit.brand()`: the mark is an open ring with a dot and a wave, the light-blue accent is
`OZ_Palette.ACCENT` from OpenZone Core, rendered in a single color on the army radio and on metal.
There's deliberately no separate letter Z in the mark: the series' audience is Ukrainian-speaking.
Each model has a one-word name so it can be used in RP («buy a couple of Балаболок»). The name is
printed on the housing in Cyrillic (`MODEL` in `layout_<radio>.py`, `PRODUCT` for the PRC) and
appears in the item's name: `displayName` in `OpenZone_Radio/config.cpp` →
`STR_OZR_RADIO_<model>` in `OpenZone_Radio/stringtable.csv`. If you change the name, change it
both on the housing and in the strings. The "modeled after" names are only for finding reference
material — they don't appear on the model.

The owner gave reference ranges for 250/500/1000/2500/5000/10000 m; «2500» is `OZ_Radio_2000m`
(there's no 2500 class in the mod).

Six classes were kept, one per model: 250, 500, 1000, 2000, 5000, 10000 m (the owner's decision,
2026-09-25). Classes 50, 100, 200, and 750 were removed from the mod.
There's no more range tape on the models (removed on 2026-09-25, together with the hidden `label`
named selection and the strip in the frequency window); it was dropped from the item names as
well: the range now appears only in the item's description, a separate one for each radio
(`descriptionShort` → `STR_OZR_RADIO_DESC_<model>`: what kind of radio it is, how far it reaches,
how the frequency is set).

## How a radio is structured

```
assets/_kit/radiokit.py        the shared toolkit (Blender Python): parts, materials, LODs,
                               unwrapping, baking, textures, rvmat, model.cfg, p3d
assets/_kit/texkit.py          labels, LCD (system Python + Pillow)
assets/<radio>/scripts/
  layout_<radio>.py            all dimensions and the layout — read by both the geometry and the printing
  make_prints_<radio>.py       face/side/back labels, LCD -> textures/
  build_<radio>.py             build(m) by level: 0 - detailed, 1..4 - in-game LODs
assets/<radio>/work/<radio>_high.blend   detailed model, written by `-- --high-only`
assets/<radio>/work/<radio>_game.blend   in-game LODs, written by every build
```

From `work/`, only these two `.blend` files go into git: everything else there (baked
`bake/*.npy` — about 1 GB per radio, textures, renders) is reproduced by the scripts. The `.blend`
files reference images from `work/` and `textures/` — open them only after a build.

Order: `python make_prints_<radio>.py` → `blender -b -P build_<radio>.py`
(`-- --high-only` only the detailed model and preview; `-- --skip-bake` reuses what's already
baked; `-- --passes albedo` re-bakes only the named passes, taking the rest from the cache) →
`asset_build(mod="OpenZone_Radio", source="model/<radio>")` → `mod_build` → the stand (all of
this is the dayz-mcp project at the repository root). To print and run Blender for several radios
in a row — `bash tools/build_all.sh [radio ...] [-- flags]`. The build writes a fresh MLOD into
`build/model-root/OpenZone_Radio/model/<radio>/` (the binarize root, `[build] project_root` in
`dayz-mcp.toml`), and `asset_build` puts the ODOL into `OpenZone_Radio/model/<radio>/`; the build
itself writes the textures, rvmat, and model.cfg there, so after touching up a single print it's
enough to re-bake the color and run `mod_build`. Checking the finished model: the ODOL should
contain `openzone_radio\model\` strings and no foreign prefixes. The group shot of the lineup —
`tools/render_lineup.py`.

## The frequency window as a «radio face» (K key)

On K, the mod opens a single window shared by all radios (`OZR_FreqMenu`). The face of whichever
radio is in hand is supplied by
`OpenZone_Radio/scripts/5_Mission/OpenZone_Radio/OZR_FreqMenuFace.c` — a modded class in the same
module (in Enforce it can see the original's private fields; the file must sort alphabetically
after `OZR_FreqMenu.c`). The layout's buttons carry the window's own button names (`Btn0..9`,
`BtnUp/Down`, `BtnGo`, `BtnDot`, `BtnClose`, `DragBar`) — its button set, the bar check, and the
request to the server all work as-is. Custom additions: `BtnBack` (erase, or exit if there's
nothing to erase), a `step` mode for radios without digits (T-388, LXT: the arrow switches
channel immediately, the window stays open), an auto-dot, and a two-row screen. Which face a
class gets is set by the `ozrFace*` fields in `OpenZone_Radio/config.cpp`; a class without them
gets the regular window.

```
tools/hud_spec.py           mode, scale, screen style, and KEY ROLES per radio
tools/render_hud_faces.py   Blender: LOD1 face from <radio>_game.blend
tools/make_hud_layouts.py   cleans up the screen, writes .edds and .layout into OpenZone_Radio/gui/
```

- **If you change a radio's model or `layout_<s>.py`, regenerate its window**:
  `blender -b -P tools/render_hud_faces.py -- <radio>`, then
  `python tools/make_hud_layouts.py <radio>`. The markup re-reads the layout fresh, but the face
  picture is still from the old model until it's re-rendered: the key zones and the screen will
  drift apart (this happened with the T-388 on 2026-09-24).
- The window textures are `.edds` with LINEAR values (the generator handles this itself). The
  interface encodes pixels to sRGB on output: whatever is written as-is comes out washed out, and
  the same goes for a `.paa` with any suffix. Details are in the skill, hud.md.
- Checking it on the stand: put the radio in hand (`world_spawn … hands`), a `Battery9V`
  inserted, `world_power`, `client_type("k")`, then `ui_find`/`ui_click` by the button names. For
  `ui_*` to work, the dayz-mcp bridge must also load on the client (`server_only = []` in the
  local toml).

## Model frame (taken from the vanilla WalkieTalkie.p3d, not invented)

- In Blender: X right, Y back (the face points -Y), Z up, origin — the center of the housing's
  bottom.
- In p3d: `(x, y, z) = (x_b, z_b, y_b)` — the face points -Z, like the vanilla radio. The
  `PersonalRadio.anm` grip and the backpack-strap slot are built for this frame; every
  `PersonalRadio` descendant gets the grip from vanilla with no scripting needed.

## Budgets

- 4 visual LODs, roughly halving at each step; `lodnoshadow = 1` on all of them (like the vanilla
  radio).
- Geometry: `autocenter = 0`, mass 0.25 kg, two convex components — housing and antenna (like
  vanilla); Fire: housing `plastic_material`, antenna `rubber`.
- Atlas per radio: `_co`/`_nohq` 2048 (baked at 4096 and downscaled), `_smdi` 1024; normals in
  DirectX format.
- The p3d name is unique, with the `oz_radio_` prefix.

## Test stand

One per machine: one `dayz-mcp` (`D:\modding\tools\dayz-mcp`) and one DayZ on port **2402**. Stop
the server when you're done. `mod_build` requires the server to be stopped. The dayz-mcp project
is the repository root. The stand needs @CF, @VPPAdminTools, and **OpenZone Core**
(Workshop 3798432022) — in the `[mods] extra` of the local `dayz-mcp.local.toml`. The
@OpenZone_Radio_PDA and @OpenZone_Radio_VPP glue mods hard-require the PDA and the VPP core: on
a stand without them, their build folders are renamed to `off-@…` (in `.gitignore`), and the
server doesn't load them.

**The stand runs on a dedicated server** (`[machine] server` in `dayz-mcp.local.toml` =
`E:\SteamLibrary\steamapps\common\DayZServer`), not on the DayZDiag from the client folder.
Reason: the radio mod needs a server-side frequency proxy — `hid.dll` +
`oz_frequencies.json` next to `DayZServer_x64.exe` (release `proxy-v1.0.0` of the
OpenZone-DayZ/openzone-radio repository, built by GitHub Actions from `native/src`; the archive's
SHA256 was checked against the release notes). Without it, the radio mod runs on the eight
vanilla frequencies and logs «engine's frequency table is not an even grid… unpatched server». The
proxy can't go into the client folder: BattlEye blocks an unsigned DLL in the regular game. The
client for this kind of stand is the retail one, launched through DayZ_BE.

- Check: `oz_frequencies.log` next to the server should say `patched: redirected 12 bytes` and
  `channels: 400, from 136.000 MHz…`; the mod writes the grid itself into
  `<stand_root>/profiles/OpenZone/OZ_Radio_Frequencies.json`.
- The proxy patches **every** server in that folder (the bat-stands for the pistol, keybox,
  casings, and Immersive Placing — they also get 400 channels). To roll back — delete `hid.dll`
  and `oz_frequencies.json` from the server folder.
