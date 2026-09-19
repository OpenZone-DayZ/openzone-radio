// Цифрова клавіатура частот -- і чому вона не заважає бігти.
//
// Меню в DayZ забирає ввід, і гравець стає стовпом. Але ваніль уміє інакше:
// колесо жестів відкрите, а персонаж біжить. Різниця в одному -- воно
// перевизначає UseMouse() і НЕ ЧІПАЄ клавіатуру. Миша йде меню, клавіатура
// лишається грі, тому WASD живі.
//
// Звідси й форма клавіатури: цифри КЛІКАЮТЬСЯ. Забери меню клавіатуру заради
// набору з цифрового ряду -- і бігти стане нічим. Це не компроміс, а єдина
// форма, в якій обидві вимоги власника уживаються разом.

class OZR_FreqMenu extends UIScriptedMenu
{
    private TextWidget m_Title;
    private TextWidget m_Freq;
    private TextWidget m_Band;
    private TextWidget m_Hint;
    private Widget     m_Card;

    // НАБРАНЕ -- ЦЕ НАМІР, і рації він не стосується, поки не натиснуто TUNE.
    //
    // Рядок, а не число: «145.1» -- це стан набору. Числом воно стає лише в
    // мить підтвердження. Порожній рядок означає «нічого не набрано», і тоді
    // на табло світиться те, на чому рація стоїть насправді.
    private string m_Typed = "";

    // Набране поставили СТРІЛКИ, а не пальці: перша ж цифра тоді починає набір
    // з чистого, а не дописується в хвіст готовому числу («145.500» + «7»).
    private bool   m_Dialled = false;
    private float  m_Since = 0;

    // Підказка тримається В ПОЛІ, а не пишеться просто у віджет. Інакше
    // наступний же Paint затирає її звичайним текстом -- саме так відмова
    // «частота поза смугою» жодного разу не потрапила гравцеві на очі.
    private string m_HintKey = "#STR_OZR_KEYPAD_HINT";

    // Перетягування: зсув між курсором і кутом картки в мить захоплення.
    private bool   m_Dragging = false;
    private float  m_GrabX = 0;
    private float  m_GrabY = 0;

    private TransmitterBase m_Radio;
    private ref OZR_RadioProfile m_Profile;

    override Widget Init()
    {
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("OpenZone_Radio/gui/layouts/ozr_freq.layout");

        // ВИХОДИМО, а не тільки скаржимось. Тут ішли чотири FindAnyWidget
        // одразу після рядка «розкладка не дала жодного віджета» -- тобто
        // розіменування null на клієнті при будь-якій біді з ozr_freq.layout
        // (зниклий файл, перейменований, pbo без gui/). Викликач
        // (OZR_FreqInput.Open) порожнє вже вміє читати.
        if (!layoutRoot)
        {
            OZR_Log.Error("freq keypad: the layout produced no widgets");
            return null;
        }

        OZR_Log.Dbg("freq keypad: layout built");

        m_Card  = layoutRoot;
        m_Title = TextWidget.Cast(layoutRoot.FindAnyWidget("TitleText"));
        m_Freq  = TextWidget.Cast(layoutRoot.FindAnyWidget("FreqText"));
        m_Band  = TextWidget.Cast(layoutRoot.FindAnyWidget("BandText"));
        m_Hint  = TextWidget.Cast(layoutRoot.FindAnyWidget("HintText"));

        return layoutRoot;
    }

    // Миша -- нам. Клавіатура НЕ згадується навмисне: саме її мовчання й
    // лишає гравцеві біг.
    override bool UseMouse()
    {
        return true;
    }

    override void OnShow()
    {
        super.OnShow();

        OZR_Log.Dbg("freq keypad: shown");

        // LockControls -- це і є «забрати мишу». База вміє це сама (див.
        // UIScriptedMenu.LockControls: ChangeGameFocus(1, INPUT_DEVICE_MOUSE)
        // плюс ShowUICursor), але САМА НЕ КЛИЧЕ -- меню мусить покликати.
        // Без цього курсор не з'являється й клікати нема чим; спіймано тим,
        // що автотест бив по обробнику напряму й миші не торкався зовсім.
        //
        // Клавіатуру не чіпаємо: UseKeyboard() лишається false, тож
        // ChangeGameFocus для неї не викликається, і біг живий.
        LockControls();
        SetFocus(layoutRoot);

        // Без цього клік доходить і до меню, І ДО ГРИ: кнопка натискається, а
        // разом із нею спрацьовує дія в світі -- та сама рація вмикається й
        // вимикається. LockControls дає курсор, але не забирає у гри саму дію.
        //
        // Глушимо РІВНО мишачі групи. "movement" навмисне НЕ чіпаємо -- саме
        // на цьому тримається вимога бігати з відкритою клавіатурою, і саме
        // цим ми відрізняємось від КПК, який глушить усе гуртом ("menu").
        GetGame().GetMission().AddActiveInputExcludes(Excludes());

        Place();
        Grab();
        Paint();
    }

