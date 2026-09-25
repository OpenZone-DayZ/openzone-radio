# Модели раций OpenZone Radio (исходники)

**Правила работы — в [AGENTS.md](AGENTS.md).** Он общий для Claude и Codex и здесь намеренно
не продублирован.

## Специфичное для Claude Code

- Навык `dayz-modding` — перед правкой моделей, материалов и конфигов. Ловушки движка
  живут там, в `references/`.
- Ванильные данные распакованы в `D:\modding\PDrive` (он же `P:`) — образец для любых
  значений в rvmat, конфигах и именованных свойствах лодов.
- Blender: `E:\SteamLibrary\steamapps\common\Blender\blender.exe` (5.2). Системный Python
  (`C:\Users\Crystal\AppData\Local\Programs\Python\Python312\python.exe`) — с Pillow, без numpy;
  у Blender наоборот.
