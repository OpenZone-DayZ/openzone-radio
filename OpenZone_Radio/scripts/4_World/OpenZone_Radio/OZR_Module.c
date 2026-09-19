// Серверна половина мода рації.
//
// Мод несе РУЧНІ рації й нічого більше: плата в відсіку КПК, сторінка та
// оголошення заліза живуть у склейці @OpenZone_Radio_PDA, бо знають про два
// моди одразу. Тут -- чотири кроки старту:
//
//   1. створити каталог профілю, поки в нього ще ніхто не писав;
//   2. виміряти таблицю частот рушія (див. OZR_Bands: число «сім» ніде не
//      оголошене, і вигадувати його не можна);
//   3. прочитати профілі рацій -- або взяти вбудовану драбину, якщо адмін не
//      описав нічого, -- і вивести з них ефір;
//   4. сказати одним рядком, що з цього вийшло, щоб вердикт стенда мав за що
//      зачепитись.
//
// Порядок значущий цілком: профілі перевіряються проти ВИМІРЯНОЇ таблиці, а
// ефір виводиться з профілів.
//
// ВЛАСНИХ RPC ТУТ БІЛЬШЕ НЕМАЄ (2026-09-20, спека серії
// 2026-09-20-radio-on-core-transport-design). Ефір їде клієнтові додатком до
// пакета синхронізації ядра (OZR_EtherServer.Fill -> OZ_Sync), настройка й
// гашетка приходять парою служби ядра (OZR_Service). Разом із сімома CF-RPC
// пішли тяга сітки з клієнта, троттл на неї та лічильник GRID: ядро тягне
// свій пакет саме тоді, коли клієнт готовий його прийняти (OZ_Rpc.Hello), і
// робить це для всієї родини один раз.

[CF_RegisterModule(OZR_Module)]
class OZR_Module : CF_ModuleWorld
{
    override void OnInit()
    {
        super.OnInit();

        // Порядок такий самий, як у решті модів OpenZone: спершу super, потім
        // підписки. Інакше CF не встигає зареєструвати модуль, і подія
        // приходить у порожнечу.
        EnableMissionStart();
        EnableMissionFinish();

        // Стан гашетки гравця йде з ним. Без цього мапа росла б на кожного,
        // хто хоч раз натиснув клавішу, і не зменшувалась ніколи.
        EnableInvokeDisconnect();
    }

    override void OnInvokeDisconnect(Class sender, CF_EventArgs args)
    {
        super.OnInvokeDisconnect(sender, args);

        if (!GetGame().IsServer())
            return;

        // На дисконекті особи може вже не бути, тому CF окремо несе UID.
        CF_EventPlayerDisconnectedArgs dArgs = CF_EventPlayerDisconnectedArgs.Cast(args);
        if (dArgs)
            OZR_Throttle.Forget(dArgs.UID);
    }

    // Таймери дебаг-режиму лагів; див. OZR_Meter і OZR_LoadTest. Заводяться
    // лише коли Profiler увімкнено, тож вимкнений режим не має навіть таймера.
    private ref Timer m_MeterTimer;
    private ref Timer m_LoadTimer;
    private int m_LoadRadios = 0;
    private static const float METER_INTERVAL = 60.0;
    private static const float LOAD_INTERVAL  = 15.0;

