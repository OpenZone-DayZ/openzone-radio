// Профілі ручних рацій -- те, що адмін описує сам.
//
// Профіль каже про ОДИН класнейм: який відрізок ефіру йому доступний і через
// скільки МГц він крокує. Дальність сюди не входить: вона живе в config.cpp
// класу (`range`), бо її читає сам рушій, а не ми.
//
// Типово смуга в усіх ОДНА -- 136.000..155.950 МГц кроком 0.050, тобто 400
// каналів (рішення власника 2026-09-12; замінило драбину з десяти різних
// відрізків і кроків, яка виводила 1281 ділення). Тири розрізняються
// дальністю з config.cpp класу, а не ефіром: будь-які дві рації завжди
// можуть зійтися на одному каналі, питання лише в тому, чи дістануть одна
// одну. Адмін вільний описати інакше -- це його файл.

class OZR_Profiles : OZR_ConfigBase
{
    ref array<ref OZR_RadioProfile> Radios;

    private static ref OZR_Profiles s_Inst;

    static OZR_Profiles Get()
    {
        return s_Inst;
    }

    override int LatestVersion()
    {
        return OZR_Const.SCHEMA_PROFILES;
    }

    // Одна смуга на всі сім класів. Дальність кожного стоїть у
    // config.cpp його класу (рушій читає її звідти й нізвідки більше); тут --
    // лише ефір, і він у всіх той самий.
    //
    // 136.000..155.950 кроком 0.050 -- це 400 ділень: (155.95 - 136.0) / 0.05
    // + 1. Усі кратні 0.0001 МГц (OZR_Ether.UNITS_PER_MHZ) і всі різні у
    // float32. Ефір, виведений із цього (OZR_Ether.Derive), -- база 136.0,
    // крок 0.05, 400 -- збігається із запасним дефолтом бібліотеки в
    // native/oz_frequencies.json і з зашитим у неї (dllmain.cpp, g_config):
    // три копії одного числа, і мінятись вони мусять разом.
    private static const float BAND_LO   = 136.0;
    private static const float BAND_HI   = 155.95;
    private static const float BAND_STEP = 0.05;

    override void LoadDefaults()
    {
        Version = LatestVersion();
        Radios  = new array<ref OZR_RadioProfile>();

        Add("OZ_Radio_250m",   BAND_LO, BAND_HI, BAND_STEP);
        Add("OZ_Radio_500m",   BAND_LO, BAND_HI, BAND_STEP);
        Add("OZ_Radio_1000m",  BAND_LO, BAND_HI, BAND_STEP);
        Add("OZ_Radio_2000m",  BAND_LO, BAND_HI, BAND_STEP);
        Add("OZ_Radio_5000m",  BAND_LO, BAND_HI, BAND_STEP);
        Add("OZ_Radio_10000m", BAND_LO, BAND_HI, BAND_STEP);

        // Плата в КПК -- така сама рація, тільки в відсіку, і профіль їй
        // потрібен той самий. Клас оголошує @OpenZone_Radio_PDA; без нього
        // рядок просто нікому не відповідає, і це нікому не шкодить.
        Add("OZ_Module_Radio", BAND_LO, BAND_HI, BAND_STEP);
    }

    private void Add(string cls, float lo, float hi, float step)
    {
        OZR_RadioProfile p = new OZR_RadioProfile();
        p.ClassName = cls;
        p.MinMHz    = lo;
        p.MaxMHz    = hi;
        p.StepMHz   = step;
        Radios.Insert(p);
    }

    // Migrate тут НЕ перевизначений навмисно. Схема одна (SCHEMA_PROFILES == 1),
    // і override, який побайтово повторював базову реалізацію, лише обіцяв
    // переніс, якого не буває. Повернути його -- справа того дня, коли схема
    // рушить із місця; OZR_Settings живе на тій самій базі й без нього.

