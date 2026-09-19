# Publishing to the Steam Workshop

**Published 2026-09-01:** https://steamcommunity.com/sharedfiles/filedetails/?id=3794105144

All three mods are on the Workshop since 2026-09-09; the ids are in the Ready list. What
is ready, what is not, and what has to be decided by a person.

*Українською — нижче, у другій половині файла.*

> **Superseded 2026-09-09.** The owner decided to publish **every** OpenZone mod, the
> two glue mods included: OpenZone Core and OpenZone PDA go to the Workshop as well, so
> a subscriber can satisfy the hard dependencies there. The same `ZoneProtocol` key now
> signs the whole series (`keys/` in every repository, private half never committed),
> and every repository carries `packaging/` and `package.ps1` copied from this one.

## Ready

- **All three mods are on the Workshop** since 2026-09-09:
  [OZ_Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=3794105144),
  [OZ_Radio_PDA](https://steamcommunity.com/sharedfiles/filedetails/?id=3798437416),
  [OZ_Radio_VPP](https://steamcommunity.com/sharedfiles/filedetails/?id=3798437535);
  each `packaging/<Mod>/meta.cpp` carries its id. The glue mods' dependencies are hard,
  so a subscriber needs OpenZone Core and OpenZone PDA from the Workshop too -- which is
  why the 2026-09-01 decision to ship only `@OpenZone_Radio` was superseded (see above).
  Three Workshop items, three mods in git.
- **Signed.** Key `ZoneProtocol`, created 2026-09-01 with `DSCreateKey`. All three pbos
  carry `*.ZoneProtocol.bisign`, and `keys/ZoneProtocol.bikey` is placed inside every
  `@Mod` folder at build time, so a server running `verifySignatures = 2` can accept
  them. The key lives once in git, in `keys/` at the repository root.
  > **The private key is not in git and must never be.** `keys/ZoneProtocol.biprivatekey`
  > exists only on the build machine and is covered by `.gitignore`. **Back it up
  > somewhere outside this repository.** Losing it means every future release is signed
  > by a different key, and every server that installed the old `.bikey` has to replace
  > it. Anyone who obtains it can sign a mod as you.
- **`@OpenZone_Radio` runs on OpenZone Core** (since 2026-09-20; before that it stood
  alone on Community Framework, verified by a boot with nothing else). `requiredAddons`
  names `DZ_Data`, `DZ_Scripts`, `JM_CF_Scripts` and `OpenZone_Core`; every script symbol
  in the pbo still lives in its own `OZR_` namespace, and the wire is the core's: the
  ether rides the sync packet, tuning and push-to-talk the service pair.
- **`mod.cpp` in all three mods.** Without it DayZ shows the bare folder name and
  nothing else — no author, no version, no description. Each one names its hard
  dependencies in the description, so a server owner learns about them before the
  blocking window rather than from it.
- **The band works without the native library.** The mod detects the unpatched engine,
  writes `the engine's frequency table is not an even grid (8 bands) — radio profiles
  stay unapplied; this is what an unpatched server looks like`, and leaves vanilla
  alone. Nothing breaks; the operator simply gets eight channels.
- **Workshop listings** in English and Ukrainian, Steam BBCode, one file per item beside
  the packaging folders (`packaging/<Mod>.workshop.bbcode`;
  [`workshop-description.md`](workshop-description.md) points there). They tell a server
  owner that widening the band needs a server-side mod and link the repository for the
  setup, because the Workshop cannot carry it.

## Not ready, and each needs a person

**A picture and a logo.** `mod.cpp` deliberately does not point at `picture` or `logo`
files: DayZ draws a blank for a missing texture and says nothing, so a wrong path is
worse than none. Add the fields when the art exists.

**The version number.** `mod.cpp` says `0.1` in all three. It is a claim about maturity
that the Workshop shows to strangers.

**The unproven claim.** The README says so plainly and the Workshop text does not repeat
it: nobody has yet *heard* two players on distant channels fail to hear each other. The
frequencies are distinct and the router keys on their bytes, so the risk is small — but
"measured distinct" and "heard separated" are different sentences. Two players, two
handheld radios, eight presses of tune apart.

## Publishing again

The `@Mod` folders are **build output and are not in git**. Three steps, in order:

```powershell
# 1. pack and sign        -> @OpenZone_Radio/addons/
mod_build                  # via the dayz MCP, or Addon Builder by hand

# 2. put the rest in place -> mod.cpp, meta.cpp, keys/
.\package.ps1

# 3. upload
```

Then give **Publisher** the folder itself:

```
E:\openzone\openzone-radio\@OpenZone_Radio
```

Not the repository, not `packaging/`, not `addons` inside it.

**Do not skip step 2.** `mod_build` writes only `addons/`; the files that make the folder
a publishable mod come from `packaging/`. `.\package.ps1 -Check` says what is missing or
stale without changing anything.

### meta.cpp, and why it is in packaging/

`meta.cpp` ties a local folder to a Workshop item. Without it the next upload creates a
**second** item instead of updating this one.

The first publish (2026-09-01, item 3794105144) left none — the folder held `addons`,
`keys` and `mod.cpp` and nothing else, and a search of the machine found no `meta.cpp`
and no file containing the id anywhere. It was reconstructed from the Workshop URL, in
the format an installed Workshop mod carries, and it lives in `packaging/` so that
deleting a build folder can never take it away again.

`timestamp` is deliberately absent: it means "when this build was uploaded", and a
number invented to fill it would be false in a file whose only job is bookkeeping.
Publisher writes a real one.

**If Publisher rewrites `meta.cpp`** — a new timestamp, or an id for a mod published for
the first time — copy it back into `packaging/<Mod>/` and commit it. Otherwise the next
`package.ps1` overwrites Publisher's version with the older one.

**If a publish still forks a second item**, the id is not being read: publish once more
from a folder Publisher assembled itself, then commit that `meta.cpp` over this one.

The owner drives Publisher — the GUI tools are not run from here.

---

# Публікація в Steam Workshop

> **Скасовано 2026-09-09.** Власник вирішив публікувати **кожен** мод OpenZone, обидві
> склейки включно: OpenZone Core і OpenZone PDA теж ідуть у Workshop, тож жорсткі
> залежності підписник задовольнить там само. Той самий ключ `ZoneProtocol` тепер
> підписує всю серію (`keys/` у кожному репозиторії, приватна половина не комітиться),
> і кожен репозиторій має `packaging/` та `package.ps1`, скопійовані звідси.

Що готове, що ні, і що мусить вирішити людина. Написано 2026-09-01 під час підготовки до
першої публікації.

## Готове

- **У Workshop усі три моди** з 2026-09-09:
  [OZ_Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=3794105144),
  [OZ_Radio_PDA](https://steamcommunity.com/sharedfiles/filedetails/?id=3798437416),
  [OZ_Radio_VPP](https://steamcommunity.com/sharedfiles/filedetails/?id=3798437535);
  id кожного лежить у `packaging/<Mod>/meta.cpp`. Залежності склейок жорсткі, тож
  підписнику потрібні ще OpenZone Core і OpenZone PDA з Workshop -- саме тому рішення
  2026-09-01 «лише `@OpenZone_Radio`» скасовано (див. вище). Три елементи Workshop,
  три моди в git.
- **Підписано.** Ключ `ZoneProtocol`, створений 2026-09-01 через `DSCreateKey`. Усі три
  pbo несуть `*.ZoneProtocol.bisign`, а `keys/ZoneProtocol.bikey` кладеться в кожну теку
  `@Mod` під час збірки, тож сервер із `verifySignatures = 2` їх прийме. У git ключ
  лежить один раз — у `keys/` в корені репозиторію.
  > **Приватного ключа в git немає, і бути не мусить.** `keys/ZoneProtocol.biprivatekey`
  > існує лише на складальній машині й покритий `.gitignore`. **Зробіть резервну копію
  > поза цим репозиторієм.** Втратити його означає, що кожен наступний випуск підписаний
  > іншим ключем, і кожен сервер, який поставив старий `.bikey`, мусить його замінити.
  > Хто його дістане, зможе підписувати моди вашим ім'ям.
- **`@OpenZone_Radio` працює на OpenZone Core** (з 2026-09-20; до того він стояв сам на
  Community Framework, що перевірено бутом без нічого іншого). У `requiredAddons` —
  `DZ_Data`, `DZ_Scripts`, `JM_CF_Scripts` і `OpenZone_Core`; усі скриптові імена pbo,
  як і раніше, живуть у власному просторі `OZR_`, а провід — ядерний: ефір їде пакетом
  синхронізації, настройка й PTT — парою служби.
- **`mod.cpp` в усіх трьох модах.** Без нього DayZ показує голу назву теки й більше
  нічого — ні автора, ні версії, ні опису. Кожен називає свої жорсткі залежності в
  описі, щоб власник сервера дізнався про них до блокуючого вікна, а не з нього.
- **Ефір працює й без нативної бібліотеки.** Мод розпізнає непропатчений рушій, пише
  `the engine's frequency table is not an even grid (8 bands) — radio profiles stay
  unapplied; this is what an unpatched server looks like` і лишає ваніль недоторканою.
  Нічого не ламається; оператор просто отримує вісім каналів.
- **Описи для Workshop** англійською та українською, у Steam BBCode, по файлу на предмет
  поруч із теками packaging (`packaging/<Mod>.workshop.bbcode`;
  [`workshop-description.md`](workshop-description.md) веде туди). Вони кажуть власнику
  сервера, що для розширення ефіру потрібен серверний мод, і ведуть у репозиторій по
  установку, бо Workshop нести його не може.

## Не готове, і кожне потребує людини

**Картинка й логотип.** `mod.cpp` навмисне не вказує на `picture` і `logo`: DayZ малює
порожнечу замість відсутньої текстури й мовчить, тож хибний шлях гірший за відсутній.
Додати поля, коли з'явиться арт.

**Номер версії.** У `mod.cpp` в усіх трьох стоїть `0.1`. Це твердження про зрілість, яке
Workshop показує стороннім.

**Недоведене твердження.** README каже це прямо, а текст Workshop не повторює: ніхто ще
не **чув**, як двоє гравців на далеких каналах не чують одне одного. Частоти різні, а
маршрутизатор ключується на їхніх байтах, тож ризик малий — але «зміряно різними» і
«почуто роздільними» це різні речення. Двоє гравців, дві ручні рації, вісім натискань
«налаштувати» одне від одного.

## Публікація ще раз

Теки `@Mod` — це **результат збірки, і в git їх немає**. Три кроки, по порядку:

```powershell
# 1. запакувати й підписати -> @OpenZone_Radio/addons/
mod_build                    # через MCP dayz або Addon Builder руками

# 2. покласти решту          -> mod.cpp, meta.cpp, keys/
.\package.ps1

# 3. вивантажити
```

Далі **Publisher** отримує саму теку:

```
E:\openzone\openzone-radio\@OpenZone_Radio
```

Не репозиторій, не `packaging/`, не `addons` усередині неї.

**Крок 2 не пропускати.** `mod_build` пише лише `addons/`; файли, які роблять теку
модом, придатним до публікації, беруться з `packaging/`. `.\package.ps1 -Check` скаже,
чого бракує або що застаріло, нічого не змінюючи.

### meta.cpp, і чому він у packaging/

`meta.cpp` прив'язує локальну теку до елемента Workshop. Без нього наступна вивантаження
створює **другий** елемент замість оновлення цього.

Перша публікація (2026-09-01, елемент 3794105144) його не лишила — у теці були `addons`,
`keys` і `mod.cpp`, і більше нічого, а пошук по машині не знайшов ані `meta.cpp`, ані
жодного файла з цим номером. Його відновили з URL Workshop, у форматі, який несе
встановлений мод із Workshop, і живе він у `packaging/`, щоб видалення теки збірки більше
ніколи його не забрало.

`timestamp` навмисно відсутній: він означає «коли цю збірку вивантажили», і вигадане
число було б неправдою у файлі, чия єдина робота — облік. Publisher запише справжній.

**Якщо Publisher перепише `meta.cpp`** — новий timestamp або id мода, опублікованого
вперше, — скопіюйте його назад у `packaging/<Мод>/` і закомітьте. Інакше наступний
`package.ps1` перезапише версію Publisher старішою.

**Якщо публікація все одно роздвоїть елемент**, номер звідти не читається: опублікуйте ще
раз із теки, яку зібрав сам Publisher, і закомітьте той `meta.cpp` поверх цього.

Publisher запускає власник — GUI-інструменти звідси не запускаються.
