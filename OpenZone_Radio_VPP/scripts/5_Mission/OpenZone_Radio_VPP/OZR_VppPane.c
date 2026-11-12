// Сторінка «Профілі рацій» модуля «Рація» в адмінському вікні OpenZone (VPP rework
// 2026-11-12, design 5.4): профілі ручних рацій списком і карткою вибраного. Чіпляється
// до вікна ядра через modded class -- ядро про рацію не знає й знати не мусить. Розмітка
// -- з опису ui/OpenZone_Radio_VPP/ozr_vpp_pane.json (до 2026-11-12 це була єдина
// написана руками розмітка вікна).
//
// Гарди: NO_GUI -- сервер компілює Mission без UI; AVPPAdminTools і OpenZone_VPP --
// імена класів CfgMods (їх авто-дефайнить рушій).
//
// ЧОМУ ЦЕ НЕ РЕДАКТОР JSON. Ефір НЕ задається окремо -- він ВИВОДИТЬСЯ з цих самих
// профілів (OZR_Ether.Derive): низ -- найнижча межа, верх -- найвища, крок --
// найбільший спільний дільник усіх кроків і всіх зміщень меж. Тому профіль не може «не
// влізти в сітку»: сітка йде за ним. Але два наслідки цього в тексті JSON не видно
// взагалі, і саме заради них сторінка існує:
//
//   1. ЕФІР МІНЯЄТЬСЯ ВІД ОДНОГО ЧИСЛА. Дрібніший крок в одній рації подрібнює крок
//      УСЬОГО ефіру, бо НСД падає; ширша смуга розсуває його межі. Сторінка показує,
//      яким ефір СТАНЕ, ще до збереження.
//   2. Є СТЕЛЯ, і вона не з рушія, а з рішення власника (2026-09-01, ТЗ-5 R-E4): 65536
//      ділень ефіру. Ефір, якому треба більше, сервер відхилить -- тож сторінка каже про
//      це ДО збереження, з числом, якого не вистачило.
//
// І третє, вже про час: файл сітки читає нативний патч при старті ПРОЦЕСУ, тож новий
// ефір діє з наступного запуску сервера. Сторінка каже, що зараз у ефірі й що стане
// після рестарту -- мовчазна відкладена дія гірша за відсутню.
//
// Дальність НЕ РЕДАГУЄТЬСЯ, і це не лінощі. `range` живе в CfgVehicles класу, його
// читає сам рушій, а скрипту доступні лише ConfigGetFloat і рідня -- жодного ConfigSet
// у грі немає. Тому поле показує справжнє число з конфігу класу і мовчить.
//
// Чернетка: NEW і DELETE міняють список на сторінці, поля -- вибраний профіль; на
// сервер усе йде одним файлом кнопкою «Зберегти все», через смугу підтвердження вікна
// (design 3.4), як і видалення, і відкидання незбережених правок (D106: перейти на
// інший рядок, NEW, перечитати). «Так» вертається в OnConfirmed дією "ozr:".
//
// Члени цього шару починаються з Ozr (поля -- m_Ozr): той самий клас модифікує кожна
// склейка, і ім'я, яке мають двоє, не компілюється.

#ifdef AVPPAdminTools
#ifdef OpenZone_VPP
#ifndef NO_GUI