    override void Validate(out int warnings)
    {
        warnings = 0;

        if (!Radios)
            Radios = new array<ref OZR_RadioProfile>();

        // ПЕРЕСАДКА ВКЛАДЕНОГО -- ПЕРШИМ ДІЛОМ І ОДНИМ ПРОХОДОМ.
        //
        // Кожен елемент Radios виділив серіалізатор, а не скрипт: ані
        // конструктора, ані ініціалізаторів полів, і члени без значення у
        // файлі -- сира пам'ять (доказ і механізм -- у шапці OZR_Cfg.c).
        // Validate кличуть ОДРАЗУ після розбору, тобто це остання мить, коли
        // читання ще чесне: далі власник об'єкта Copy() уже не встигне --
        // саме тому пересадка тут, а не в ServerLoad.
        //
        // ОКРЕМИМ ПРОХОДОМ, а не всередині циклу перевірок нижче: правило --
        // «до наступного виділення», а той цикл на кожній невдалій сходинці
        // склеює рядок попередження. Пересадивши всіх спершу, ми читаємо
        // Problem() уже з об'єктів, зроблених скриптом.
        //
        // УМОВЧАННЯ ВКЛАДЕНИХ ЧЛЕНІВ після копії -- нулі, а не те, що стоїть
        // в оголошенні полів OZR_RadioProfile. Для профілю це саме те, що
        // треба: смуги за замовчуванням не буває, і нуль у будь-якому з
        // чотирьох полів Problem() називає поіменно й такий профіль
        // викидається -- замість того, щоб мовчки поїхати на чужих байтах.
        for (int c = 0; c < Radios.Count(); c++)
        {
            OZR_RadioProfile raw = Radios[c];
            if (raw)
                Radios.Set(c, raw.Copy());
        }

        // ЩО ТУТ ВИКИДАЄТЬСЯ, А ЩО ЛИШЕ ЗГАДУЄТЬСЯ.
        //
        // Викидається те, з чого не можна вивести НІЧОГО: порожній елемент,
        // профіль без імені, порожня чи перевернута смуга, нульовий крок,
        // межа понад стелю. Такий профіль зламав би і виведення ефіру, і саму
        // рацію. Перелік не тут -- він один на весь мод, у
        // OZR_RadioProfile.Problem.
        //
        // ПЕРШИМ, І НЕЗАЛЕЖНО ВІД СІТКИ. Раніше цей цикл стояв ПІСЛЯ виходу
        // «сітка нерівна», тобто на непропатченому сервері не виконувався
        // взагалі -- і порожній елемент масиву доживав до першого ж запиту
        // ефіру, який розіменовував його без перевірки (нині -- до першого
        // OZR_EtherServer.Fill).
        for (int i = Radios.Count() - 1; i >= 0; i--)
        {
            OZR_RadioProfile p = Radios[i];

            if (!p)
            {
                OZR_Log.Warn("an empty entry in the radio profile list dropped");
                Radios.Remove(i);
                warnings++;
                continue;
            }

            string bad = p.Problem();
            if (bad != "")
            {
                OZR_Log.Warn("profile " + p.Named() + " " + bad + " - dropped");
                Radios.Remove(i);
                warnings++;
            }
        }

        // Далі -- лише те, що має сенс проти ЖИВОЇ сітки. Без рівномірної
        // сітки рахувати нічим; це не поломка, а те, як виглядає
        // непропатчений сервер із ванільною нерівною вісімкою. Кажемо про це
        // ОДИН раз і лишаємо профілі як є -- вони просто не застосуються.
        if (!OZR_Grid.Ready())
        {
            string flat = "the engine's frequency table is not an even grid (";
            flat += OZR_Bands.Count().ToString();
            flat += " bands) - radio profiles stay unapplied; this is what an unpatched server looks like";
            OZR_Log.Warn(flat);
            warnings++;
            return;
        }

        float lo = OZR_Grid.Base();
        float hi = OZR_Grid.MHzAt(OZR_Grid.Count() - 1);

        // Межі лишаються як написано. Раніше тут обрізали їх під сітку й
        // округляли крок -- і це було правильно, поки сітка була чимось
        // зовнішнім. Тепер сітка ВИВОДИТЬСЯ з цих самих чисел, і переписати їх
        // під стару сітку означало б знищити те, з чого будують нову: адмін
        // просить 86 МГц, ми обрізаємо до 136, ефір виводиться з 136, і 86 не
        // настає ніколи. Тому тут лише кажуть вголос, що профіль випереджає
        // ефір, а обрізає ВИКОРИСТАННЯ (OZR_Grid.Window) -- до наступного
        // старту сервера.
        for (int k = 0; k < Radios.Count(); k++)
        {
            OZR_RadioProfile q = Radios[k];
            if (q.MinMHz >= lo && q.MaxMHz <= hi)
                continue;

            string ahead = "profile " + q.ClassName + " asks for ";
            ahead += OZR_Fmt.MHz(q.MinMHz) + ".." + OZR_Fmt.MHz(q.MaxMHz);
            ahead += " MHz while the running ether is " + OZR_Fmt.MHz(lo);
            ahead += ".." + OZR_Fmt.MHz(hi);
            ahead += " - it works on the overlap until the server is restarted";
            OZR_Log.Warn(ahead);
            warnings++;
        }
    }