    override void OnMissionStart(Class sender, CF_EventArgs args)
    {
        super.OnMissionStart(sender, args);

        // Клієнтської половини тут більше немає: ефір приїздить пакетом ядра,
        // і приймає його OZR_ClientSync із modded MissionGameplay.
        if (!GetGame().IsServer())
            return;

        // Настройка й гашетка -- служба в реєстрі ядра; ефір -- додаток до
        // його пакета синхронізації. Обидві реєстрації до будь-якого читання:
        // порядок CF-модулів не гарантований, але перший клієнт з'явиться в
        // будь-якому разі пізніше за всі OnMissionStart.
        OZ_ServiceRegistry.Register(OZR_Const.SERVICE, new OZR_Service());
        OZ_SyncExtras.OnFill().Insert(OZR_EtherFill);

        // ПЕРЕД БУДЬ-ЯКИМ ЗАПИСОМ. Каталог профілю будує ядро, але порядок
        // CF-модулів не гарантований, і без цього рядка кожен Save мовчки
        // провалювався б -- разом із публікацією сітки частот.
        OZR_Const.EnsureProfileDir();

        // Найперше: рівень діагностики стоїть саме тут, і рядки нижче вже
        // мають на нього зважати.
        OZR_Settings.ServerLoad();

        OZR_Bands.Probe();
        // Після проби: профілі перевіряються ПРОТИ виміряної сітки, і без неї
        // перевіряти нічим.
        OZR_Profiles.ServerLoad();
        // Після профілів: ефір виводиться з них, і виводити його до того,
        // як вони прочитані, нема з чого. Пише файл, який прочитає
        // НАСТУПНИЙ старт сервера, і каже, чи вже діє.
        OZR_EtherServer.Publish(OZR_Profiles.Get());

        int profiles = 0;
        OZR_Profiles cfg = OZR_Profiles.Get();
        if (cfg && cfg.Radios)
            profiles = cfg.Radios.Count();

        string summary = "radio loaded: bands=" + OZR_Bands.Count().ToString();
        summary += " profiles=" + profiles.ToString();
        OZR_Log.Info(summary);

        // Дебаг-режим лагів -- ПІСЛЯ рядка готовності, щоб вердикт стенда не
        // чекав два мільйони викликів самоперевірки.
        OZR_Settings st = OZR_Settings.Get();
        if (st && st.Profiler)
        {
            OZR_LoadTest.SelfCheck();

            m_MeterTimer = new Timer(CALL_CATEGORY_SYSTEM);
            m_MeterTimer.Run(METER_INTERVAL, this, "MeterTick", NULL, true);

            if (st.ProfilerRadios > 0)
            {
                m_LoadRadios = st.ProfilerRadios;
                m_LoadTimer = new Timer(CALL_CATEGORY_SYSTEM);
                m_LoadTimer.Run(LOAD_INTERVAL, this, "LoadTick", NULL, true);
            }
        }
    }

    // Що рація докладає до пакета синхронізації ядра. Кличе інвокер
    // OZ_SyncExtras на кожну відправку -- на вході гравця й на розсилку після
    // адмінської правки, -- тому метод мусить бути видимим (не private).
    void OZR_EtherFill(OZ_SyncPayload p)
    {
        OZR_EtherServer.Fill(p);
    }

    override void OnMissionFinish(Class sender, CF_EventArgs args)
    {
        super.OnMissionFinish(sender, args);

        if (m_MeterTimer)
            m_MeterTimer.Stop();
        if (m_LoadTimer)
            m_LoadTimer.Stop();

        // Дзеркало підписки з OnMissionStart: інвокер ядра статичний і
        // переживе місію, а модуль, що підписався, -- ні.
        OZ_SyncExtras.OnFill().Remove(OZR_EtherFill);

        // Рації-підсилювачі не переживають місію: інакше стенд, який падає
        // замість зупинки, лишав би їх на землі до наступного разу.
        OZR_LoadTest.Clear();
    }

    // Один рядок на хвилину, поки Profiler увімкнено. Кличеться таймером
    // за ім'ям, тому не private.
    void MeterTick()
    {
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        OZR_Log.Info(OZR_Meter.Report(players.Count()));
    }

    // Питає, доки є поруч із ким ставити, потім зупиняє себе.
    void LoadTick()
    {
        if (!OZR_LoadTest.SpawnRadios(m_LoadRadios))
            return;
        if (m_LoadTimer)
            m_LoadTimer.Stop();
    }

    // Гравець за особою відправника -- ОДНИМ СТРИБКОМ.
    //
    // Тут стояв обхід усього онлайну зі звіркою рядків GetId(): «іншого
    // зв'язку між PlayerIdentity й сутністю немає» -- твердження, яке просто
    // не було перевірене. Зв'язок є й нативний: PlayerIdentityBase.GetPlayer()
    // (3_game/gameplay.c:375). Обхід коштував десятки кастів і дві рядкові
    // алокації на гравця на КОЖЕН пакет настройки й на кожен край PTT; той
    // самий фікс уже зроблено в КПК (OZ_PdaAccess.PlayerOf).
    //
    // Різниця в поведінці одна й на краще: застаріла особа перепідключеного
    // гравця тепер дає порожньо, а не його НОВЕ тіло. Для обробника пакета це
    // й є правильна відповідь -- відкривати рацію тому, хто цього пакета не
    // слав, не треба.
    //
    // Статичні -- ними користується служба (OZR_Service), а стану модуля їм
    // не треба.
    static PlayerBase OZR_PlayerOf(PlayerIdentity who)
    {
        if (!who)
            return null;

        return PlayerBase.Cast(who.GetPlayer());
    }

