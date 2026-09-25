// Окно частот «лицом рации».
//
// По K открывается одно окно на все рации - OZR_FreqMenu (OZR_FreqMenu.c) с общей клавиатурой.
// Этот файл даёт тому же окну лицо той рации, что в руках: своя разметка
// (gui/layouts/oz_face_<s>.layout, её пишет models/tools/make_hud_layouts.py), частота на экране
// самой рации, клавиши на корпусе. Картинки лиц - gui/faces/oz_face_<s>.edds.
//
// Отдельным файлом и modded class, а не правкой OZR_FreqMenu.c: окно без лица (класс без
// ozrFaceLayout) остаётся ровно тем, что было, а всё про лица лежит в одном месте. Modded class
// в Enforce видит и private-поля, и private-методы оригинала (вики DayZ:Enforce Script Syntax,
// «Modded private members»). Файл обязан собираться ПОСЛЕ OZR_FreqMenu.c - внутри папки порядок
// алфавитный, и имя OZR_FreqMenuFace.c идёт за ним; не переименовывать в то, что встанет раньше.
// Набор, проверка полосы и запрос к серверу остаются у окна: клавиши разметки носят имена
// кнопок его окна - Btn0..Btn9, BtnUp, BtnDown, BtnGo, BtnDot, BtnClose, DragBar. Своё здесь:
//   - BtnBack: стереть цифру, а если стирать нечего - выйти (EXIT у Baofeng, CLR у PRC);
//   - рация без цифр (ozrFaceMode = "step"): стрелка СРАЗУ переключает канал, окно остаётся;
//   - автоточка: целая часть больше не может расти в пределах полосы - дальше точка;
//   - два ряда экрана: у рации с цифрами сверху то, на чём стоит, снизу набранное; у рации
//     без цифр крупно номер канала, мелко частота.
//
// Что за лицо у класса - в его конфиге: ozrFaceLayout, ozrFaceMode,
// ozrFaceHint. Класс без ozrFaceLayout получает окно мода рации как было.