    // Рівно мишачі групи. "movement" тут немає навмисне -- див. OnShow.
    private static array<string> Excludes()
    {
        array<string> a = new array<string>();
        a.Insert("aiming");
        a.Insert("actions");
        a.Insert("optics");
        a.Insert("hotkey");
        return a;
    }

    override void OnHide()
    {
        super.OnHide();

        m_Dragging = false;
        // БЕЗ true. Другий аргумент форсує скидання вводу, і затиснута W
        // губиться -- персонаж зупиняється рівно в мить закриття вікна.
        // Ваніль і КПК ставлять true, бо їм байдуже: вони й так знерухомили
        // гравця. Нам не байдуже, у цьому вся суть цього меню.
        GetGame().GetMission().RemoveActiveInputExcludes(Excludes(), false);
        UnlockControls();

        // Кажемо опитувачу самі: FindMenu(MENU_FREQ) це меню не бачить, тож
        // питати менеджера, чи ми ще відкриті, марно.
        OZR_FreqInput.Forget();
    }

    // Куди поставити картку: туди, куди її перетягнули востаннє, а якщо ще
    // нікуди -- по центру.
    // Позиція картки -- ОДИН РАЗ ЗА СЕСІЮ з диска, далі з пам'яті.
    //
    // Файл читався на кожне відкриття вікна й переписувався на кожне
    // відпускання миші, хоч у ньому пара float, яку ми ж і поклали.
    // Синхронний файловий ввід-вивід у кадрі відкриття меню -- не те, за що
    // варто платити двічі.
    private static ref OZR_KeypadPos s_Pos;
    private static bool s_PosRead = false;

    private void Place()
    {
        if (!m_Card)
            return;

        if (!s_PosRead)
        {
            s_PosRead = true;

            // LoadFile віддає ще й текст помилки -- третій параметр
            // обов'язковий. Відсутній файл тут не помилка, а перший запуск,
            // тож мовчимо. Копіюємо в СВІЙ об'єкт: те, що повернув
            // завантажувач, створив рушій, і жити довше за цей виклик воно не
            // мусить (доказ -- над OZR_Profiles.Copy).
            OZR_KeypadPos saved;
            string err;
            if (JsonFileLoader<OZR_KeypadPos>.LoadFile(OZR_Const.KEYPAD_POS, saved, err) && saved)
            {
                s_Pos   = new OZR_KeypadPos();
                s_Pos.X = saved.X;
                s_Pos.Y = saved.Y;
            }
        }

        if (s_Pos)
        {
            m_Card.SetPos(s_Pos.X, s_Pos.Y);
            Clamp();
            return;
        }

        Centre();
    }

    private void SavePos()
    {
        if (!m_Card)
            return;

        float x, y;
        m_Card.GetPos(x, y);

        // Не зрушили -- не пишемо. Відпускання миші без перетягування трапляється
        // частіше за саме перетягування.
        if (s_Pos && s_Pos.X == x && s_Pos.Y == y)
            return;

        // Каталог профілю на КЛІЄНТІ теж ніхто не створює: ядро тут може бути
        // відсутнє так само, як на сервері, а без каталогу SaveFile мовчки не
        // пише -- вікно щоразу поверталось би на середину екрана.
        OZR_Const.EnsureProfileDir();

        OZR_KeypadPos p = new OZR_KeypadPos();
        p.X = x;
        p.Y = y;

        string err;
        if (!JsonFileLoader<OZR_KeypadPos>.SaveFile(OZR_Const.KEYPAD_POS, p, err))
        {
            OZR_Log.Warn("keypad position not saved: " + err);
            return;
        }

        s_Pos = p;
    }

    // Не даємо картці піти за край: вікно, за яке більше не вхопитись, --
    // це вікно, яке більше не закрити.
    private void Clamp()
    {
        float cw, ch, x, y;
        m_Card.GetScreenSize(cw, ch);
        m_Card.GetPos(x, y);

        int sw, sh;
        GetScreenSize(sw, sh);

        m_Card.SetPos(Math.Clamp(x, 0, sw - cw), Math.Clamp(y, 0, sh - ch));
    }

