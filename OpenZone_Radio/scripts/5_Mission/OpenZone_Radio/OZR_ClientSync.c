// Клієнтська половина ефіру: прочитати з пакета синхронізації ядра те, що
// сервер про ефір думає, і застосувати.
//
// До 2026-09-20 клієнт тягнув сітку сам (OZR_GridReq раз на дві секунди, до
// двох хвилин), а сервер відповідав чотирма видами пакетів. Тепер усе це --
// один додаток до OZ_Sync, який ядро шле, щойно клієнт сам привітався
// (OZ_Rpc.Hello), і шле знову на кожну зміну (адмінська правка профілів).
// Порядок застосування той самий, що був: спершу рівень діагностики, бо
// рядки нижче вже на нього зважають; потім гучності; потім сітка з профілями.

class OZR_ClientSync
{
    static void Apply()
    {
        string json = OZ_ClientState.Extra(OZR_Const.SYNC_ETHER, "");
        if (json == "")
        {
            // Пакет ядра є, а ефіру в ньому немає: сервер крутить ядро без
            // модуля рації. Для клієнта з цим pbo це неможливо, але мовчати
            // не можна: зовні воно виглядає рівно як «сітка не приїхала».
            OZR_Log.Warn("no ether in the server's sync packet - the radio module is not running on the server");
            return;
        }

        OZR_EtherWire w = new OZR_EtherWire();
        string err;
        if (!JsonFileLoader<OZR_EtherWire>.LoadData(json, w, err))
        {
            OZR_Log.Error("ether packet unreadable: " + err);
            return;
        }

        // НАЙПЕРШЕ: рядки нижче вже мусять на нього зважати -- той самий
        // порядок, що на сервері в OnMissionStart.
        OZR_Log.SetDebug(w.DebugLog);

        OZR_Audio.SetGains(w.Squelch, w.Mirror, w.Range, w.Cargo);

        string got = "audio: squelch x" + w.Squelch.ToString();
        got += " within " + OZR_Audio.SquelchRung().ToString() + " m";
        got += ", mirror ptt onto the voice key = " + w.Mirror.ToString();
        got += ", ptt from cargo = " + w.Cargo.ToString();
        // Рівень діагностики -- у ТОМУ САМОМУ рядку: без нього «чому в лозі
        // немає squelch» не має відповіді, яку видно.
        got += ", debug log = " + w.DebugLog.ToString();
        OZR_Log.Info(got);

        // Сітка скидає перелік профілів, і профілі йдуть за нею -- як і
        // раніше, лише додатками пакета замість низки пакетів: по одному на
        // профіль, бо одне строкове значення JSON рушій ріже на 1023 байтах
        // (див. OZR_Wire).
        OZR_ClientGrid.SetGrid(w.BaseMHz, w.StepMHz, w.Count);

        int n = 0;
        int total = OZ_ClientState.Extra(OZR_Const.SYNC_RADIOS, "0").ToInt();
        for (int i = 0; i < total; i++)
        {
            string one = OZ_ClientState.Extra(OZR_Const.SYNC_RADIO + i.ToString(), "");
            if (one == "")
                continue;

            // Корінь створює скрипт (new), поля скалярні -- копіювати нема чого;
            // AddProfile переписує їх у власний об'єкт одразу.
            OZR_RadioProfile p = new OZR_RadioProfile();
            string perr;
            if (!JsonFileLoader<OZR_RadioProfile>.LoadData(one, p, perr))
            {
                OZR_Log.Error("radio profile " + i.ToString() + " unreadable: " + perr);
                continue;
            }

            OZR_ClientGrid.AddProfile(p.ClassName, p.MinMHz, p.MaxMHz, p.StepMHz);
            n++;
        }

        if (OZR_ClientGrid.Ready())
        {
            string line = "ether received: " + w.Count.ToString() + " divisions from ";
            line += OZR_Fmt.MHz(w.BaseMHz) + " MHz by " + OZR_Fmt.Step(w.StepMHz);
            line += ", " + n.ToString() + " profile(s)";
            OZR_Log.Info(line);
        }
        else
        {
            // Не збій зв'язку, а відповідь: сервер каже, що ефіру немає.
            // Сказати це прямо треба тому, що зовні воно виглядає точно так
            // само, як пакет, який не доїхав.
            OZR_Log.Warn("no ether: the server reports no even frequency grid - radios stay vanilla and the keypad will not open");
        }
    }

    // Відповідь служби «radio». Сьогодні сервер відповідає лише на одне --
    // відмову настройки, ключем таблиці рядків: мовчазна відмова виглядала як
    // зламана клавіатура (D103). Удача відповіді не має: її видно на самій
    // рації, коли приїде синхрозмінна.
    static void OnServiceResponse(string serviceId, string op, bool ok, string json, string error)
    {
        if (serviceId != OZR_Const.SERVICE || ok)
            return;

        OZR_Log.Info(op + " refused by the server: " + error);
        OZR_Say.Toast(error);
    }
}
