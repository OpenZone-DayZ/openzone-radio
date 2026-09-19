# packaging

What goes into a `@Mod` folder besides the packed pbo.

The `@Mod` folders are **build output and are not in git**. `mod_build` writes
`addons/` into them and signs it; everything else a published mod needs lives here and
is copied in by [`package.ps1`](../package.ps1).

```
packaging/<Mod>/mod.cpp     the name, author, version and description DayZ shows in
                            the launcher and the mod list
packaging/<Mod>/meta.cpp    the Workshop item id, for mods that have been published
packaging/<Mod>.workshop.bbcode
                            the Workshop listing: the description the item's page
                            shows, English and Ukrainian in one field, Steam BBCode.
                            Beside the folder, not inside it, so package.ps1 never
                            ships it as a file of the mod
packaging/<Mod>.workshop.bbcode
                            the Workshop listing: the description the item's page
                            shows, English and Ukrainian in one field, Steam BBCode.
                            Beside the folder, not inside it, so package.ps1 never
                            ships it as a file of the mod
```

## Why meta.cpp is here rather than only in the published folder

`meta.cpp` is neither source nor build output: it is the line that ties a local folder
to a Workshop item. Publisher normally writes it, and if it goes missing the next upload
creates a **second** item instead of updating the one that exists.

The first publish of `OpenZone_Radio` (2026-09-01, item 3794105144) left none — the
folder had `addons`, `keys` and `mod.cpp` and nothing else, and a search of the machine
found no `meta.cpp` and no file containing the id. It was reconstructed from the
Workshop URL, and it lives here so it cannot be lost again by deleting a build folder.

`timestamp` is deliberately absent: it is the .NET `DateTime.ToBinary()` of the moment
Publisher wrote the file, and a number invented to fill it would be false. Publisher
writes a real one; the `dayz` MCP writes the three lines above, and Steam needs no more.

## After Publisher runs

If Publisher rewrites `meta.cpp` in the `@Mod` folder — a new timestamp, or an id for a
mod published for the first time — **copy it back here** and commit it. Otherwise the
next `package.ps1` overwrites Publisher's version with this one.

## Publishing

Publishing, in order: `mod_build` (packs and signs) -> `.\package.ps1` (puts the rest in
place; `-Check` only reports) -> `workshop_publish("<Mod>")` from the `dayz` MCP, which
uploads the `@Mod` folder to the item `meta.cpp` names (Publisher, pointed at the same
folder, still works). The listing goes up separately and without touching the files:
`workshop_publish("<Mod>", description=<the text of packaging/<Mod>.workshop.bbcode>,
tags=[...], content=False)`. Steam replaces the whole tag list on every such call, so pass
the full set; the tags each item carries:

| item | tags |
|---|---|
| OZ_Radio (3794105144) | Mod, Server, Equipment, Mechanics, Sound |
| OZ_Radio_PDA (3798437416) | Mod, Equipment, Mechanics |
| OZ_Radio_VPP (3798437535) | Mod, Mechanics |

The procedure and its reasons are written out in `openzone-radio/docs/publishing.md`.

`packaging/<Mod>.workshop.png` is the preview image the item's page shows: 1024x512 PNG, under
1 MB, sent with `workshop_publish("<Mod>", preview="packaging/<Mod>.workshop.png", content=False)`
-- like the listing text, beside the folder so it never ships as a file of the mod.