    // Картку центрує скрипт, а не розкладка: вирівнювання по екрану залежить
    // від роздільної здатності, і скрипт її знає, а розкладка ні.
    private void Centre()
    {
        if (!m_Card)
            return;

        // Два різні GetScreenSize, і плутати їх не варто: у Widget це ЙОГО
        // власний розмір у пікселях (enwidgets.c), а голий -- розмір екрана
        // (глобальний proto в 1_core/ensystem.c). Тут потрібні обидва.
        float cw, ch;
        m_Card.GetScreenSize(cw, ch);

        int sw, sh;
        GetScreenSize(sw, sh);

        m_Card.SetPos((sw - cw) * 0.5, (sh - ch) * 0.5);
    }

    // Рація в руках -- і тільки вона. Клавіатура без рації нічого не значить.
    private void Grab()
    {
        m_Radio   = null;
        m_Profile = null;

        PlayerBase p = PlayerBase.Cast(GetGame().GetPlayer());
        if (!p || !p.GetHumanInventory())
            return;

        m_Radio = TransmitterBase.Cast(p.GetHumanInventory().GetEntityInHands());
        if (!m_Radio)
            return;

        m_Profile = OZR_ClientGrid.For(m_Radio.GetType());
    }

    // Чому не відкриється -- словами, і порожній рядок означає «відкриється».
    //
    // Мовчазна відмова тут коштувала дорожче за все інше в цьому файлі:
    // клавіша, яка нічого не робить, читається як зламаний мод, і відрізнити
    // «немає ефіру» від «рація вимкнена» чи «профіль не приїхав» не міг ніхто
    // -- ні гравець, ні той, кому він про це напише. П'ять різних причин
    // виглядали однаково.
    static string WhyNotOpen()
    {
        if (!OZR_ClientGrid.Ready())
            return "no ether: the server has not sent a usable frequency grid";

        PlayerBase p = PlayerBase.Cast(GetGame().GetPlayer());
        if (!p || !p.GetHumanInventory())
            return "no player inventory";

        TransmitterBase t = TransmitterBase.Cast(p.GetHumanInventory().GetEntityInHands());
        if (!t)
            return "nothing in hands that can transmit";

        // Вимкнена рація нічого не вміє, і клавіатура над нею -- обіцянка,
        // якої ніхто не виконає.
        if (!t.OZR_IsPowered())
            return t.GetType() + " is not powered";

        if (!OZR_ClientGrid.For(t.GetType()))
            return "no profile for " + t.GetType() + " (" + OZR_ClientGrid.ProfileCount().ToString() + " profile(s) received)";

        return "";
    }

    private void Paint()
    {
        if (m_Title)
        {
            string title = "";
            if (m_Radio)
                title = m_Radio.GetDisplayName();
            m_Title.SetText(title);
        }

        // ТАБЛО ОДНЕ, І ЗНАЧЕНЬ У НЬОГО ДВА. Поки щось набрано або накручено --
        // це НАМІР, і він чекає TUNE. Порожній набір означає «наміру немає», і
        // тоді світиться те, на чому рація стоїть насправді.
        //
        // Другого рядка під налаштовану частоту тут немає, і це видно: поки
        // намір на табло, де стоїть рація, не показує ніщо. Розкладка ведеться
        // руками, тож окреме поле -- окреме рішення власника, а не побічний
        // наслідок цієї правки.
        if (m_Freq)
        {
            string shown = m_Typed;
            if (shown == "" && m_Radio)
                shown = OZR_Fmt.MHz(OZR_ClientGrid.MHzAt(m_Radio.OZR_ShownIndex()));
            m_Freq.SetText(shown);
        }

        if (m_Band && m_Profile)
        {
            string band = OZR_Fmt.MHz(m_Profile.MinMHz) + " - " + OZR_Fmt.MHz(m_Profile.MaxMHz);
            band += "   step " + OZR_Fmt.MHz(m_Profile.StepMHz);
            m_Band.SetText(band);
        }

        if (m_Hint)
            m_Hint.SetText(m_HintKey);
    }

