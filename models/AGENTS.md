# Модели раций OpenZone Radio — правила работы

Исходники моделей раций мода OpenZone Radio (Workshop 3794105144). С 25.09.2026 модели — часть
самого мода, а не отдельный аддон: что идёт в игру, лежит в основном моде `OpenZone_Radio/`
(см. «Где что лежит»), а эта папка — скрипты, из которых оно собрано. Правила общие для Claude
и Codex; `CLAUDE.md` только ссылается сюда.

## Где что лежит

```
OpenZone_Radio/model/<радио>/          p3d (ODOL), model.cfg, data/ (_co/_nohq/_smdi .paa, три .rvmat)
OpenZone_Radio/gui/faces/oz_face_*     лица окна частот (.edds)
OpenZone_Radio/gui/layouts/oz_face_*   разметка окна лицом рации (.layout)
OpenZone_Radio/scripts/5_Mission/OpenZone_Radio/OZR_FreqMenuFace.c   окно лицом рации
OpenZone_Radio/scripts/4_World/OpenZone_Radio/OZR_PowerGesture.c     жест кнопки (Шептун)
OpenZone_Radio/config.cpp              в классах OZ_Radio_*: model, ozrFace*, ozrPowerGesture, DamageSystem
OpenZone_Radio/stringtable.csv         STR_OZR_RADIO_* (имена), STR_OZR_HINT_* (подсказки лиц)
models/assets/, models/tools/          исходники (этот файл - о них)
```

Каждый путь, зашитый в p3d и rvmat, начинается с `OpenZone_Radio\model\`. Переложить папку
модели — значит пересобрать её (`build_all.sh` + `asset_build`), а не просто перенести.

## Перед началом и после работы

- **Коммитить до конца сессии.** Незакоммиченное не существует ни для кого, кроме этой машины.
  Удалённого репозитория пока нет — создавать только с согласия пользователя.
- В сообщении коммита — *почему*, а не *что*.

## Какая модель какому классу

| папка | имя OZ-COM | по мотивам | классы мода друга |
|---|---|---|---|
| `pmr_t388` | Шептун | детская PMR T-388 | `OZ_Radio_250m` |
| `lxt` | Базар | Midland LXT600 | `OZ_Radio_500m` |
| `uv5r` | Балаболка | Baofeng UV-5R | `OZ_Radio_1000m` |
| `uvs9` | Скриня | Baofeng UV-S9 (олива) | `OZ_Radio_2000m` |
| `xts` | Терран | Motorola XTS5000 | `OZ_Radio_5000m` |
| `prc152` | Кристал | AN/PRC-152 | `OZ_Radio_10000m` |

**Марка и имена (выбор пользователя 24-25.09).** На всех рациях одна своя марка **OZ-COM** —
как BIS-COM у ванильной рации. Рисует её `texkit.brand()`: знак — открытое кольцо с точкой и
волной, голубой акцент — `OZ_Palette.ACCENT` из OpenZone Core, у армейской и на металле одним
цветом. Отдельной буквы Z в знаке нет нарочно: аудитория серии украиноязычная. У каждой модели
имя одним словом, чтобы звать её в РП («купи пару Балаболок»). Имя печатается на корпусе
кириллицей (`MODEL` в `layout_<радио>.py`, у PRC — `PRODUCT`) и стоит в названии предмета:
`displayName` в `OpenZone_Radio/config.cpp` → `STR_OZR_RADIO_<м>` в `OpenZone_Radio/stringtable.csv`.
Меняешь имя — меняй и на корпусе, и в строках. Названия «по мотивам» — только для поиска референсов, на модели их нет.

Пользователь дал референсы на 250/500/1000/2500/5000/10000 м; «2500» - это `OZ_Radio_2000m`
(класса 2500 в моде нет).

Оставлены шесть классов, по одному на модель: 250, 500, 1000, 2000, 5000, 10000 м (решение
пользователя 25.09). Классы 50, 100, 200, 750 из мода убраны.
Скотча с дальностью на моделях больше нет (убран 25.09, вместе со скрытой выборкой `label`
и лентой в окне частот), из названий предметов её тоже убрали: дальность — только в описании
предмета, у каждой рации своём (`descriptionShort` → `STR_OZR_RADIO_DESC_<м>`: что за рация,
докуда достаёт, как ставится частота).

## Как устроена рация

```
assets/_kit/radiokit.py        общий набор (Python Блендера): детали, материалы, лоды,
                               развёртка, запекание, текстуры, rvmat, model.cfg, p3d
