// Логер мода рації.
//
// Свій префікс, а не ядерний: у лозі сервера з тридцятьма модами треба одразу
// бачити, ЧИЙ це рядок, і вердикт MCP шукає саме префікс.
//
// WARNING пишеться повним словом навмисно: вердикт шукає \bWARNING\b, і
// скорочене WARN під це не підпадає -- бюджет попереджень тоді перестав би
// стежити за нашими ж перевірками.

class OZR_Log
{
    static void Info(string msg)
    {
        Print(OZR_Const.LOG_PREFIX + msg);
    }

    static void Warn(string msg)
    {
        Print(OZR_Const.LOG_PREFIX + "WARNING: " + msg);
    }

    static void Error(string msg)
    {
        Print(OZR_Const.LOG_PREFIX + "ERROR: " + msg);
    }

    // Тихий рівень.
    //
    // Прапорець ВЛАСНИЙ -- вмикач у OZ_Radio_Settings.json, -- хоч ядро з
    // 2026-09-20 стоїть завжди. Порядок CF-модулів не гарантований, і в
    // OnMissionStart рації налаштування ядра можуть бути ще не прочитані;
    // склейка @OpenZone_Radio_PDA переставляє цей прапорець за ядерним, коли
    // родина стоїть цілком. Клієнт бере ЖИВЕ значення сервера з пакета
    // синхронізації (OZR_ClientSync), тож обидва боки мовчать чи говорять
    // разом.
    private static bool s_Debug = false;

    static void SetDebug(bool on)
    {
        s_Debug = on;
    }

    static bool IsDebug()
    {
        return s_Debug;
    }

    static void Dbg(string msg)
    {
        if (!s_Debug)
            return;
        Print(OZR_Const.LOG_PREFIX + "dbg: " + msg);
    }
}

// Слово гравцеві на екран -- ванільний тост. Для того, що інакше жило б лише
// в лозі: відмова сервера на настройку (D103) і «ефіру немає» (ТЗ-5 R-E3).
class OZR_Say
{
    static void Toast(string key)
    {
        if (!GetGame() || GetGame().IsDedicatedServer() || key == "")
            return;
        NotificationSystem.AddNotificationExtended(4, "#STR_OZR_TOAST_TITLE", "#" + key, "");
    }
}
