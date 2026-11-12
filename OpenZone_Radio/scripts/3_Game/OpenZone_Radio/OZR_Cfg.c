// Версійований JSON-конфіг -- ВЛАСНИЙ, а не ядерний.
//
// Це майже дослівна копія OZ_ConfigBase/OZ_ConfigLoader з OpenZone_Core, і
// копія тут зроблена свідомо. Причина не в тому, що ядро погане, а в тому, що
// в DayZ немає необов'язкових посилань: клас із незавантаженого мода не можна
// згадати навіть у мертвій гілці, а порядок компіляції задається лише
// requiredAddons -- тобто ЖОРСТКОЮ залежністю. Отже «користуватись ядром,
// якщо воно є» неможливо: або жорстко залежати, або мати своє.
//
// Ручна рація ядра не потребує ні для чого іншого, і платити за дев'яносто
// три рядки блокуючим вікном «requires addon OpenZone_Core» на сервері, де
// ядра свідомо немає, -- погана угода. Тому вони тут.
//
// Що саме дає ця обгортка, крім читання файлу: версію схеми й міграцію. Конфіг
// без версії -- це файл, який після зміни формату мовчки читається як сміття;
// з версією він або мігрує, або скаржиться, і в обох випадках адмін дізнається
// про це від нас, а не від наслідків.
//
// ------------------------------------------------------------------------
// КОРІНЬ І ВКЛАДЕНЕ -- ЦЕ ДВА РІЗНІ ВИПАДКИ, І ПЛУТАТИ ЇХ ДОРОГО
// (зміряно 2026-09-06, persistence-networking.md; те саме записано в шапці
// ядерного OZ_ConfigBase.c).
//
// JsonFileLoader -- тонка обгортка над рідним JsonSerializer.ReadFromString,
// а той оголошений як `proto bool ReadFromString(void variable_in, ...)`.
// `variable_in`, не `out`: КОРЕНЕВИЙ об'єкт заповнюється на місці, тобто той
// самий, що дав викликач. Тому корінь тут безпечний -- його створює
// скриптовий `new` (OZR_Settings.ServerLoad, OZR_Profiles.ServerLoad), його
// ініціалізатори виконались, і поле, якого у файлі немає, лишається з тим,
// що написано в оголошенні.
//
// А от УСЕ ВКЛАДЕНЕ -- кожне `ref`-поле й кожен елемент масиву -- виділяє САМ
// серіалізатор, і конструктор скрипта на них не кличеться. Член, якому він не
// знайшов значення у файлі, -- сира пам'ять: одразу після розбору сторінка ще
// обнулена й читається правильно, а за хвилину на тому самому зміщенні лежать
// чужі байти. Найзвичайніший шлях у цю пастку -- не зіпсований файл, а НОВЕ
// ПОЛЕ В КЛАСІ: живі файли його не несуть, а LoadDefaults на успішному
// розборі не кличеться.
//
// ЩО ЦЕ ВИМАГАЄ ВІД НАЩАДКА: дай кожному вкладеному класу Copy() (новий
// `new` свого типу, поле за полем) і пересади в нього кожен вкладений об'єкт
// із САМОГО Validate(). Validate -- єдине правильне місце: Load кличе його
// одразу після розбору, поки читання ще чесне, і тільки там пересадка
// випереджає наступне виділення. Після копії вкладене поле, якого у файлі не
// було, тримає НУЛЬ, а не свій ініціалізатор, -- тож справжні умовчання
// вкладених членів виставляє теж Validate. Приклад -- OZR_Profiles.Validate.
// ------------------------------------------------------------------------

class OZR_ConfigBase
{
    int Version = 0;

    // Перевизначаються нащадком. База навмисне робить найтихіше, що можна:
    // конфіг, який нічого не переносить і нічого не перевіряє, -- законний.
    //
    // Validate МУСИТЬ пересадити кожен вкладений об'єкт, який конфіг лишає
    // собі, у створений скриптом -- або виставити кожен його член сам. Чому
    // саме так -- у шапці цього файла.
    int  LatestVersion()            { return 1; }
    void LoadDefaults()             { Version = LatestVersion(); }
    bool Migrate(int from)          { Version = LatestVersion(); return true; }
    void Validate(out int warnings) { warnings = 0; }
}

// Problems of the last load per file (VPP rework 2026-11-12, design 4.3): what Validate
// fixed or warned about, plus one for a file that could not be used. The radio's card on
// Ядро › Огляд sums its files (OZR_Facts). The core keeps the same table for its own
// loader (OZ_ConfigProblems); this copy keeps the loader above free of the core, as the
// header says.
class OZR_CfgProblems
{
    // Made on first use, not in the declaration: a static's initialiser has been seen not
    // to run once (the PDA's OZ_PdaProfiles notes it).
    private static ref map<string, int> s_Of;

