# OpenZone Radio radio models (sources)

**Working rules are in [AGENTS.md](AGENTS.md).** It's shared between Claude and Codex and is
deliberately not duplicated here.

## Specific to Claude Code

- The `dayz-modding` skill — before editing models, materials, and configs. The engine's
  gotchas live there, in `references/`.
- The vanilla data is unpacked at `D:\modding\PDrive` (also `P:`; the contributor's machine) —
  the reference for any values in rvmat, configs, and the LODs' named properties.
- Blender: `E:\SteamLibrary\steamapps\common\Blender\blender.exe` (5.2). The system Python
  (`C:\Users\Crystal\AppData\Local\Programs\Python\Python312\python.exe`) — has Pillow, no numpy;
  for Blender it's the other way around.