modded class OZ_VppAdminMenu
{
    static const string OZR_PAGE = "radio.profiles";

    // The profiles as the page holds them: the server's file, with NEW and DELETE laid
    // over it until Save all sends it.
    private ref OZR_Profiles m_OzrCfg;
    // The picked row: an index of m_OzrCfg.Radios, -1 for none.
    private int  m_OzrPicked = -1;
    // NEW or DELETE changed the list since the server's file.
    private bool m_OzrDraft = false;
    // Rebuilding the list selects a row; the OnItemSelected that comes of it is not a
    // pick (the same flag the core and the other pages keep).
    private bool m_OzrRepaint = false;

    override void OnCreate(Widget RootW)
    {
        super.OnCreate(RootW);
        if (!M_SUB_WIDGET)
            return;

        Widget pane = GetGame().GetWorkspace().CreateWidgets("OpenZone_Radio_VPP/gui/layouts/ozr_vpp_pane.layout", M_SUB_WIDGET);
        if (!pane)
        {
            OZR_Log.Error("radio vpp page: layout failed to load");
            return;
        }

        // The page names its hint line itself: the core knows no glue's widgets.
        RegisterPage("radio", "#STR_OZR_VPP_MOD", OZR_PAGE, "#STR_OZR_VPP_PAGE_PROFILES", pane, "RadHint");
        OzrPaintCard();
    }

    override void OnPaneShown(string id)
    {
        super.OnPaneShown(id);
        if (id != OZR_PAGE)
            return;

        // The admin's unsaved work stays on the page; otherwise the server's file.
        if (!OzrUnsaved())
            AskCfg(OZR_VppModule.CFG_PROFILES);
        OzrPaintCard();
    }

    // Every name goes on to super: Ядро › Файли конфігів shows the same file raw, and
    // this layer used to keep it to itself and leave that editor empty.
    override void OnCfgText(string name, string body)
    {
        if (name == OZR_VppModule.CFG_PROFILES)
            OzrOnProfilesText(body);
        super.OnCfgText(name, body);
    }

    override void OnCfgApplied()
    {
        super.OnCfgApplied();
        if (CurrentPane() == OZR_PAGE)
            AskCfg(OZR_VppModule.CFG_PROFILES);
    }

    // The confirm strip's "yes" (design 3.4). The radio's actions start with "ozr:".
    override void OnConfirmed(string action)
    {
        if (action.IndexOf("ozr:") != 0)
        {
            super.OnConfirmed(action);
            return;
        }

        if (action == "ozr:save")
        {
            OzrSaveNow();
            return;
        }
        if (action == "ozr:new")
        {
            OzrNewNow();
            return;
        }
        if (action == "ozr:reload")
        {
            OzrReloadNow();
            return;
        }
        if (action.IndexOf("ozr:del:") == 0)
        {
            OzrDeleteNow(action.Substring(8, action.Length() - 8));
            return;
        }
        if (action.IndexOf("ozr:switch:") == 0)
            OzrSwitchNow(action.Substring(11, action.Length() - 11));
    }

    // ------------------------------------------------------------ файл

    private void OzrOnProfilesText(string body)
    {
        bool shown = CurrentPane() == OZR_PAGE;

        // The admin's unsaved work stays: the same file arrives for Config files too.
        if (OzrUnsaved())
        {
            if (shown)
                Hint("#STR_OZR_VPP_H_KEPT");
            return;
        }

        // The root made by the script, then a copy made by the script before anything
        // else is allocated (the core's OZ_ConfigBase header): every profile in the list
        // was made by the serializer, and the page holds them the admin's whole session.
        OZR_Profiles parsed = new OZR_Profiles();
        string err;
        if (!JsonFileLoader<OZR_Profiles>.LoadData(body, parsed, err) || !parsed)
        {
            if (shown)
            {
                string bad = Widget.TranslateString("#STR_OZR_VPP_H_BAD");
                Hint(bad + " " + err);
            }
            return;
        }
        OZR_Profiles fresh = parsed.Copy();

        // The picked profile is found again by class: the order may have changed.
        string was = OzrPickedClass();
        m_OzrCfg = fresh;
        m_OzrDraft = false;
        m_OzrPicked = OzrFindClass(was);
        OzrRebuildList();
        if (m_OzrPicked >= 0)
            OzrFill(m_OzrPicked);
        else
            OzrClearForm();

        if (shown)
            Hint("#STR_OZR_VPP_H_LOADED");
    }

    // ------------------------------------------------------------ сітка

    // "136.000 - 155.950 MHz, step 0.0500, 400 divisions" -- in the admin's language. The
    // numbers are OZR_Fmt's, the ones the fields and the server's log show.
    private string OzrGridText(float baseMHz, float step, int count)
    {
        if (count < 1)
            return "-";

        string mhz = Widget.TranslateString("#STR_OZR_VPP_MHZ");
        string stepWord = Widget.TranslateString("#STR_OZR_VPP_STEP_WORD");
        string divs = Widget.TranslateString("#STR_OZR_VPP_DIVISIONS");
        float top = baseMHz + (count - 1) * step;

        string s = OZR_Fmt.MHz(baseMHz) + " - " + OZR_Fmt.MHz(top);
        s = s + " " + mhz + ", " + stepWord;
        s = s + " " + OZR_Fmt.Step(step) + ", ";
        s = s + count.ToString() + " " + divs;
        return s;
    }

    // The ether now: what the server sent with the core's sync packet.
    private void OzrPaintGrid()
    {
        if (!OZR_ClientGrid.Ready())
        {
            OzrSay("RadGrid", "#STR_OZR_VPP_NO_GRID", OZR_VppMetal.MUTED);
            return;
        }
        string now = OzrGridText(OZR_ClientGrid.BaseMHz(), OZR_ClientGrid.StepMHz(), OZR_ClientGrid.Count());
        OzrSay("RadGrid", now, OZR_VppMetal.TEXT);
    }

    // The profiles as they would be sent: copies, the picked one from the fields. The
    // point of the warning is to see the result BEFORE saving.
    private ref array<ref OZR_RadioProfile> OzrPlannedProfiles()
    {
        array<ref OZR_RadioProfile> what = new array<ref OZR_RadioProfile>();
        if (!m_OzrCfg)
            return what;

        for (int i = 0; i < m_OzrCfg.Radios.Count(); i++)
        {
            OZR_RadioProfile src = m_OzrCfg.Radios[i];
            OZR_RadioProfile cp = src.Copy();
            if (i == m_OzrPicked)
            {
                cp.ClassName = OzrTrimmed("RadF_Class");
                cp.MinMHz    = OzrTrimmed("RadF_Min").ToFloat();
                cp.MaxMHz    = OzrTrimmed("RadF_Max").ToFloat();
                cp.StepMHz   = OzrTrimmed("RadF_Step").ToFloat();
            }
            what.Insert(cp);
        }
        return what;
    }

    // The ether that comes of the page as it is now, by the same function the server
    // derives it with -- otherwise the warning here and the refusal there could part.
    private OZR_EtherPlan OzrPlanned()
    {
        if (!m_OzrCfg)
            return null;
        array<ref OZR_RadioProfile> what = OzrPlannedProfiles();
        return OZR_Ether.Derive(what);
    }

    private bool OzrSameAsRunning(OZR_EtherPlan plan)
    {
        if (!OZR_ClientGrid.Ready())
            return false;
        return OZR_Ether.Same(plan, OZR_ClientGrid.BaseMHz(), OZR_ClientGrid.StepMHz(), OZR_ClientGrid.Count());
    }

    // The ether after a restart, in words: refused (and why), the same, or the new grid.
    private string OzrPlanText(OZR_EtherPlan plan)
    {
        if (!plan)
            return "";
        if (!plan.Ok)
        {
            string refused = Widget.TranslateString("#STR_OZR_VPP_REFUSED");
            return refused + " " + plan.Why;
        }
        if (OzrSameAsRunning(plan))
        {
            string same = Widget.TranslateString("#STR_OZR_VPP_SAME");
            return same;
        }
        return OzrGridText(plan.BaseMHz, plan.StepMHz, plan.Count);
    }

    private void OzrPaintEther()
    {
        OZR_EtherPlan plan = OzrPlanned();
        bool warn = false;
        int ink = OZR_VppMetal.MUTED;
        if (plan && !plan.Ok)
            ink = OZR_VppMetal.BAD;
        else if (plan && OzrSameAsRunning(plan))
            ink = OZR_VppMetal.OK;
        else if (plan)
        {
            ink = OZR_VppMetal.ALERT;
            warn = true;
        }
        string afterText = OzrPlanText(plan);
        OzrSay("RadEther", afterText, ink);
        OzrShow("OzrWarn", warn);
    }

    // ------------------------------------------------------------ список

    private void OzrRebuildList()
    {
        TextListboxWidget lb = TextListboxWidget.Cast(M_SUB_WIDGET.FindAnyWidget("RadList"));
        if (!lb || !m_OzrCfg)
            return;

        m_OzrRepaint = true;
        lb.ClearItems();
        for (int i = 0; i < m_OzrCfg.Radios.Count(); i++)
        {
            OZR_RadioProfile p = m_OzrCfg.Radios[i];
            string line = OzrRowName(p);
            line = line + "   " + OZR_Fmt.MHz(p.MinMHz);
            line = line + "-" + OZR_Fmt.MHz(p.MaxMHz);
            line = line + " / " + OZR_Fmt.Step(p.StepMHz);
            line = line + "   " + OzrRangeOf(p.ClassName);
            lb.AddItem(line, NULL, 0);
        }
        m_OzrRepaint = false;
        OzrSelectPicked();
    }

    private void OzrSelectPicked()
    {
        TextListboxWidget lb = TextListboxWidget.Cast(M_SUB_WIDGET.FindAnyWidget("RadList"));
        if (!lb)
            return;
        m_OzrRepaint = true;
        if (m_OzrCfg && m_OzrPicked >= 0 && m_OzrPicked < m_OzrCfg.Radios.Count())
            lb.SelectRow(m_OzrPicked);
        else
            lb.SelectRow(-1);
        m_OzrRepaint = false;
    }

    // The class, or "(new)" for a profile that has none yet.
    private string OzrRowName(OZR_RadioProfile p)
    {
        if (p.ClassName != "")
            return p.ClassName;
        string fresh = Widget.TranslateString("#STR_OZR_VPP_NEW_ROW");
        return "(" + fresh + ")";
    }

    // The range the item's config gives, as the engine reads it: "250 m", or "?".
    private string OzrRangeOf(string cls)
    {
        if (cls == "")
            return "-";
        string path = "CfgVehicles " + cls + " range";
        if (!GetGame().ConfigIsExisting(path))
            return "?";
        float r = GetGame().ConfigGetFloat(path);
        string meters = Widget.TranslateString("#STR_OZR_VPP_M");
        return Math.Round(r).ToString() + " " + meters;
    }

    private string OzrPickedClass()
    {
        if (!m_OzrCfg || m_OzrPicked < 0 || m_OzrPicked >= m_OzrCfg.Radios.Count())
            return "";
        return m_OzrCfg.Radios[m_OzrPicked].ClassName;
    }

    private int OzrFindClass(string cls)
    {
        if (!m_OzrCfg || cls == "")
            return -1;
        for (int i = 0; i < m_OzrCfg.Radios.Count(); i++)
        {
            if (m_OzrCfg.Radios[i].ClassName == cls)
                return i;
        }
        return -1;
    }

    // Whether the fields differ from the picked profile in the list.
    private bool OzrDirty()
    {
        if (!m_OzrCfg || m_OzrPicked < 0 || m_OzrPicked >= m_OzrCfg.Radios.Count())
            return false;

        OZR_RadioProfile p = m_OzrCfg.Radios[m_OzrPicked];
        if (OzrTrimmed("RadF_Class") != p.ClassName)
            return true;
        if (OzrTrimmed("RadF_Min") != OZR_Fmt.MHz(p.MinMHz))
            return true;
        if (OzrTrimmed("RadF_Max") != OZR_Fmt.MHz(p.MaxMHz))
            return true;
        string step = OZR_Fmt.Step(p.StepMHz);
        return OzrTrimmed("RadF_Step") != step;
    }

    // Work of the admin's the server has not seen: a changed list, or changed fields.
    private bool OzrUnsaved()
    {
        if (m_OzrDraft)
            return true;
        return OzrDirty();
    }

    // The question before unsaved fields go: "Unsaved edits of the profile X: discard them?"
    private string OzrDropQuestion()
    {
        string ask = Widget.TranslateString("#STR_OZR_VPP_ASK_SWITCH");
        string tail = Widget.TranslateString("#STR_OZR_VPP_ASK_SWITCH_TAIL");
        string name = OzrRowName(m_OzrCfg.Radios[m_OzrPicked]);
        string text = ask + " " + name;
        text = text + ": " + tail;
        return text;
    }

    // UNSAVED EDITS ARE NOT LOST SILENTLY (D106): another row asks on the confirm strip
    // first, and the list keeps its highlight on the profile being edited meanwhile.
    private void OzrPick(int row)
    {
        if (!m_OzrCfg || row < 0 || row >= m_OzrCfg.Radios.Count() || row == m_OzrPicked)
            return;

        if (OzrDirty())
        {
            string text = OzrDropQuestion();
            Confirm(text, "#STR_OZR_VPP_YES_DROP", "ozr:switch:" + row.ToString());
            OzrSelectPicked();
            return;
        }
        OzrFill(row);
    }

    private void OzrSwitchNow(string rowText)
    {
        int row = rowText.ToInt();
        if (!m_OzrCfg || row < 0 || row >= m_OzrCfg.Radios.Count())
            return;
        OzrFill(row);
    }

    private void OzrFill(int row)
    {
        if (!m_OzrCfg || row < 0 || row >= m_OzrCfg.Radios.Count())
            return;

        m_OzrPicked = row;
        OZR_RadioProfile p = m_OzrCfg.Radios[row];
        SetEdit("RadF_Class", p.ClassName);
        SetEdit("RadF_Min",   OZR_Fmt.MHz(p.MinMHz));
        SetEdit("RadF_Max",   OZR_Fmt.MHz(p.MaxMHz));
        SetEdit("RadF_Step",  OZR_Fmt.Step(p.StepMHz));
        OzrSelectPicked();
        OzrPaintCard();
    }

    private void OzrClearForm()
    {
        m_OzrPicked = -1;
        SetEdit("RadF_Class", "");
        SetEdit("RadF_Min",   "");
        SetEdit("RadF_Max",   "");
        SetEdit("RadF_Step",  "");
        OzrSelectPicked();
        OzrPaintCard();
    }

    // ------------------------------------------------------------ картка

    private void OzrPaintCard()
    {
        if (!M_SUB_WIDGET)
            return;

        bool picked = false;
        if (m_OzrCfg && m_OzrPicked >= 0 && m_OzrPicked < m_OzrCfg.Radios.Count())
            picked = true;

        if (picked)
        {
            string title = OzrRowName(m_OzrCfg.Radios[m_OzrPicked]);
            OzrSay("OzrCardTitle", title, OZR_VppMetal.TEXT);
        }
        else
            OzrSay("OzrCardTitle", "#STR_OZR_VPP_PICK", OZR_VppMetal.MUTED);
        OzrShow("BtnRadDel", picked);

        OzrPaintGrid();
        OzrPaintChecks();
    }

    // The range from the class's config, not a copy in JSON: a copy would part from the
    // engine, and a difference in THIS number shows nowhere -- the radio just does not
    // reach as far as the page says.
    private void OzrPaintRange(string cls)
    {
        if (cls == "")
        {
            OzrSay("RadF_Range", "-", OZR_VppMetal.MUTED);
            OzrSay("OzrRangeH", "#STR_OZR_VPP_F_RANGE_HINT", OZR_VppMetal.MUTED);
            return;
        }
        string range = OzrRangeOf(cls);
        if (range == "?")
        {
            OzrSay("RadF_Range", "?", OZR_VppMetal.ALERT);
            OzrSay("OzrRangeH", "#STR_OZR_VPP_NO_RANGE", OZR_VppMetal.ALERT);
            return;
        }
        OzrSay("RadF_Range", range, OZR_VppMetal.TEXT);
        OzrSay("OzrRangeH", "#STR_OZR_VPP_F_RANGE_HINT", OZR_VppMetal.MUTED);
    }

    // One line of the checks and the dot before it.
    private void OzrCheck(int i, string text, int dot)
    {
        string name = "RadF_Fit2";
        if (i == 0)
            name = "RadF_Chan";
        else if (i == 1)
            name = "RadF_Fit1";

        int ink = OZR_VppMetal.TEXT;
        if (dot == OZR_VppMetal.FAINT)
            ink = OZR_VppMetal.MUTED;
        OzrSay(name, text, ink);
        OzrColor("OzrDot" + i.ToString(), dot);
    }

    // Counted from the FIELDS, not from the saved profile: the point is to see the result
    // before saving.
    private void OzrPaintChecks()
    {
        OzrPaintRange(OzrTrimmed("RadF_Class"));
        OzrPaintEther();

        float lo   = OzrTrimmed("RadF_Min").ToFloat();
        float hi   = OzrTrimmed("RadF_Max").ToFloat();
        float step = OzrTrimmed("RadF_Step").ToFloat();

        // An empty field is no error, it is "not filled yet": nobody typed the zero.
        if (lo <= 0 || hi <= 0 || step <= 0)
        {
            OzrCheck(0, "-", OZR_VppMetal.FAINT);
            OzrCheck(1, "#STR_OZR_VPP_EMPTY_FORM", OZR_VppMetal.FAINT);
            OzrCheck(2, "", OZR_VppMetal.FAINT);
            return;
        }
        if (hi <= lo)
        {
            OzrCheck(0, "-", OZR_VppMetal.BAD);
            OzrCheck(1, "#STR_OZR_VPP_HI_LO", OZR_VppMetal.BAD);
            OzrCheck(2, "", OZR_VppMetal.FAINT);
            return;
        }

        // The whole ether is refused: there is no grid to count this profile's channels in.
        OZR_EtherPlan plan = OzrPlanned();
        if (!plan || !plan.Ok)
        {
            OzrCheck(0, "-", OZR_VppMetal.BAD);
            OzrCheck(1, "#STR_OZR_VPP_NO_PLAN", OZR_VppMetal.BAD);
            OzrCheck(2, "", OZR_VppMetal.FAINT);
            return;
        }

        int stride = Math.Round(step / plan.StepMHz);
        if (stride < 1)
            stride = 1;
        int count = Math.Round((hi - lo) / step) + 1;

        string chWord = Widget.TranslateString("#STR_OZR_VPP_CHANNELS");
        string fromWord = Widget.TranslateString("#STR_OZR_VPP_FROM");
        string toWord = Widget.TranslateString("#STR_OZR_VPP_TO");
        string chan = chWord + " " + count.ToString();
        chan = chan + "   " + fromWord;
        chan = chan + " " + OZR_Fmt.MHz(lo);
        chan = chan + " " + toWord;
        chan = chan + " " + OZR_Fmt.MHz(hi);
        OzrCheck(0, chan, OZR_VppMetal.OK);

        string strideWord = Widget.TranslateString("#STR_OZR_VPP_STRIDE");
        string etherStep = Widget.TranslateString("#STR_OZR_VPP_ETHER_STEP");
        string every = strideWord + " " + stride.ToString();
        every = every + " x " + etherStep;
        OzrCheck(1, every, OZR_VppMetal.OK);

        // The one question that can still be answered "no": whether the profile works
        // NOW or only after the restart. The ether follows it either way, not this second.
        string nowWord = Widget.TranslateString("#STR_OZR_VPP_NOW");
        if (!OZR_ClientGrid.Ready())
        {
            string noGrid = Widget.TranslateString("#STR_OZR_VPP_NO_GRID");
            OzrCheck(2, nowWord + " " + noGrid, OZR_VppMetal.FAINT);
            return;
        }

        float gLo = OZR_ClientGrid.MHzAt(0);
        float gHi = OZR_ClientGrid.MHzAt(OZR_ClientGrid.Count() - 1);
        float gTol = OZR_ClientGrid.StepMHz() * 0.5;
        if (lo < gLo - gTol || hi > gHi + gTol)
        {
            float cLo = lo;
            float cHi = hi;
            if (cLo < gLo)
                cLo = gLo;
            if (cHi > gHi)
                cHi = gHi;
            string clamp = Widget.TranslateString("#STR_OZR_VPP_NOW_CLAMP");
            string notNow = nowWord + " " + clamp;
            notNow = notNow + " " + OZR_Fmt.MHz(cLo);
            notNow = notNow + " - " + OZR_Fmt.MHz(cHi);
            OzrCheck(2, notNow, OZR_VppMetal.ALERT);
            return;
        }

        string yesWord = Widget.TranslateString("#STR_OZR_VPP_NOW_YES");
        OzrCheck(2, nowWord + " " + yesWord, OZR_VppMetal.OK);
    }

    // ------------------------------------------------------------ правки

    private void OzrAskNew()
    {
        if (!m_OzrCfg)
        {
            Hint("#STR_OZR_VPP_H_NOT_LOADED");
            return;
        }

        // NEW changes the picked profile too: unsaved edits are named first (D106).
        if (OzrDirty())
        {
            string text = OzrDropQuestion();
            Confirm(text, "#STR_OZR_VPP_YES_DROP", "ozr:new");
            return;
        }
        OzrNewNow();
    }

    private void OzrNewNow()
    {
        if (!m_OzrCfg)
            return;

        OZR_RadioProfile p = new OZR_RadioProfile();
        p.ClassName = "";

        // The blank lies on the running grid: give it an item class and it works.
        if (OZR_ClientGrid.Ready())
        {
            p.MinMHz  = OZR_ClientGrid.MHzAt(0);
            p.MaxMHz  = OZR_ClientGrid.MHzAt(OZR_ClientGrid.Count() - 1);
            p.StepMHz = OZR_ClientGrid.StepMHz();
        }

        m_OzrCfg.Radios.Insert(p);
        m_OzrDraft = true;
        m_OzrPicked = m_OzrCfg.Radios.Count() - 1;
        OzrRebuildList();
        OzrFill(m_OzrPicked);
        Hint("#STR_OZR_VPP_H_NEW");
    }

    private void OzrAskDelete()
    {
        if (!m_OzrCfg || m_OzrPicked < 0 || m_OzrPicked >= m_OzrCfg.Radios.Count())
        {
            Hint("#STR_OZR_VPP_H_PICK");
            return;
        }

        OZR_RadioProfile p = m_OzrCfg.Radios[m_OzrPicked];
        string ask = Widget.TranslateString("#STR_OZR_VPP_ASK_DEL");
        string tail = Widget.TranslateString("#STR_OZR_VPP_ASK_DEL_TAIL");
        string name = OzrRowName(p);
        string text = ask + " " + name;
        text = text + " " + tail;
        string action = "ozr:del:" + m_OzrPicked.ToString();
        action = action + ":" + p.ClassName;
        Confirm(text, "#STR_OZR_VPP_YES_DEL", action);
    }

    // The strip's "yes" for "<row>:<class>". The strip may stay open while the admin
    // works on, so the row is checked against the class it asked about, and found again
    // by class when it moved; a gone profile is said, not replaced by another.
    private void OzrDeleteNow(string what)
    {
        if (!m_OzrCfg)
            return;
        int colon = what.IndexOf(":");
        if (colon < 0)
            return;
        int row = what.Substring(0, colon).ToInt();
        string cls = what.Substring(colon + 1, what.Length() - colon - 1);

        bool same = false;
        if (row >= 0 && row < m_OzrCfg.Radios.Count() && m_OzrCfg.Radios[row].ClassName == cls)
            same = true;
        if (!same)
            row = OzrFindClass(cls);
        if (row < 0)
        {
            Hint("#STR_OZR_VPP_H_GONE");
            return;
        }

        string gone = OzrRowName(m_OzrCfg.Radios[row]);
        // RemoveOrdered: Remove swaps with the last, and the file an admin reads by eye
        // would reshuffle with every delete.
        m_OzrCfg.Radios.RemoveOrdered(row);
        m_OzrDraft = true;

        if (row == m_OzrPicked)
        {
            m_OzrPicked = -1;
            OzrRebuildList();
            OzrClearForm();
        }
        else
        {
            if (row < m_OzrPicked)
                m_OzrPicked = m_OzrPicked - 1;
            OzrRebuildList();
            OzrPaintCard();
        }

        string removed = Widget.TranslateString("#STR_OZR_VPP_H_REMOVED");
        Hint(gone + ": " + removed);
    }

    // What the fields cannot be saved with, in words; "" when they can. CHECKED BEFORE
    // THE LIST (D106): numbers used to land in the profile and be refused after, and the
    // spoilt row stayed in memory for the next Save all to write silently.
    private string OzrFormProblem()
    {
        if (!m_OzrCfg || m_OzrPicked < 0 || m_OzrPicked >= m_OzrCfg.Radios.Count())
            return "";

        if (OzrTrimmed("RadF_Class") == "")
            return Widget.TranslateString("#STR_OZR_VPP_CLASS_EMPTY");
        float lo   = OzrTrimmed("RadF_Min").ToFloat();
        float hi   = OzrTrimmed("RadF_Max").ToFloat();
        float step = OzrTrimmed("RadF_Step").ToFloat();
        if (hi <= lo)
            return Widget.TranslateString("#STR_OZR_VPP_HI_LO");
        if (step <= 0)
            return Widget.TranslateString("#STR_OZR_VPP_STEP_ZERO");
        return "";
    }

    // What the server would refuse the whole file for (OZR_ProfilesApplier): a profile
    // OZR_RadioProfile.Problem names, or a class listed twice.
    private string OzrListProblem()
    {
        array<ref OZR_RadioProfile> what = OzrPlannedProfiles();
        array<string> seen = new array<string>();
        for (int i = 0; i < what.Count(); i++)
        {
            OZR_RadioProfile p = what[i];
            string bad = p.Problem();
            if (bad != "")
                return p.Named() + " " + bad;
            if (seen.Find(p.ClassName) != -1)
            {
                string twice = Widget.TranslateString("#STR_OZR_VPP_H_TWICE");
                return p.ClassName + " " + twice;
            }
            seen.Insert(p.ClassName);
        }
        return "";
    }

    private void OzrAskSave()
    {
        if (!m_OzrCfg)
        {
            Hint("#STR_OZR_VPP_H_NOT_LOADED");
            return;
        }
        string formBad = OzrFormProblem();
        if (formBad != "")
        {
            Hint(formBad);
            return;
        }
        string listBad = OzrListProblem();
        if (listBad != "")
        {
            Hint(listBad);
            return;
        }

        OZR_EtherPlan plan = OzrPlanned();
        string ask = Widget.TranslateString("#STR_OZR_VPP_ASK_SAVE");
        string after = OzrPlanText(plan);
        Confirm(ask + " " + after, "#STR_OZR_VPP_YES_SAVE", "ozr:save");
    }

    // The strip's "yes": the fields go into the PICKED profile alone -- the rest are in
    // the list already -- and the whole file to the server. The server derives the ether,
    // writes the grid file for the next start and sends the profiles to everyone online.
    private void OzrSaveNow()
    {
        if (!m_OzrCfg)
            return;
        string formBad = OzrFormProblem();
        if (formBad != "")
        {
            Hint(formBad);
            return;
        }
        string listBad = OzrListProblem();
        if (listBad != "")
        {
            Hint(listBad);
            return;
        }

        if (m_OzrPicked >= 0 && m_OzrPicked < m_OzrCfg.Radios.Count())
        {
            OZR_RadioProfile p = m_OzrCfg.Radios[m_OzrPicked];
            p.ClassName = OzrTrimmed("RadF_Class");
            p.MinMHz    = OzrTrimmed("RadF_Min").ToFloat();
            p.MaxMHz    = OzrTrimmed("RadF_Max").ToFloat();
            p.StepMHz   = OzrTrimmed("RadF_Step").ToFloat();
        }

        string body;
        string err;
        if (!JsonFileLoader<OZR_Profiles>.MakeData(m_OzrCfg, body, err, false))
        {
            string noJson = Widget.TranslateString("#STR_OZR_VPP_H_NO_JSON");
            Hint(noJson + " " + err);
            return;
        }

        SendCfg(OZR_VppModule.CFG_PROFILES, body);
        m_OzrDraft = false;
        OzrRebuildList();
        // The fields as the list now has them ("136" becomes "136.000"): the answer's
        // read-back then finds nothing unsaved and shows the server's file.
        if (m_OzrPicked >= 0)
            OzrFill(m_OzrPicked);
    }

    // The strip's "yes" to dropping the unsaved work: the fields go back to the list,
    // the list to the server's file when it arrives.
    private void OzrReloadNow()
    {
        m_OzrDraft = false;
        if (m_OzrCfg && m_OzrPicked >= 0 && m_OzrPicked < m_OzrCfg.Radios.Count())
            OzrFill(m_OzrPicked);
        AskCfg(OZR_VppModule.CFG_PROFILES);
    }

    // ------------------------------------------------------------ шматки

    private string OzrTrimmed(string name)
    {
        string t = GetEdit(name);
        return t.Trim();
    }

    private void OzrSay(string name, string text, int ink)
    {
        TextWidget t = TextWidget.Cast(M_SUB_WIDGET.FindAnyWidget(name));
        if (!t)
            return;
        t.SetText(text);
        t.SetColor(ink);
    }

    private void OzrColor(string name, int color)
    {
        Widget w = M_SUB_WIDGET.FindAnyWidget(name);
        if (w)
            w.SetColor(color);
    }

    private void OzrShow(string name, bool show)
    {
        Widget w = M_SUB_WIDGET.FindAnyWidget(name);
        if (w)
            w.Show(show);
    }

    private void OzrSize(string name, float w, float h)
    {
        Widget x = M_SUB_WIDGET.FindAnyWidget(name);
        if (x)
            x.SetSize(w, h);
    }

    private void OzrMove(string name, float x, float y)
    {
        Widget m = M_SUB_WIDGET.FindAnyWidget(name);
        if (m)
            m.SetPos(x, y);
    }

    // ------------------------------------------------------------ розмір вікна

    // The window changed size: the page is now w x h pixels. The head and its rule span
    // it (the actions anchored to its right edge follow), the list takes the height and
    // the button and the note under it move with its foot. Nothing is read back
    // (dayz-modding gui-layouts §23a).
    override void OnWindowResized(float w, float h)
    {
        super.OnWindowResized(w, h);
        if (!M_SUB_WIDGET)
            return;

        float s = UnitScale();
        OzrSize("OzrHead", w, 60 * s);
        OzrSize("OzrHeadRule", w, s);
        OzrSize("OzrDivider", s, h - 60 * s);

        float listH = h - 234 * s;
        if (listH < 60 * s)
            listH = 60 * s;
        OzrSize("RadList", 472 * s, listH);
        OzrMove("BtnRadNew", 24 * s, listH + 110 * s);
        OzrMove("OzrRangeNote", 24 * s, listH + 150 * s);
    }

    // ------------------------------------------------------------ ввід

    override bool OnItemSelected(Widget w, int x, int y, int row, int column, int oldRow, int oldColumn)
    {
        if (w && M_SUB_WIDGET && w.GetName() == "RadList")
        {
            if (!m_OzrRepaint)
                OzrPick(row);
            return true;
        }
        return super.OnItemSelected(w, x, y, row, column, oldRow, oldColumn);
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (!w || !M_SUB_WIDGET)
            return super.OnClick(w, x, y, button);

        string nm = w.GetName();

        if (nm == "BtnRadNew")
        {
            OzrAskNew();
            return true;
        }
        if (nm == "BtnRadDel")
        {
            OzrAskDelete();
            return true;
        }
        if (nm == "BtnRadCheck")
        {
            OzrPaintGrid();
            OzrPaintChecks();
            return true;
        }
        if (nm == "BtnRadSave")
        {
            OzrAskSave();
            return true;
        }
        if (nm == "BtnRadReload")
        {
            if (OzrUnsaved())
            {
                Confirm("#STR_OZR_VPP_ASK_RELOAD", "#STR_OZR_VPP_YES_RELOAD", "ozr:reload");
                return true;
            }
            OzrReloadNow();
            return true;
        }

        return super.OnClick(w, x, y, button);
    }
}

#endif
#endif
#endif