modded class OZR_FreqMenu
{
    protected bool       m_OZR_Face;
    protected bool       m_OZR_Step;
    protected string     m_OZR_Hint;
    protected TextWidget m_OZR_Main;
    protected TextWidget m_OZR_Sub;

    // Шаг, отправленный серверу и ещё не вернувшийся. Два быстрых нажатия иначе считали бы
    // от одного и того же старого канала и ушли бы на один канал вместо двух. На экран это
    // не попадает: экран, как и у мода рации, показывает только подтверждённое.
    protected int m_OZR_PendingIdx = -1;
    protected int m_OZR_PendingAt;

    private static const int OZR_PENDING_MS = 1500;

    override Widget Init()
    {
        string layout = "";
        string mode = "";
        string image = "";
        EntityAI radio = OZR_InHands();
        if (radio)
        {
            string cfg = "CfgVehicles " + radio.GetType() + " ";
            layout = GetGame().ConfigGetTextOut(cfg + "ozrFaceLayout");
            mode = GetGame().ConfigGetTextOut(cfg + "ozrFaceMode");
            image = GetGame().ConfigGetTextOut(cfg + "ozrFaceImage");
            m_OZR_Hint = GetGame().ConfigGetTextOut(cfg + "ozrFaceHint");
        }
        if (layout == "")
            return super.Init();

        layoutRoot = GetGame().GetWorkspace().CreateWidgets(layout);
        if (!layoutRoot)
        {
            // Лицо не собралось - окно мода рации лучше, чем никакого.
            OZR_Log.Error("face keypad: " + layout + " produced no widgets, falling back to the stock keypad");
            return super.Init();
        }

        m_OZR_Face = true;
        m_OZR_Step = mode == "step";
        m_Card  = layoutRoot;
        m_Title = TextWidget.Cast(layoutRoot.FindAnyWidget("TitleText"));
        m_Hint  = TextWidget.Cast(layoutRoot.FindAnyWidget("HintText"));
        // Табло и полосы мода рации в лице нет: экран рисует OZR_Paint, и его строки никто
        // не должен перезаписывать.
        m_Freq = null;
        m_Band = null;
        m_OZR_Main = TextWidget.Cast(layoutRoot.FindAnyWidget("LcdMain"));
        m_OZR_Sub  = TextWidget.Cast(layoutRoot.FindAnyWidget("LcdSub"));

        OZR_Load("Face", image);

        OZR_Log.Dbg("face keypad: " + layout + " (" + mode + ")");
        return layoutRoot;
    }

    // Картинка в ImageWidget из скрипта, а не только из image0 разметки: так путь приходит из
    // конфига класса, и промах виден в логе, а не пустым местом на экране.
    protected void OZR_Load(string widget, string path)
    {
        ImageWidget w = ImageWidget.Cast(layoutRoot.FindAnyWidget(widget));
        if (!w || path == "")
            return;
        if (w.LoadImageFile(0, path))
            w.SetImage(0);
        else
            OZR_Log.Warn("face keypad: " + widget + " image not loaded: " + path);
    }

    // Рация в руках - та же проверка, что в Grab() мода рации, но Init идёт раньше OnShow.
    protected static EntityAI OZR_InHands()
    {
        PlayerBase p = PlayerBase.Cast(GetGame().GetPlayer());
        if (!p || !p.GetHumanInventory())
            return null;
        return TransmitterBase.Cast(p.GetHumanInventory().GetEntityInHands());
    }

    override void Paint()
    {
        if (!m_OZR_Face)
        {
            super.Paint();
            return;
        }

        if (m_Title)
        {
            string title = "";
            if (m_Radio)
                title = m_Radio.GetDisplayName();
            m_Title.SetText(title);
        }

        string now = "";
        if (m_Radio)
            now = OZR_Fmt.MHz(OZR_ClientGrid.MHzAt(m_Radio.OZR_ShownIndex()));

        if (m_OZR_Step)
        {
            if (m_OZR_Main)
                m_OZR_Main.SetText(OZR_Channel());
            if (m_OZR_Sub)
                m_OZR_Sub.SetText(now);
        }
        else
        {
            if (m_OZR_Main)
                m_OZR_Main.SetText(now);
            if (m_OZR_Sub)
                m_OZR_Sub.SetText(m_Typed);
        }

        // Подсказка мода рации зовёт жать TUNE, а у этой рации своя клавиша ввода. Отказ
        // («вне полосы») остаётся его.
        if (m_Hint)
        {
            if (m_HintKey == "#STR_OZR_KEYPAD_HINT" && m_OZR_Hint != "")
                m_Hint.SetText(m_OZR_Hint);
            else
                m_Hint.SetText(m_HintKey);
        }
    }

    // Номер канала в своей полосе рации, с единицы. Пусто, пока полоса не известна.
    protected string OZR_Channel()
    {
        if (!m_Radio || !m_Profile)
            return "";

        int lo;
        int hi;
        int stride;
        if (!OZR_ClientGrid.Window(m_Profile, lo, hi, stride) || stride <= 0)
            return "";

        int cur = OZR_Chan.Snap(m_Radio.OZR_ShownIndex(), lo, hi, stride);
        int k = (cur - lo) / stride + 1;
        return k.ToString();
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!m_OZR_Face || !w)
            return super.OnClick(w, x, y, button);

        string name = w.GetName();

        if (name == "BtnBack")
        {
            int n = m_Typed.Length();
            if (n > 0)
            {
                m_Typed = m_Typed.Substring(0, n - 1);
                m_Dialled = false;
                Paint();
            }
            else
            {
                Close();
            }
            return true;
        }

        if (m_OZR_Step && (name == "BtnUp" || name == "BtnDown"))
        {
            if (name == "BtnUp")
                OZR_StepNow(1);
            else
                OZR_StepNow(-1);
            return true;
        }

        // Автоточка: точка встаёт сама, только когда целая часть расти уже не может - с ещё
        // одной цифрой она точно вышла бы за верх полосы этой рации. Полоса бывает любой
        // (частоты двузначные, трёхзначные, четырёхзначные), поэтому не число цифр, а сама
        // граница: при 136-156 после «136» (1360 > 156), при 80-1200 после «850», а «85» там
        // неоднозначно (85.125 или 850) - точку ставит игрок, клавиша точки есть у всех раций
        // с цифрами.
        if (name.Length() == 4 && name.Substring(0, 3) == "Btn" && !m_Dialled && m_Profile)
        {
            if (m_Typed != "" && m_Typed.IndexOf(".") < 0 && OZR_IntComplete())
                m_Typed = m_Typed + ".";
        }

        return super.OnClick(w, x, y, button);
    }

    // Целая часть набрана до конца: приписав к ней любую цифру, выйдем за верх полосы.
    protected bool OZR_IntComplete()
    {
        int top = m_Profile.MaxMHz;
        int typed = m_Typed.ToInt();
        return typed * 10 > top;
    }

    // Шаг на свой канал СРАЗУ, без TUNE: у рации без цифр набирать нечего, и подтверждение
    // на каждый шаг было бы лишним нажатием. Окно остаётся открытым - шагать можно подряд.
    protected void OZR_StepNow(int dir)
    {
        if (!m_Radio || !m_Profile)
            return;

        int lo;
        int hi;
        int stride;
        if (!OZR_ClientGrid.Window(m_Profile, lo, hi, stride) || stride <= 0)
            return;

        int cur = m_Radio.OZR_ShownIndex();
        int now = GetGame().GetTime();
        if (m_OZR_PendingIdx >= 0 && now - m_OZR_PendingAt < OZR_PENDING_MS && cur != m_OZR_PendingIdx)
            cur = m_OZR_PendingIdx;
        if (cur < lo || cur > hi)
            cur = lo;

        int k = ((OZR_Chan.Snap(cur, lo, hi, stride) - lo) / stride) + dir;
        int last = (hi - lo) / stride;
        if (k < 0)
            k = last;
        if (k > last)
            k = 0;

        int want = lo + k * stride;
        m_OZR_PendingIdx = want;
        m_OZR_PendingAt = now;
        m_Typed = "";
        m_Dialled = false;
        Send(want);
    }
}