    // Кнопка «говорити» на ручних рацій.
    //
    // Клієнт присилає НАМІР -- один біт, і більше нічого. Які саме передавачі
    // від цього відкриються, вирішує сервер, обійшовши інвентар цього гравця:
    // інакше пакет «говорю» став би способом розкрити чужу рацію.
    //
    // ВІДКРИВАЄТЬСЯ ОДНА РАЦІЯ, а не всі, які гравець несе. Це заміна
    // попереднього рішення, і замінене воно свідомо.
    //
    // Було: відкрити все живе й профільне, бо так робить ваніль -- увімкнена
    // рація везе голос власника хоч із дна рюкзака. Ціна виявилась не тією,
    // на яку розраховували: гравець, що несе три рації на трьох частотах,
    // одним натисканням говорив у три ефіри одразу, і жодного способу
    // сказати «в цю, а не в ту» не було. Ваніль цієї біди не має лише тому,
    // що в неї немає кнопки: там рація везе голос ЗАВЖДИ, і носити три
    // увімкнені рації однаково безглуздо.
    //
    // Правило: та, що В РУКАХ; якщо руки порожні -- та, що НА СЛОТІ й
    // останньою була в руках. Карго не говорить ніколи: рація в рюкзаку --
    // це запасна, а не робоча.
    //
    // ЗАКРИВАЄМО ЗАВЖДИ ВСІ. Несиметрія навмисна: рацію можна прибрати в
    // рюкзак, не відпустивши кнопки, і тоді край відпускання не знайшов би
    // того, кого відкрив край натискання -- передавач лишився б відкритим
    // назавжди. Відкриваємо вузько, закриваємо широко.
    //
    // Ванільних і чужих передавачів обхід не чіпає в обидва боки: їхній ефір
    // цей мод не відкривав, і закривати його теж не його справа.
    //
    // Скільки передавачів перемкнули. Число повертається не для краси: «нуль»
    // -- це єдине, чим відрізняється «гравець натиснув кнопку без рації» від
    // «пакет не дійшов», і без нього обидва випадки виглядають у лозі однаково.
    static int OZR_SetAll(PlayerBase player, bool on, bool locked)
    {
        array<EntityAI> items = new array<EntityAI>();
        if (!player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items))
            return 0;

        // Закриття не вибирає: усе, що цей мод міг відкрити, він і закриває.
        if (!on)
        {
            int shut = 0;
            for (int j = 0; j < items.Count(); j++)
            {
                TransmitterBase c = TransmitterBase.Cast(items[j]);
                if (!c || !OZR_Profiles.For(c.GetType()))
                    continue;

                if (c.OZR_SetSpeaking(false, false))
                    shut++;
            }
            return shut;
        }

        TransmitterBase pick = OZR_PickSpeaker(player, items);
        if (!pick)
            return 0;

        // Нуль і тут можливий: рацію могли вимкнути між пакетом і його
        // обробкою. Лічити вибір замість результату означало б писати в лог
        // "opens 1" над мовчазним ефіром -- саме так ця вада й ховалась.
        if (!pick.OZR_SetSpeaking(true, locked))
            return 0;

        return 1;
    }

    // Кого саме відкрити.
    //
    // Руки за все: рація в долоні -- це вже сказане вголос «говорю в цю», і
    // жодне інше правило не мусить це перебивати.
    //
    // Далі -- слоти, і серед них найсвіжіша за часом останнього тримання.
    // Час веде саме тому, що місце не розрізняє: дві рації на двох слотах
    // виглядають однаково, а діставали одну.
    //
    // Порожня пам'ять -- окремий випадок, і мовчанням він закінчуватись не
    // може. Після рестарту сервера жодна рація в руках ще не була, і правило
    // «остання в руках» не має відповіді взагалі; відмовити тут означало б
    // зробити кнопку мертвою до першого перекладання. Тому без пам'яті
    // говорить перша ж рація на слоті.
    static TransmitterBase OZR_PickSpeaker(PlayerBase player, array<EntityAI> items)
    {
        bool cargo = false;
        OZR_Settings st = OZR_Settings.Get();
        if (st)
            cargo = st.PttFromCargo;

        TransmitterBase best     = null;
        int             bestRank = 0;
        int             latest   = 0;

        for (int i = 0; i < items.Count(); i++)
        {
            TransmitterBase t = TransmitterBase.Cast(items[i]);
            if (!t || !OZR_Profiles.For(t.GetType()))
                continue;

            int rank = t.OZR_SpeakRank(cargo);
            if (rank == 0)
                continue;

            // Руки б'ють усе й закінчують пошук: рація в долоні -- це вже
            // сказане вголос «говорю в цю».
            if (rank == 3)
                return t;

            int held = t.OZR_HeldAt();

            // Спершу за місцем, і лише в межах одного місця -- за свіжістю.
            // Надіта рація б'є ту, що в рюкзаку, навіть якщо рюкзачну
            // тримали пізніше: місце -- це намір, а час лише розводить
            // однакові.
            if (rank > bestRank || (rank == bestRank && held > latest))
            {
                best     = t;
                bestRank = rank;
                latest   = held;
            }
        }

        return best;
    }
}
