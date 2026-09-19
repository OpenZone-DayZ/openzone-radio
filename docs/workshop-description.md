# Steam Workshop description

The listing texts live beside the packaging folders, one file per item, English and
Ukrainian in one field, Steam BBCode:

- [`packaging/OpenZone_Radio.workshop.bbcode`](../packaging/OpenZone_Radio.workshop.bbcode)
- [`packaging/OpenZone_Radio_PDA.workshop.bbcode`](../packaging/OpenZone_Radio_PDA.workshop.bbcode)
- [`packaging/OpenZone_Radio_VPP.workshop.bbcode`](../packaging/OpenZone_Radio_VPP.workshop.bbcode)

They are what the Workshop pages show since 2026-09-19. Edit them there and publish with the
`dayz` MCP: `workshop_publish(mod, description=<the file's text>, tags=[...], content=False)`
-- see [`packaging/README.md`](../packaging/README.md) for the tags.

---

# Опис для Steam Workshop

Тексти описів лежать поруч із теками packaging, по файлу на предмет, англійською та
українською в одному полі, у Steam BBCode: `packaging/OpenZone_Radio.workshop.bbcode`,
`packaging/OpenZone_Radio_PDA.workshop.bbcode`, `packaging/OpenZone_Radio_VPP.workshop.bbcode`.
Саме вони стоять на сторінках Workshop з 2026-09-19. Правте їх там і публікуйте через `dayz`
MCP: `workshop_publish(mod, description=<текст файла>, tags=[...], content=False)`; теги
перелічено в `packaging/README.md`.