    // ОБ'ЄКТ ІЗ ЗАВАНТАЖУВАЧА ЖИВЕ РІВНО ДО КІНЦЯ РОЗБОРУ -- далі тільки копія.
    //
    // JsonFileLoader<T> -- тонка обгортка над нативним JsonSerializer, тож
    // усе ВКЛАДЕНЕ створює РУШІЙ: ані конструктор, ані ініціалізатори полів
    // (`= ""`, `= 0`) не виконуються, а сам розбір присвоює лише ті члени, для
    // яких знайшов значення. Решта лишається тим, що лежало за цим зміщенням.
    // Одразу після розбору сторінка ще свіжо занулена, тому перші читання
    // виглядають правильними; за хвилину купа зрушила, і те саме поле віддає
    // чуже сміття -- при цьому `if (x != "")` на ньому ІСТИННЕ. Зміряно на
    // стенді фракцій 2026-09-06 (рядок звання читався то "3", то "$").
    //
    // САМІ ПРОФІЛІ ПЕРЕСАДЖУЄ ВЖЕ VALIDATE -- він єдиний біжить одразу після
    // розбору. Тут лишається те, чого Validate зробити не може: сам МАСИВ і
    // корінь. Масив теж виділив серіалізатор, s_Inst живе весь запуск
    // сервера, і його поля читає кожен тюн, кожен спавн і кожен запит
    // сторінки -- тож копія коштує один прохід на бут і знімає питання.
    //
    // Порожній елемент тут ВИКИДАЄТЬСЯ, і саме це робить безпечним
    // неперевірений Radios[i] в OZR_Ether.Derive. Хто мусить не викинути, а
    // ВІДМОВИТИ (аплікатор VPP -- межа довіри), шукає порожні до копії.
    OZR_Profiles Copy()
    {
        OZR_Profiles c = new OZR_Profiles();
        c.Version = Version;
        c.Radios  = new array<ref OZR_RadioProfile>();

        if (!Radios)
            return c;

        for (int i = 0; i < Radios.Count(); i++)
        {
            OZR_RadioProfile p = Radios[i];
            if (!p)
                continue;
            c.Radios.Insert(p.Copy());
        }
        return c;
    }

    // Профіль за класнеймом, або порожньо. Порожньо означає «ця рація не наша»
    // -- ванільні й чужі рації лишаються з ванільною поведінкою.
    static OZR_RadioProfile For(string className)
    {
        if (!s_Inst || !s_Inst.Radios)
            return null;

        for (int i = 0; i < s_Inst.Radios.Count(); i++)
        {
            if (s_Inst.Radios[i].ClassName == className)
                return s_Inst.Radios[i];
        }
        return null;
    }

    // Чи можна писати похідне від цього файлу.
    //
    // false означає одне: файл на диску є, і ми його НЕ ЗРОЗУМІЛИ, тобто
    // працюємо на дефолтах, яких адмін не писав. Виводити з них ефір і класти
    // його поверх робочого OZ_Radio_Frequencies.json -- значить після одного
    // зіпсованого старту втратити всі власні смуги мовчки. Той самий прапорець
    // і з тієї ж причини стоїть у ядрі (OZ_Settings.Writable).
    private static bool s_Writable = true;

    static bool Writable()
    {
        return s_Writable;
    }

    static void ServerLoad()
    {
        OZR_Profiles loaded = new OZR_Profiles();
        s_Writable = OZR_ConfigLoader<OZR_Profiles>.Load(OZR_Const.PROFILES, "RadioProfiles", loaded);

        // Профілі пересадив уже Validate усередині Load; тут переписуємо
        // масив і корінь -- див. Copy() вище.
        s_Inst = loaded.Copy();
    }
}
