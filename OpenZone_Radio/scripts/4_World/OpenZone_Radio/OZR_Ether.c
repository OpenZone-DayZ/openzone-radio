// Серверна половина ефіру: покласти виведену сітку на диск і сказати, чи вона
// вже діє.
//
// Арифметика живе в 3_Game (OZR_Ether), бо її рахує і вкладка на клієнті. Тут
// лишається те, що має сенс лише на сервері: файл і порівняння з ВИМІРЯНОЮ
// сіткою рушія.
//
// Файл читає нативний патч при старті ПРОЦЕСУ, тому нова сітка вступає в дію
// тільки з наступним запуском сервера. Це сказано вголос -- і в лозі, і у
// вкладці: мовчазна відкладена дія гірша за відсутню.

// Межа на гашетці -- про ЗМІНУ, а не про час.
//
// Півсекундний проміжок тут стояв (906c696) і з'їдав клацання -- власник
// почув це 2026-09-09, а до 2475baf, де межі не було, вони грали надійно.
// Довід був: «свій клієнт шле краї, а не стан щокадру, тож півсекунди в
// нього не забирають нічого». Неправда, і неправда рівно про краї:
// натиснути й відпустити швидше за півсекунди -- це звичайне клацання
// гашетки, і ДРУГИЙ його край проміжок відкидав мовчки. Наслідків два, і
// обидва гірші за флуд: сплеск закриття не грав, а ефір лишався ВІДКРИТИМ
// до наступного краю -- мікрофон, якого ніхто не вимикав. Край не
// повторюється ніколи: його або обробили, або втратили назавжди.
//
// Проміжок за часом годився лише ідемпотентному запитові сітки, і разом із
// ним і пішов (2026-09-20): сітку клієнт більше не тягне, вона приїздить
// пакетом ядра, і питати про неї нема кого.
class OZR_Throttle
{
    // ПАКЕТ, ЯКИЙ ПРОСИТЬ ТЕ, ЩО ВЖЕ СТОЇТЬ.
    //
    // Це все, що на гашетці можна відкинути безпечно: край за визначенням
    // МІНЯЄ стан, тож жоден край сюди не потрапить. Свій клієнт дублікатів
    // не шле взагалі (OZR_Ptt.Apply звіряє з посланим), а змінений може
    // слати їх скільки завгодно -- і кожен коштував би обходу всього
    // інвентаря гравця.
    //
    // Стан цілим числом, бо мапа тут одна: 0 -- закрито, 1 -- відкрито
    // клавішею, 2 -- відкрито замком. Замок від утримання відрізняти
    // обов'язково: кинуту рацію сервер лишає говорити лише із замком.
    private static ref map<string, int> s_Ptt;

    static bool Changed(PlayerIdentity who, bool on, bool locked)
    {
        if (!who)
            return false;

        if (!s_Ptt)
            s_Ptt = new map<string, int>();

        // ГІЛКОЮ, А НЕ ЛАНЦЮЖКОМ -- та сама пастка, що в m_OZR_Latched:
        // складене «&&» у цьому рушії вміє мовчки дати не ту відповідь.
        int state = 0;
        if (on)
        {
            state = 1;
            if (locked)
                state = 2;
        }

        string key = who.GetPlainId();

        int was;
        if (s_Ptt.Find(key, was) && was == state)
            return false;

        s_Ptt.Set(key, state);
        return true;
    }

    // Гравець пішов -- його рядок теж. Мапа без цього росла б увесь запуск.
    // За UID, а не за особою: на дисконекті особи вже може не бути, і саме
    // тому CF несе uid окремим полем події.
    //
    // ЧЕРЕЗ Contains, а не голим Remove: рідний map оголошує Remove без слова
    // про відсутній ключ, і сама ваніль про всяк випадок питає перед ним
    // (enscript.c, map.Replace). Дисконект -- поганий шлях, щоб про це
    // дізнатись.
    static void Forget(string uid)
    {
        if (uid == "")
            return;

        // Наступний власник цього UID -- нове тіло з закритим ефіром, і
        // пам'ять про чужий замок відкинула б його перше ж натискання.
        if (s_Ptt && s_Ptt.Contains(uid))
            s_Ptt.Remove(uid);
    }
}

class OZR_EtherServer
{
    private static ref OZR_EtherPlan s_Plan;