    // Перетягування за верхню смугу. Тягнемо КАРТКУ, а не окремі віджети:
    // вони всі її діти, тож рухаються разом.
    override bool OnMouseButtonDown(Widget w, int x, int y, int button)
    {
        if (w && button == 0 && w.GetName() == "DragBar")
        {
            float cx, cy;
            m_Card.GetPos(cx, cy);
            m_GrabX    = x - cx;
            m_GrabY    = y - cy;
            m_Dragging = true;
            return true;
        }
        return super.OnMouseButtonDown(w, x, y, button);
    }

    override bool OnMouseButtonUp(Widget w, int x, int y, int button)
    {
        if (m_Dragging)
        {
            m_Dragging = false;
            Clamp();
            SavePos();
            return true;
        }
        return super.OnMouseButtonUp(w, x, y, button);
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w)
            return false;

        string name = w.GetName();

        // Закриття мусить жити ВСЕРЕДИНІ меню. Клавіша-перемикач цього не
        // може: поки меню відкрите, DayZ глушить інпути, і та сама клавіша
        // більше не спрацьовує -- перевірено на стенді, разом із Back на
        // геймпаді. Меню, яке не закрити, гірше за відсутнє.
        if (name == "BtnClose")
        {
            Close();
            return true;
        }

        if (name == "BtnGo")
        {
            Commit();
            return true;
        }

        if (name == "BtnUp")
        {
            Nudge(1);
            return true;
        }

        if (name == "BtnDown")
        {
            Nudge(-1);
            return true;
        }

        // BACKSPACE, а не «стерти все». Промахнувся однією цифрою -- втрачати
        // через це весь набір безглуздо, а очистити можна й затиснувши.
        if (name == "BtnClear")
        {
            int n = m_Typed.Length();
            if (n > 0)
                m_Typed = m_Typed.Substring(0, n - 1);
            m_Dialled = false;
            Paint();
            return true;
        }

        if (name == "BtnDot")
        {
            if (m_Typed != "" && m_Typed.IndexOf(".") < 0)
                m_Typed = m_Typed + ".";
            m_Dialled = false;
            Paint();
            return true;
        }

        // Btn0..Btn9 -- останній символ імені і є цифрою.
        if (name.Length() == 4 && name.Substring(0, 3) == "Btn")
        {
            // Почав набирати -- відмова більше не актуальна.
            m_HintKey = "#STR_OZR_KEYPAD_HINT";

            // Число на табло поставили стрілки -- цифра починає СВІЙ набір, а
            // не дописується в хвіст готовому «145.500».
            if (m_Dialled)
            {
                m_Typed   = "";
                m_Dialled = false;
            }

            // Довжину обмежуємо: «1451250000» не частота, а промах по клавіші,
            // помножений на десять.
            if (m_Typed.Length() < 8)
                m_Typed = m_Typed + name.Substring(3, 1);
            Paint();
            return true;
        }

