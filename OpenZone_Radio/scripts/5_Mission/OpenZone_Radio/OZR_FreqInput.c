// Клавіша клавіатури частот.
//
// ВІДКРИВАЄ, і тільки. Закривають кнопки в самому меню -- «X» і «TUNE».
//
// Це не задум, а вимір. Задумувався перемикач, але поки меню відкрите, DayZ
// глушить інпути, і та сама клавіша більше не спрацьовує; Back на геймпаді теж
// не дійшов. Тому єдиний надійний шлях назовні -- віджет усередині меню, і
// саме тому кнопка «X» там є.
//
// Друге, що довелося з'ясувати: менеджер НЕ знаходить це меню за id.
// EnterScriptedMenu віддає екземпляр, ui-дерево показує його відкритим, а
// FindMenu(MENU_FREQ) одразу після цього повертає порожньо -- і CloseMenu(id)
// відповідно нічого не закриває. Тому меню закриває САМЕ СЕБЕ через Close(), а
// тут ми лише пам'ятаємо посилання.
//
// Сам UAInput кешувати НЕ можна: ваніль тримає обгортку й перечитує вказівник
// щокадру (radialmenu.c, actiontargets). Робимо так само.

class OZR_FreqInput
{
    // БЕЗ ref: UAIDWrapper -- нативний об'єкт із приватним деструктором, і
    // скрипт ним не володіє.
    private static UAIDWrapper s_Key;
    private static OZR_FreqMenu s_Menu;

    static void Init()
    {
        s_Key = OZR_Const.BindInput(OZR_Const.INPUT_FREQ);
    }

    static void Poll()
    {
        if (!s_Key)
            return;

        UAInput i = s_Key.InputP();
        if (!i)
            return;

        // Поки меню відкрите, клавіша ЗАКРИВАЄ його -- і Escape теж.
        //
        // Раніше опитування тут просто вимикалось, бо здавалось, що при
        // відкритому меню інпути однаково заглушені. Тепер це не так: ми
        // глушимо лише мишачі групи, клавіатура лишається живою, тож та сама
        // клавіша чесно доходить і може працювати перемикачем.
        if (s_Menu)
        {
            bool byKey  = i.LocalPress();
            bool byBack = GetUApi().GetInputByID(UAUIBack).LocalPress();

            if (byKey || byBack)
            {
                OZR_FreqMenu m = s_Menu;
                s_Menu = null;
                m.Close();
            }
            return;
        }

        if (!i.LocalPress())
            return;

        // Клавіша бачить сирі натискання незалежно від фокуса UI. Поле з
        // фокусом означає «клавіатура зайнята текстом» -- сусідній мод спіймав
        // це тим, що літера в назві мітки закривала йому меню посеред слова.
        if (OZR_Const.Typing())
            return;

        Open();
    }

    // Меню саме каже, що його вже немає: покладатись на FindMenu тут не можна.
    static void Forget()
    {
        s_Menu = null;
    }

    // Гравець помер або згорнув гру -- меню лишилось би висіти.
    static void Drop()
    {
        if (!s_Menu)
            return;

        OZR_FreqMenu m = s_Menu;
        s_Menu = null;
        m.Close();
    }

    private static void Open()
    {
        // Не лізти поверх ЧУЖОГО меню -- але перевіряти саме інвентар, а не
        // GetMenu(): у геймплеї той буває не-null і без жодного відкритого
        // вікна, і тоді клавіатура мовчки не відкривалась би ніколи.
        if (GetGame().GetUIManager().IsMenuOpen(MENU_INVENTORY))
            return;

        // Кажемо ВГОЛОС, чому ні. Натиснення клавіші -- це не кадр циклу, а
        // свідома дія, тож рядок на неї не спам, а відповідь.
        string why = OZR_FreqMenu.WhyNotOpen();
        if (why != "")
        {
            OZR_Log.Info("freq keypad: not opening - " + why);
            // Ефіру немає -- гравець бачить це на екрані (ТЗ-5 R-E3.1), а не
            // лише в лозі, який ретейл-клієнт і не пише.
            if (!OZR_ClientGrid.Ready())
                OZR_Say.Toast("STR_OZR_NOT_INIT");
            return;
        }

        UIScriptedMenu made = GetGame().GetUIManager().EnterScriptedMenu(OZR_Const.MENU_FREQ, null);
        if (!made)
        {
            OZR_Log.Error("freq keypad: EnterScriptedMenu returned nothing for id " + OZR_Const.MENU_FREQ.ToString());
            return;
        }

        // Реєстру id меню в рушії немає, і чужий мод міг зайняти наш номер --
        // 133 вже виявився зайнятий OZ_LinkMenu ядра, і відкривалось чуже,
        // мовчки. Тому перевіряємо, що екземпляр саме наш.
        s_Menu = OZR_FreqMenu.Cast(made);
        if (!s_Menu)
            OZR_Log.Error("freq keypad: menu id " + OZR_Const.MENU_FREQ.ToString() + " is taken by " + made.ClassName() + " - pick another id");
    }
}