    // ЩО ЦЕЙ СЕРВЕР ДУМАЄ ПРО ЕФІР -- додатком до пакета синхронізації ядра.
    //
    // Кличе інвокер OZ_SyncExtras на кожну відправку пакета: на вході
    // гравця (ядро шле його, щойно клієнт сам привітався) і на Broadcast
    // нижче. Раніше це було тілом обробника RPC, потім -- чотирма видами
    // пакетів ЧИСЛАМИ, бо рядок-значення рушій ріже на 1023 байтах і один
    // JSON з усіма профілями переріс межу на одинадцятому. Пакет ядра цієї
    // межі не має: OZ_Sync ріжеться на частини (OZ_Rpc.SendSync), тож
    // профілі знову їдуть одним об'єктом.
    static void Fill(OZ_SyncPayload p)
    {
        OZR_EtherWire w = new OZR_EtherWire();

        // Сітку віддаємо, ЛИШЕ якщо вона сітка.
        //
        // Без цієї перевірки сервер описував клієнтові ванільну вісімку як
        // рівну ґратку: база 87.800, "крок" (102.5 - 87.8) / 7 = 2.1000,
        // вісім ділень. Клієнт перевірити рівномірність не може -- йому їдуть
        // три числа, а не таблиця, -- тож він чесно рахував base + i*step для
        // індексів СПРАВЖНЬОЇ сітки. Рація, збережена на індексі 962 (у сітці
        // на 1281 ділення це 148.025 МГц), підписувалась як 2108.000 МГц, а
        // ванільна ручка крокувала її по 2.1 МГц за натиск.
        //
        // Спостережено на живому сервері 2026-09-01: після рестарту не
        // піднявся нативний патч, і рушій роздав ванільну вісімку.
        //
        // Нулі означають "ефіру немає", і кожен споживач на клієнті вже вміє
        // це читати: підпис падає на ванільний, клавіатура не відкривається.
        if (OZR_Grid.Ready())
        {
            w.BaseMHz = OZR_Grid.Base();
            w.StepMHz = OZR_Grid.StepMHz();
            w.Count   = OZR_Grid.Count();
        }
        else
        {
            OZR_Log.Warn("ether asked for, but the engine's table is not an even grid - telling the client there is no ether instead of describing the vanilla eight as one");
        }

        // Гучності їдуть тим самим об'єктом, бо питання те саме: «що цей
        // сервер про ефір думає». Сітка може бути відсутньою, а гучності
        // діють однаково завжди -- тому вони окремі поля, а не частина сітки.
        //
        // РІВЕНЬ ДІАГНОСТИКИ ЇДЕ РАЗОМ, і без нього клієнтського лога в цього
        // мода не було ЗОВСІМ: OZR_Log.SetDebug на клієнті не кликав ніхто, і
        // кожен OZR_Log.Dbg там був мертвим рядком -- а саме на цьому боці
        // живуть сплески squelch. Береться ЖИВИЙ прапорець логера, а не
        // st.DebugLog: склейка @OpenZone_Radio_PDA переставляє наш рівень за
        // ядерним (OZRP_Module.OnMissionStart), і саме за переставленим
        // сервер пише. Клієнт мусить мовчати чи говорити разом із ним.
        OZR_Settings st = OZR_Settings.Get();
        if (st)
        {
            w.Squelch = st.SquelchGain;
            w.Mirror  = st.MirrorPtt;
            w.Range   = st.SquelchRange;
            w.Cargo   = st.PttFromCargo;
        }
        w.DebugLog = OZR_Log.IsDebug();

        string json;
        string err;
        // prettyPrint=false: у провід не треба ані відступів, ані переносів.
        if (!JsonFileLoader<OZR_EtherWire>.MakeData(w, json, err, false))
        {
            OZR_Log.Error("cannot serialise the ether for the sync packet: " + err);
            return;
        }
        OZ_SyncExtras.Put(p, OZR_Const.SYNC_ETHER, json);

        // ПРОФІЛІ -- ПО ОДНОМУ ДОДАТКУ, а не масивом у тому самому об'єкті:
        // одне строкове значення JSON рушій ріже на 1023 байтах, і ефір з
        // усіма профілями в цю межу не вміщався (див. OZR_Wire). Профіль --
        // близько дев'яноста байтів, тож жоден додаток від їх числа не росте.
        int sent = 0;
        OZR_Profiles cfg = OZR_Profiles.Get();
        if (cfg && cfg.Radios)
        {
            for (int i = 0; i < cfg.Radios.Count(); i++)
            {
                OZR_RadioProfile prof = cfg.Radios[i];
                if (!prof)
                    continue;

                string one;
                string perr;
                if (!JsonFileLoader<OZR_RadioProfile>.MakeData(prof, one, perr, false))
                {
                    OZR_Log.Error("cannot serialise radio profile " + prof.Named() + ": " + perr);
                    continue;
                }

                OZ_SyncExtras.Put(p, OZR_Const.SYNC_RADIO + sent.ToString(), one);
                sent++;
            }
        }
        OZ_SyncExtras.Put(p, OZR_Const.SYNC_RADIOS, sent.ToString());
    }