        return super.OnClick(w, x, y, button);
    }

    // Підтвердження. Рахуємо ділення, перевіряємо, що воно в смузі й на
    // ґратці профілю, і лише тоді просимо сервер. Сервер перевірить те саме
    // ще раз -- клієнтові тут не вірять, і правильно.
    private void Commit()
    {
        if (!m_Radio || !m_Profile)
        {
            OZR_Log.Dbg("freq keypad: commit ignored - no radio or no profile");
            return;
        }

        // Нічого не набрано й нічого не накручено -- підтверджувати нема чого.
        // TUNE тут означає просто «готово», і мовчазна кнопка на цьому місці
        // читалась би як зламана.
        if (m_Typed == "")
        {
            OZR_Log.Dbg("freq keypad: nothing dialled, closing");
            Close();
            return;
        }

        int lo;
        int hi;
        int stride;
        if (!OZR_ClientGrid.Window(m_Profile, lo, hi, stride))
        {
            OZR_Log.Dbg("freq keypad: commit ignored - this set does not overlap the ether");
            return;
        }

        int idx = Dialled();
        if (idx < lo || idx > hi)
        {
            OZR_Log.Dbg("freq keypad: commit refused - " + m_Typed + " is outside this set's band");
            m_Typed   = "";
            m_Dialled = false;
            m_HintKey = "#STR_OZR_KEYPAD_OUT";
            Paint();
            return;
        }

        Send(OZR_Chan.Snap(idx, lo, hi, stride));

        // Закриваємось одразу. Показати «нову» частоту тут однаково нічим:
        // індекс на клієнті оновиться лише коли сервер його поверне, і
        // домальовувати очікуване значення означало б показати те, чого ще
        // немає -- а на відмову сервера воно й не з'явиться.
        m_Typed   = "";
        m_Dialled = false;
        OZR_Log.Dbg("freq keypad: commit done, closing");
        Close();
    }

    // Набране, у діленнях ефіру. -1, коли не набрано нічого або набране не
    // читається числом.
    private int Dialled()
    {
        if (m_Typed == "")
            return -1;

        float mhz = m_Typed.ToFloat();
        if (mhz <= 0)
            return -1;

        return OZR_ClientGrid.IndexOf(mhz);
    }

    private void Send(int idx)
    {
        OZ_Rpc.ServiceRequest(OZR_Const.SERVICE, OZR_Const.OP_TUNE, "{\"Index\":" + idx.ToString() + "}");
        OZR_Log.Dbg("freq keypad: asked for index " + idx.ToString() + " (" + OZR_Fmt.MHz(OZR_ClientGrid.MHzAt(idx)) + ")");
    }

    // Крок на один СВІЙ канал, по колу відрізка. Набирати частоту цілком
    // заради сусіднього каналу безглуздо, а що таке «сусідній», профіль уже
    // знає.
    //
    // СТРІЛКА КРУТИТЬ ТАБЛО, А НЕ РАЦІЮ (рішення власника 2026-09-09). Раніше
    // вона слала настройку одразу, тож на клавіатурі жило два різні правила:
    // цифри чекали TUNE, а «+» і «-» ходили повз нього. Тепер правило одне --
    // набрав чи накрутив, тоді TUNE.
    private void Nudge(int dir)
    {
        if (!m_Radio || !m_Profile)
            return;

        int lo;
        int hi;
        int stride;
        if (!OZR_ClientGrid.Window(m_Profile, lo, hi, stride))
            return;

        // Крутимо від НАБРАНОГО, якщо набрано щось осмислене: інакше «набрав
        // 145.5, тисну +» відкидало б назад на ту частоту, де рація стоїть.
        int cur = Dialled();
        if (cur < 0)
            cur = m_Radio.OZR_ShownIndex();
        if (cur < lo || cur > hi)
            cur = lo;

        // Спершу прилипаємо до ґратки профілю, потім крокуємо: рація могла
        // стояти між своїми каналами, якщо профіль щойно змінили.
        int k = ((OZR_Chan.Snap(cur, lo, hi, stride) - lo) / stride) + dir;

        int last = (hi - lo) / stride;
        if (k < 0)
            k = last;
        if (k > last)
            k = 0;

        int want = lo + k * stride;

        if (OZR_Log.IsDebug())
        {
            string dbg = "freq keypad: step " + dir.ToString();
            dbg += " cur=" + cur.ToString() + " lo=" + lo.ToString() + " hi=" + hi.ToString();
            dbg += " stride=" + stride.ToString() + " k=" + k.ToString();
            dbg += " -> " + want.ToString();
            OZR_Log.Dbg(dbg);
        }

        // Накручене лягає туди ж, куди й набране: на табло і в намір. Рацію
        // рухає TUNE.
        m_Typed   = OZR_Fmt.MHz(OZR_ClientGrid.MHzAt(want));
        m_Dialled = true;
        m_HintKey = "#STR_OZR_KEYPAD_HINT";
        Paint();
    }

    // Малюємо те, що СПРАВДІ на рації, а не те, що попросили: сервер може
    // відмовити, і домальоване очікування було б брехнею. Відповідь приходить
    // із мережею, тож перемальовуємо за часом, а не за кліком -- і лише коли
    // гравець нічого не набирає, інакше набір затиралося б.
    override void Update(float timeslice)
    {
        super.Update(timeslice);

        // Тягнемо за курсором. Події «миша поїхала» у віджета немає, тож
        // позицію читаємо самі, поки кнопку тримають.
        if (m_Dragging && m_Card)
        {
            int mx, my;
            GetMousePos(mx, my);
            m_Card.SetPos(mx - m_GrabX, my - m_GrabY);
            return;
        }

        m_Since = m_Since + timeslice;
        if (m_Since < 0.25)
            return;
        m_Since = 0;

        // Рацію могли вимкнути або прибрати з рук, поки вікно відкрите.
        // Клавіатура над мертвою коробкою нічого не значить.
        if (!m_Radio || !m_Radio.OZR_IsPowered())
        {
            OZR_Log.Dbg("freq keypad: the radio is gone or switched off, closing");
            Close();
            return;
        }

        if (m_Typed == "")
            Paint();
    }
}