assets/_kit/texkit.py          надписи, ЖКИ (системный Python + Pillow)
assets/<радио>/scripts/
  layout_<радио>.py            все размеры и раскладка — их читают и геометрия, и печать
  make_prints_<радио>.py       надписи лица/боков/тыла, ЖКИ -> textures/
  build_<радио>.py             build(m) по уровням: 0 - детальная, 1..4 - игровые лоды
assets/<радио>/work/<радио>_high.blend   детальная модель, пишет `-- --high-only`
assets/<радио>/work/<радио>_game.blend   игровые лоды, пишет каждая сборка
```

Из `work/` в git только эти два `.blend`: остальное там (запечённое `bake/*.npy` — около 1 ГБ на
рацию, текстуры, рендеры) воспроизводится скриптами. `.blend` ссылаются на картинки из `work/` и
`textures/` — открывать их после сборки.

Порядок: `python make_prints_<радио>.py` → `blender -b -P build_<радио>.py`
(`-- --high-only` только детальная и превью; `-- --skip-bake` переиспользует запечённое;
`-- --passes albedo` перепекает только названные проходы, остальные берёт из кэша) →
`asset_build(mod="OpenZone_Radio", source="model/<радио>")` → `mod_build` → стенд (всё — проект
dayz-mcp в корне репозитория). Печать и Blender для нескольких раций подряд —
`bash tools/build_all.sh [радио ...] [-- флаги]`. Сборка пишет свежий MLOD в
`build/model-root/OpenZone_Radio/model/<радио>/` (корень binarize, `[build] project_root` в
`dayz-mcp.toml`), а `asset_build` кладёт ODOL в `OpenZone_Radio/model/<радио>/`; текстуры, rvmat и
model.cfg сборка пишет туда сама, так что после правки одной печати хватает перепекания цвета и
`mod_build`. Проверка готовой модели: в ODOL есть строки `openzone_radio\model\` и нет чужих
префиксов. Общий снимок линейки — `tools/render_lineup.py`.

## Окно частот «лицом рации» (клавиша K)

Мод открывает по K одно окно на все рации (`OZR_FreqMenu`). Лицо той рации, что в руках, ему
даёт `OpenZone_Radio/scripts/5_Mission/OpenZone_Radio/OZR_FreqMenuFace.c` — modded class в том же
модуле (в Enforce он видит private-поля оригинала; файл обязан идти по алфавиту после
`OZR_FreqMenu.c`). Кнопки разметки носят имена кнопок окна (`Btn0..9`, `BtnUp/Down`, `BtnGo`,
`BtnDot`, `BtnClose`, `DragBar`) — его набор, проверка полосы и запрос к серверу работают как
есть. Своё: `BtnBack` (стереть, а если нечего — выйти), режим `step` у раций без цифр (T-388,
LXT: стрелка сразу переключает канал, окно остаётся), автоточка, два ряда экрана. Что за лицо
у класса — поля `ozrFace*` в `OpenZone_Radio/config.cpp`; класс без них получает обычное окно.

```
tools/hud_spec.py           режим, масштаб, стиль экрана и РОЛИ КЛАВИШ по рациям
tools/render_hud_faces.py   Blender: лицо LOD1 из <рация>_game.blend
tools/make_hud_layouts.py   чистит экран, пишет .edds и .layout в OpenZone_Radio/gui/
```

- **Поменял модель или `layout_<s>.py` рации — перегенерируй её окно**:
  `blender -b -P tools/render_hud_faces.py -- <рация>`, затем
  `python tools/make_hud_layouts.py <рация>`. Разметка читает раскладку заново, а картинка
  лица — со старой модели, пока её не перерендерили: зоны клавиш и экран разъедутся
  (так было с T-388 24.09).
- Текстуры окна — `.edds` с ЛИНЕЙНЫМИ значениями (генератор делает сам). Интерфейс кодирует
  пиксели в sRGB при выводе: записанное как есть выходит блёклым, `.paa` с любым суффиксом —
  тоже. Подробности — в скилле, hud.md.
- Проверка на стенде: рация в руки (`world_spawn … hands`), `Battery9V` вложением,
  `world_power`, `client_type("k")`, потом `ui_find`/`ui_click` по именам кнопок. Для `ui_*`
  мост dayz-mcp грузится и на клиент (`server_only = []` в local toml).

## Кадр модели (снят с ванильной WalkieTalkie.p3d, не придуман)

- В Blender: X вправо, Y назад (лицо в -Y), Z вверх, начало — центр дна корпуса.
- В p3d: `(x, y, z) = (x_b, z_b, y_b)` — лицо в -Z, как у ванильной рации. Хват
  `PersonalRadio.anm` и слот на лямке рюкзака рассчитаны на этот кадр; все наследники
  `PersonalRadio` получают хват от ванили без скриптов.

## Бюджеты

- 4 визуальных лода, примерно вдвое на ступень; `lodnoshadow = 1` на всех (как у ванильной рации).
- Geometry: `autocenter = 0`, масса 0.25 кг, две выпуклые компоненты — корпус и антенна (как у
  ванили); Fire: корпус `plastic_material`, антенна `rubber`.
- Атлас на рацию: `_co`/`_nohq` 2048 (запекание 4096 и уменьшение), `_smdi` 1024; нормали
  DirectX.
- Имя p3d уникальное, с префиксом `oz_radio_`.

## Тестовый стенд

Один на машину: один `dayz-mcp` (`D:\modding\tools\dayz-mcp`) и один DayZ на порту **2402**.
Останавливайте сервер, когда закончили. `mod_build` требует остановленного сервера.
Проект dayz-mcp — корень репозитория. Стенду нужны @CF, @VPPAdminTools и **OpenZone Core**
(Workshop 3798432022) — в `[mods] extra` локального `dayz-mcp.local.toml`. Склейки
@OpenZone_Radio_PDA и @OpenZone_Radio_VPP жёстко требуют КПК и VPP-ядра: на стенде без них их
папки сборки переименовывают в `off-@…` (в `.gitignore`), и сервер их не грузит.

**Стенд идёт на выделенном сервере** (`[machine] server` в `dayz-mcp.local.toml` =
`E:\SteamLibrary\steamapps\common\DayZServer`), а не на DayZDiag из папки клиента. Причина:
рации друга нужен серверный прокси частот — `hid.dll` + `oz_frequencies.json` рядом с
`DayZServer_x64.exe` (релиз `proxy-v1.0.0` репозитория OpenZone-DayZ/openzone-radio, собран
GitHub Actions из `native/src`; SHA256 архива сверен с заметками релиза). Без него мод рации
работает на восьми ванильных частотах и пишет в лог «engine's frequency table is not an even
grid… unpatched server». В папку клиента прокси класть нельзя: BattlEye блокирует неподписанную
DLL в обычной игре. Клиент к такому стенду — ретейльный, через DayZ_BE.

- Проверка: `oz_frequencies.log` рядом с сервером должен сказать `patched: redirected 12 bytes`
  и `channels: 400, from 136.000 MHz…`; сетку мод сам пишет в
  `<stand_root>/profiles/OpenZone/OZ_Radio_Frequencies.json`.
- Прокси патчит **каждый** сервер из этой папки (bat-стенды пистолета, keybox, гильз,
  Immersive Placing — у них тоже 400 каналов). Откат — удалить `hid.dll` и
  `oz_frequencies.json` из папки сервера.