    // ...і всім, хто вже в грі.
    //
    // Потрібно рівно після адмінської правки профілів: пакет ядра клієнт
    // отримує на вході й далі не питає, тож без цієї розсилки кейпад і PTT
    // в онлайну лишались би зі старими смугами до перезаходу. Ядро шле
    // повний пакет кожному, і Fill вище кладе в нього свіжий ефір.
    static void Broadcast()
    {
        OZ_SyncSender.SendAll("radio profiles edited");
    }

    // Порахувати й записати. Кличеться і при старті, і після кожної правки
    // профілів: файл, який відстав від профілів, -- це рівно та неузгодженість,
    // заради усунення якої все це й зроблено.
    static void Publish(OZR_Profiles cfg)
    {
        // ПРОФІЛІ, ЯКИХ АДМІН НЕ ПИСАВ, НЕ ВИВОДЯТЬ ЕФІРУ.
        //
        // OZ_Radio_Profiles.json міг не розібратись -- кома не там, редактор
        // обірвав запис, -- і тоді ми стоїмо на вбудованій драбині, а файл
        // лишається на диску недоторканим. Вивести сітку з ЦИХ чисел і
        // покласти її поверх робочого OZ_Radio_Frequencies.json означало б
        // після одного зіпсованого старту втратити всі власні смуги сервера
        // мовчки -- і виявилось би це аж наступним рестартом.
        if (!OZR_Profiles.Writable())
        {
            OZR_Log.Warn("ether not derived: the radio profiles on disk did not parse, so we are on built-in defaults - the frequency file is left as it was, fix OZ_Radio_Profiles.json and restart");
            return;
        }

        array<ref OZR_RadioProfile> radios;
        if (cfg)
            radios = cfg.Radios;

        OZR_EtherPlan plan = OZR_Ether.Derive(radios);
        s_Plan = plan;

        if (!plan.Ok)
        {
            // Файл НЕ чіпаємо. Профілі можуть бути тимчасово безглуздими --
            // адмін посеред правки, -- і затирати цим робочу сітку не можна.
            OZR_Log.Warn("ether not derived: " + plan.Why + " - the frequency file is left as it was");
            return;
        }

        // ПИШЕМО ТЕКСТ САМІ, а не через JsonFileLoader. Він серіалізує те, що
        // лишилось від числа у float32: 0.0125 виходить як
        // 0.012500000186264515, і файл, який має бути джерелом правди про крок,
        // виглядає як помилка. Виведений крок за побудовою кратний 0.0001 МГц
        // (див. UNITS_PER_MHZ), тож чотирьох знаків достатньо рівно завжди.
        string body = "{ \"base_mhz\": " + OZR_Fmt.Fixed(plan.BaseMHz, 4);
        body += ", \"step_mhz\": " + OZR_Fmt.Fixed(plan.StepMHz, 4);
        body += ", \"count\": " + plan.Count.ToString() + " }";

        FileHandle fh = OpenFile(OZR_Const.FREQUENCIES, FileMode.WRITE);
        if (fh == 0)
        {
            OZR_Log.Error("cannot open " + OZR_Const.FREQUENCIES + " for writing");
            return;
        }
        FPrintln(fh, body);
        CloseFile(fh);

        string said = "ether derived from profiles: " + OZR_Ether.Describe(plan);
        if (Matches())
            said += " (in effect)";
        else
            said += " - RESTART THE SERVER to apply; the running ether is still " + Running();

        OZR_Log.Info(said);
    }

    // Чи те, що ми вивели, збігається з тим, що рушій справді роздає зараз.
    // Порівняння і форматування живуть у 3_Game (OZR_Ether): їх робить і
    // вкладка на клієнті, а два підрахунки одного числа розійшлись би тихо.
    static bool Matches()
    {
        if (!OZR_Grid.Ready())
            return false;

        return OZR_Ether.Same(s_Plan, OZR_Grid.Base(), OZR_Grid.StepMHz(), OZR_Grid.Count());
    }

    static string Running()
    {
        if (!OZR_Grid.Ready())
            return "not an even grid";

        return OZR_Ether.DescribeGrid(OZR_Grid.Base(), OZR_Grid.StepMHz(), OZR_Grid.Count());
    }
}
