// Служба «radio» в реєстрі ядра: настройка з клавіатури частот і край гашетки.
//
// До 2026-09-20 це були два власні CF-RPC рації (OZR_TuneReq, OZR_PttRadio) --
// другий транспорт поруч із ядерним, яким уже ходили обидві склейки. Тіла
// обробників ті самі; змінився лише конверт: ядро приносить особу відправника
// й склеєне тіло, а все, що про рацію в руках, як і раніше, перевіряється тут.
// Ворота ядра (прилад, права) до цієї служби не стосуються -- і саме тому вона
// служба, а не сторінка.

class OZR_Service : OZ_ServiceHandler
{
    override string Handle(string op, string json, PlayerIdentity sender, out bool ok, out string error)
    {
        ok = false;
        error = "STR_OZ_ERR_UNKNOWN_OP";

        if (!sender)
            return "";

        if (op == OZR_Const.OP_TUNE)
        {
            // Міряється з кінця в кінець для дебаг-режиму лагів; тіло незмінне.
            int mt = OZR_Meter.Begin();
            string refused = Tune(json, sender);
            OZR_Meter.End(OZR_Meter.TUNE, mt);

            // Лише відмови їдуть назад, ключем таблиці рядків (D103): удачу
            // видно на самій рації, коли приїде синхрозмінна, а мовчазна
            // відмова виглядала як зламана клавіатура.
            if (refused == "")
                error = OZ_Const.NO_REPLY;
            else
                error = refused;
            return "";
        }

        if (op == OZR_Const.OP_PTT)
        {
            int pt = OZR_Meter.Begin();
            Ptt(json, sender);
            OZR_Meter.End(OZR_Meter.PTT, pt);

            // Край -- подія, а не питання; відповідь на нього -- це другий
            // пакет заради рядка, який ніхто не читає.
            error = OZ_Const.NO_REPLY;
            return "";
        }

        return "";
    }

    // Пряма настройка на ділення. Клієнт присилає ЧИСЛО, і воно не має жодної
    // ваги, поки сервер не перевірив його проти профілю тієї рації, яка
    // справді в руках у цього гравця. Інакше клавіатура частот була б
    // способом сісти на чужу смугу, минаючи і профіль, і саму рацію.
    //
    // Повертає КЛЮЧ відмови, або порожньо, коли рацію настроєно. Нечитне тіло
    // -- порожньо теж: так само мовчав ctx.Read у старому обробнику, і
    // відповідати підробленому пакетові нема чим.
    private string Tune(string json, PlayerIdentity sender)
    {
        OZR_TuneWire w = new OZR_TuneWire();
        string err;
        if (!JsonFileLoader<OZR_TuneWire>.LoadData(json, w, err))
        {
            OZR_Log.Dbg("tune refused: unreadable body (" + err + ")");
            return "";
        }

        PlayerBase player = OZR_Module.OZR_PlayerOf(sender);
        if (!player || !player.GetHumanInventory())
        {
            OZR_Log.Dbg("tune refused: no player for this identity");
            return "";
        }

        TransmitterBase radio = TransmitterBase.Cast(player.GetHumanInventory().GetEntityInHands());
        if (!radio)
        {
            OZR_Log.Dbg("tune refused: nothing that transmits in hands");
            return "STR_OZR_ERR_NO_RADIO_HANDS";
        }

        if (!radio.OZR_IsPowered())
        {
            OZR_Log.Dbg("tune refused: the radio is switched off");
            return "STR_OZR_ERR_SWITCHED_OFF";
        }

        OZR_RadioProfile prof = OZR_Profiles.For(radio.GetType());
        if (!prof || !OZR_Grid.Ready())
        {
            // Info, не Dbg (ТЗ-5 R-E3.2): без цього рядка адмін не відрізнить
            // «сітка не виведена» від «клієнт не отримав».
            OZR_Log.Info("tune refused for " + sender.GetName() + ": no profile for " + radio.GetType() + " or the grid is not even");
            return "STR_OZR_NOT_INIT";
        }

        int want = w.Index;
        int lo;
        int hi;
        int stride;
        if (!OZR_Grid.Window(prof, lo, hi, stride))
        {
            OZR_Log.Dbg("tune refused: " + radio.GetType() + " does not overlap the running ether at all - restart the server");
            return "STR_OZR_ERR_NO_OVERLAP";
        }

        if (want < lo || want > hi)
        {
            OZR_Log.Dbg("tune refused: index " + want.ToString() + " is outside " + lo.ToString() + ".." + hi.ToString());
            return "STR_OZR_KEYPAD_OUT";
        }

        // Ділення мусить лежати на ґратці САМОГО профілю, а не просто в його
        // межах: інакше рація стане між своїми каналами й не зустріне нікого.
        if (((want - lo) % stride) != 0)
        {
            OZR_Log.Dbg("tune refused: index " + want.ToString() + " is between this set's own channels");
            return "STR_OZR_ERR_OFF_STEP_SET";
        }

        // Через OZR_TuneTo, а не SetFrequencyByIndex: він же й розкаже про
        // нову частоту клієнтові. Прямий виклик лишив би її невидимою.
        radio.OZR_TuneTo(want);

        OZR_Log.Dbg("tuned " + radio.GetType() + " to index " + want.ToString() + " = " + OZR_Grid.MHzAt(want).ToString() + " MHz");
        return "";
    }

    // Край гашетки. Правило «яку рацію відкрити» й доказ до нього -- над
    // OZR_Module.OZR_SetAll; тут лише конверт і межа по зміні.
    private void Ptt(string json, PlayerIdentity sender)
    {
        OZR_PttWire w = new OZR_PttWire();
        string err;
        if (!JsonFileLoader<OZR_PttWire>.LoadData(json, w, err))
        {
            OZR_Log.Dbg("ptt: unreadable body (" + err + ")");
            return;
        }

        // Обхід усього інвентаря на кожен край -- і саме тому межа. Але межа
        // ПО ЗМІНІ, не по часу: півсекундний проміжок з'їдав край відпускання
        // короткого клацання разом із його сплеском (див. OZR_Throttle).
        // Дублікат відкинути можна -- край не можна ніколи.
        if (!OZR_Throttle.Changed(sender, w.On, w.Locked))
            return;

        PlayerBase player = OZR_Module.OZR_PlayerOf(sender);
        if (!player || !player.GetInventory())
            return;

        int touched = OZR_Module.OZR_SetAll(player, w.On, w.Locked);

        if (OZR_Log.IsDebug())
        {
            string said = "ptt: " + sender.GetName();
            if (w.On)
                said += " opens ";
            else
                said += " shuts ";
            said += touched.ToString() + " radio(s)";
            if (w.Locked)
                said += " (latched)";
            OZR_Log.Dbg(said);
        }
    }
}
