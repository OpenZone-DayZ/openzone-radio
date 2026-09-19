// Клієнтська точка входу мода рації.
//
// Три речі, і всі -- через договори сусідів, а не правкою їхніх файлів:
// почати опитувати клавіші PTT і клавіатури, слухати пакет синхронізації ядра
// (у ньому їде ефір, див. OZR_ClientSync) і відповіді служби «radio».
//
// На виділеному сервері MissionGameplay не створюється взагалі (там
// MissionServer), тож цей код туди просто не потрапляє.

modded class MissionGameplay
{
    override void OnInit()
    {
        super.OnInit();

        OZR_Ptt.Init();
        OZR_FreqInput.Init();
        OZR_Von.Watch();

        // Ефір -- із пакета синхронізації ядра, на кожен пакет (перший і
        // повторний), і одразу, якщо пакет випередив місію; відмови служби --
        // тостом. Той самий візерунок, що в КПК (OZ_PdaMissionGameplay).
        OZ_ClientState.SyncWatch().Insert(OZR_Sync);
        OZ_ClientState.ServiceWatch().Insert(OZR_SvcRes);
        if (OZ_ClientState.Ready())
            OZR_ClientSync.Apply();

        // Дзеркалення НЕ тут: воно залежить від налаштування, яке ще їде з
        // сервера. Кличеться з OZR_Audio, коли пакет приїхав.
    }

    void OZR_Sync(OZ_SyncPayload p)
    {
        OZR_ClientSync.Apply();
    }

    void OZR_SvcRes(string serviceId, string op, bool ok, string json, string error)
    {
        OZR_ClientSync.OnServiceResponse(serviceId, op, ok, json, error);
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        OZR_Ptt.Poll();
        OZR_FreqInput.Poll();

        // Питаємо щокадру, бо чекаємо пакет із сервера й не знаємо, коли він
        // прийде. Після першого разу це один порівняний біт.
        OZR_Von.Mirror();
    }

    override UIScriptedMenu CreateScriptedMenu(int id)
    {
        // super ПЕРШИЙ і вихід одразу, якщо він щось віддав: саме це тримає
        // сумісність з іншими модами, що чіпали той самий клас.
        UIScriptedMenu menu = super.CreateScriptedMenu(id);
        if (menu)
            return menu;

#ifndef NO_GUI
        if (id == OZR_Const.MENU_FREQ)
        {
            menu = new OZR_FreqMenu();

            // SetID -- НЕ формальність. Без нього меню лишається меню без
            // номера, і менеджер його не веде: FindMenu не знаходить,
            // CloseMenu не закриває, і -- найгірше -- керування не
            // перемикається, тож курсор не з'являється, а кліки летять повз
            // меню у гру (вмикаючи й вимикаючи ту саму рацію). Три різні
            // симптоми з одного пропущеного рядка.
            menu.SetID(id);
        }
#endif

        return menu;
    }

    // Меню програло фокус, гравець помер, гру згорнули -- край відпускання
    // клавіші в такі миті не приходить, і відкритий передавач лишився б
    // відкритим. Тому мовчання вмикаємо самі.
    override void OnMissionFinish()
    {
        // Дзеркало підписок з OnInit: інвокери ядра статичні й переживуть
        // місію, а місія -- ні.
        OZ_ClientState.SyncWatch().Remove(OZR_Sync);
        OZ_ClientState.ServiceWatch().Remove(OZR_SvcRes);

        OZR_Ptt.Drop();
        OZR_FreqInput.Drop();
        OZR_Von.Unwatch();
        super.OnMissionFinish();
    }
}