    static void Record(string tag, int found)
    {
        if (!s_Of)
            s_Of = new map<string, int>();
        s_Of.Set(tag, found);
    }

    static int Of(string tag)
    {
        int found = 0;
        if (!s_Of || !s_Of.Find(tag, found))
            return 0;
        return found;
    }
}

class OZR_ConfigLoader<Class T>
{
    // cfg ПРИХОДИТЬ УЖЕ СТВОРЕНИМ, і це не стиль, а обмеження мови: `new T()`
    // всередині дженерика Enforce не компілюється -- "Bad type 'T'",
    // "Can't find class T", по парі на кожне інстанціювання. Той самий висновок
    // записаний і в ядрі, і сюди він приїхав удруге, вже своїм коштом.
    // Тому конкретний тип створює викликач, а тут лишається тільки наповнення.
    //
    // ПОВЕРТАЄ, ЧИ МОЖНА ПИСАТИ ПОХІДНЕ ВІД ЦЬОГО ФАЙЛУ. false означає рівно
    // одне: файл на диску є, ми його не зрозуміли й лишили як є, тобто зараз
    // працюємо на дефолтах, яких адмін не писав. Викликач, що ігнорує
    // відповідь, поводиться точно як раніше; той, хто пише щось, ВИВЕДЕНЕ з
    // прочитаного, мусить її спитати -- інакше один зіпсований старт тихо
    // затирає роботу адміна (див. OZR_EtherServer.Publish).
    //
    // Ядерний OZ_ConfigLoader повертає те саме й з тієї ж причини, але вміє
    // більше: карантин зіпсованого файлу, .bak і перезапис після починок у
    // Validate. Ця копія їх не має свідомо -- вона мусить компілюватись без
    // ядра, -- і різниця записана тут, щоб наступний читач не вважав її
    // недоглядом.
    static bool Load(string path, string tag, inout T cfg)
    {
        // NULL -- ВІДМОВА ВГОЛОС, А НЕ «НЕХАЙ СЕРІАЛІЗАТОР СТВОРИТЬ САМ».
        //
        // Створить: рідний ReadFromString виділяє корінь, якого йому не дали.
        // Але виділяє ВІН, отже жоден ініціалізатор поля не виконається, і
        // сирим стає КОЖНЕ поле конфігу, а не лише вкладені. Мовчазне
        // `return false` тут уже стояло; бракувало рядка, за яким це видно.
        //
        // false -- це «не пиши поверх файла»: викликач із порожнім конфігом у
        // пам'яті нічого туди й не покладе. Те саме й з тієї ж причини робить
        // ядерний OZ_ConfigLoader.
        if (!cfg)
        {
            OZR_Log.Error(tag + ": nothing to load into - the caller must pass a constructed object");
            return false;
        }

        bool fresh    = false;
        bool understood = true;
        string err;

        if (!FileExist(path))
        {
            // Записуємо ОДРАЗУ навмисне: адмін мусить побачити на диску файл,
            // який можна правити, а не здогадуватись, які поля бувають.
            cfg.LoadDefaults();
            fresh = true;
        }
        else if (!JsonFileLoader<T>.LoadFile(path, cfg, err))
        {
            // НЕ перезаписуємо. Зіпсований файл -- це, як правило, файл, який
            // хтось щойно правив руками: затерти його умовчаннями означає
            // знищити роботу й приховати помилку.
            OZR_Log.Error(tag + ": " + path + " does not parse (" + err + ") - using defaults, file left alone");
            cfg.LoadDefaults();
            understood = false;
        }
        else if (cfg.Version != cfg.LatestVersion())
        {
            int from = cfg.Version;
            if (!cfg.Migrate(from))
            {
                OZR_Log.Error(tag + ": cannot migrate " + path + " from version " + from.ToString() + " - using defaults, file left alone");
                cfg.LoadDefaults();
                understood = false;
            }
            else
            {
                string moved = tag + ": migrated " + path + " from version " + from.ToString();
                moved += " to " + cfg.Version.ToString();
                OZR_Log.Info(moved);
                fresh = true;
            }
        }

        int warnings = 0;
        cfg.Validate(warnings);
        if (warnings > 0)
            OZR_Log.Info(tag + ": " + warnings.ToString() + " thing(s) worth a look above");

        if (fresh)
            Save(path, tag, cfg);

        int found = warnings;
        if (!understood)
            found++;
        OZR_CfgProblems.Record(tag, found);

        return understood;
    }

    static void Save(string path, string tag, T cfg)
    {
        string err;
        if (!JsonFileLoader<T>.SaveFile(path, cfg, err))
            OZR_Log.Error(tag + ": cannot write " + path + " (" + err + ")");
    }
}
