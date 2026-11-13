// Сторінка «Профілі рацій» модуля «Рація» в адмінському вікні OpenZone (VPP rework
// 2026-11-12, design 5.4): профілі ручних рацій списком і карткою вибраного. Чіпляється
// до вікна ядра через modded class -- ядро про рацію не знає й знати не мусить.
//
// The layout is converted from the mockup's board RadioProfiles.dc.html (css2layout,
// 2026-11-13; docs/specs/2026-11-13-openzone-vpp-page-guide.md): it carries its own
// colours and follows the window by itself. What this file names is in the report
// ui/css2layout/ozr_vpp_pane.txt; the list is rows made from the template
// ozr_vpp_profile_row.layout.
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
//      яким ефір СТАНЕ, ще до збереження -- і поки адмін набирає числа.
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
// Чернетка: «Новий профіль» і «Видалити профіль» міняють список на сторінці, поля --
// вибраний профіль; на сервер усе йде одним файлом кнопкою «Зберегти все», через смугу
// підтвердження вікна (design 3.4), як і видалення, і відкидання незбережених правок
// (D106: перейти на інший рядок, новий профіль, перечитати). «Так» вертається в
// OnConfirmed дією "ozr:". What the page says goes to the window's journal and its
// status bar (Hint).
//
// Члени цього шару починаються з Ozr (поля -- m_Ozr): той самий клас модифікує кожна
// склейка, і ім'я, яке мають двоє, не компілюється. Fields are declared bare and set in
// OnCreate (dayz-modding enforce-script.md, field initialisers).

#ifdef AVPPAdminTools
#ifdef OpenZone_VPP
#ifndef NO_GUI

modded class OZ_VppAdminMenu
{
    static const string OZR_PAGE = "radio.profiles";

    // Numbers of the converted layout, in layout units. The engine does not read the
    // board, so they live twice: convert the page again, check these against its layout.
    // A row of the list; the warning's two parts (where the first starts, their line's
    // top and height); a caption over a box's border (its room left and right of the
    // words, the height of its ground and of its line).
    static const float OZR_ROW_W     = 487;
    static const float OZR_ROW_H     = 42;
    static const float OZR_WARN_X    = 41;
    static const float OZR_WARN_Y    = 12;
    static const float OZR_WARN_H    = 17;
    static const float OZR_LEG_PAD   = 6;
    static const float OZR_LEG_BAR_H = 8;
    static const float OZR_LEG_H     = 15;

    // The list shows this many profiles; the journal says when the file holds more.
    static const int OZR_ROWS_MAX = 200;

    // How a check stands: nothing to check, passed, true only after the restart, failed.
    static const int OZR_CHECK_NONE = 0;
    static const int OZR_CHECK_OK   = 1;
    static const int OZR_CHECK_WAIT = 2;
    static const int OZR_CHECK_BAD  = 3;

    // The pane, as created.
    private Widget m_OzrPane;
    // The profiles as the page holds them: the server's file, with new and deleted ones
    // laid over it until Save all sends it.
    private ref OZR_Profiles m_OzrCfg;
    // The list's rows; a row's key is its profile's index in m_OzrCfg.Radios.
    private ref OZ_VppFlexRows m_OzrRows;
    // The picked profile: an index of m_OzrCfg.Radios, -1 for none.
    private int  m_OzrPicked;
    // A new or a deleted profile changed the list since the server's file.
    private bool m_OzrDraft;
    // The script writes the fields: an OnChange that comes of it is not typing.
    private bool m_OzrFill;
    // What is fitted to its words waits for the page to be on screen: frames left to try.
    private int  m_OzrFitTries;

    override void OnCreate(Widget RootW)
    {
        super.OnCreate(RootW);
        if (!M_SUB_WIDGET)
            return;

        m_OzrPicked = -1;
        m_OzrDraft = false;
        m_OzrFill = false;
        m_OzrFitTries = 0;

        m_OzrPane = OZ_VppFlex.Create("OpenZone_Radio_VPP/gui/layouts/ozr_vpp_pane.layout", M_SUB_WIDGET, "OzrPane");
        if (!m_OzrPane)
        {
            OZR_Log.Error("radio vpp page: layout failed to load");
            return;
        }

        // No hint label of its own: the page's lines go to the journal, and the status
        // bar shows the newest.
        RegisterPage("radio", "#STR_OZR_VPP_MOD", OZR_PAGE, "#STR_OZR_VPP_PAGE_PROFILES", m_OzrPane, "");

        Widget host = m_OzrPane.FindAnyWidget("OzrListRows");
        if (host)
            m_OzrRows = new OZ_VppFlexRows(m_Flex, host, "OpenZone_Radio_VPP/gui/layouts/ozr_vpp_profile_row.layout", "OZR_VppProfileRow", OZR_ROW_W, OZR_ROW_H);
        else
            OZR_Log.Error("radio vpp page: the list has no OzrListRows");

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
        m_OzrFitTries = 30;
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

    // Every frame while the window is open: what waits to be fitted to its words.
    override void Tick()
    {
        super.Tick();
        if (m_OzrFitTries > 0)
            OzrFitTick();
    }

    // The captions over the boxes' borders and the warning's two parts are as wide as
    // their words in the game's language. A text measures only once it is on screen, so
    // the page is tried for a few frames after it is shown.
    private void OzrFitTick()
    {
        m_OzrFitTries = m_OzrFitTries - 1;
        if (m_Shown != OZR_PAGE)
        {
            m_OzrFitTries = 0;
            return;
        }

        bool done = true;
        if (!OzrFitLegend("OzrLegProfile"))
            done = false;
        if (!OzrFitLegend("OzrLegEther"))
            done = false;
        if (!OzrFitLegend("OzrLegCheck"))
            done = false;
        if (!OzrFlowWarn())
            done = false;

        if (done)
            m_OzrFitTries = 0;
    }

    // One caption over a border: its ground (<name>Bar hides the border under the words)
    // and its line (<name>Text) as wide as the words. False: the words do not measure yet.
    private bool OzrFitLegend(string name)
    {
        if (!m_OzrPane)
            return true;
        Widget bar = m_OzrPane.FindAnyWidget(name + "Bar");
        TextWidget t = TextWidget.Cast(m_OzrPane.FindAnyWidget(name + "Text"));
        if (!bar || !t)
            return true;

        int tw = OZ_VppFlex.TextWidth(t);
        if (tw <= 0)
            return false;

        float s = UnitScale();
        bar.SetSize(tw + 2 * OZR_LEG_PAD * s, OZR_LEG_BAR_H * s);
        t.SetSize(tw + 2, OZR_LEG_H * s);
        return true;
    }

    // The warning is two captions, the first in bold: the second begins a word's gap
    // after the first ends, whatever the language. False: the words do not measure yet.
    private bool OzrFlowWarn()
    {
        if (!m_OzrPane)
            return true;
        TextWidget first = TextWidget.Cast(m_OzrPane.FindAnyWidget("OzrWarnA"));
        TextWidget second = TextWidget.Cast(m_OzrPane.FindAnyWidget("OzrWarnB"));
        if (!first || !second)
            return true;
        if (!first.IsVisibleHierarchy())
            return true;

        int firstW = OZ_VppFlex.TextWidth(first);
        int secondW = OZ_VppFlex.TextWidth(second);
        if (firstW <= 0 || secondW <= 0)
            return false;

        float s = UnitScale();
        first.SetSize(firstW + 2, OZR_WARN_H * s);
        second.SetPos(OZR_WARN_X * s + firstW + 4 * s, OZR_WARN_Y * s);
        second.SetSize(secondW + 2, OZR_WARN_H * s);
        return true;
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

    // ------------------------------------------------------------ числа

    // A number as the page shows it: OZR_Fmt's, less the zeros at its end past the second
    // place ("136.000" is "136.00", "0.0500" is "0.05", "0.0125" stays). Nothing is
    // rounded: the fields take the same words back.
    private string OzrShort(string num)
    {
        int dot = num.IndexOf(".");
        if (dot < 0)
            return num;
        int n = num.Length();
        while (n > dot + 3 && num.Substring(n - 1, 1) == "0")
            n = n - 1;
        return num.Substring(0, n);
    }

    private string OzrMHz(float mhz)
    {
        return OzrShort(OZR_Fmt.MHz(mhz));
    }

    private string OzrStepText(float mhz)
    {
        return OzrShort(OZR_Fmt.Step(mhz));
    }

    // ------------------------------------------------------------ сітка

    // "136.00–155.95 МГц, крок 0.05, 400 поділок" -- in the admin's language.
    private string OzrGridText(float baseMHz, float step, int count)
    {
        if (count < 1)
            return "-";

        string mhz = Widget.TranslateString("#STR_OZR_VPP_MHZ");
        string stepWord = Widget.TranslateString("#STR_OZR_VPP_STEP_WORD");
        string divs = Widget.TranslateString("#STR_OZR_VPP_DIVISIONS");
        float top = baseMHz + (count - 1) * step;

        string text = OzrMHz(baseMHz) + "–" + OzrMHz(top);
        text = text + " " + mhz + ", " + stepWord;
        text = text + " " + OzrStepText(step) + ", ";
        text = text + count.ToString() + " " + divs;
        return text;
    }

    // The ether now: what the server sent with the core's sync packet.
    private void OzrPaintGrid()
    {
        if (!OZR_ClientGrid.Ready())
        {
            OzrSay("RadGrid", "#STR_OZR_VPP_NO_GRID", ARGB(255, 160, 159, 153));
            return;
        }
        string now = OzrGridText(OZR_ClientGrid.BaseMHz(), OZR_ClientGrid.StepMHz(), OZR_ClientGrid.Count());
        OzrSay("RadGrid", now, ARGB(255, 224, 223, 218));
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

    // The second line of the ether box, and under it the warning while the ether after
    // a restart is another than the one that runs.
    private void OzrPaintEther()
    {
        OZR_EtherPlan plan = OzrPlanned();
        bool warn = false;
        int ink = ARGB(255, 160, 159, 153);
        if (plan && !plan.Ok)
            ink = ARGB(255, 224, 82, 74);
        else if (plan && OzrSameAsRunning(plan))
            ink = ARGB(255, 102, 199, 92);
        else if (plan)
        {
            ink = ARGB(255, 245, 199, 64);
            warn = true;
        }
        string afterText = OzrPlanText(plan);
        OzrSay("RadEther", afterText, ink);
        OzrShow("OzrWarn", warn);
        if (warn && !OzrFlowWarn())
            m_OzrFitTries = 30;
    }

    // ------------------------------------------------------------ список

    // A row per profile: its class, its band and step, the range its item's config gives.
    private void OzrRebuildList()
    {
        if (!m_OzrRows || !m_OzrCfg)
            return;

        int cInk = ARGB(255, 224, 223, 218);
        int cMuted = ARGB(255, 160, 159, 153);

        m_OzrRows.Clear();
        Widget row;
        OZR_RadioProfile p;
        string band;
        int total = m_OzrCfg.Radios.Count();
        for (int i = 0; i < total && i < OZR_ROWS_MAX; i++)
        {
            p = m_OzrCfg.Radios[i];
            row = m_OzrRows.Add(i.ToString());
            if (!row)
                continue;
            band = OzrMHz(p.MinMHz) + "–" + OzrMHz(p.MaxMHz);
            band = band + " / " + OzrStepText(p.StepMHz);
            OzrRowText(row, "OzrRowCls", OzrRowName(p), cInk);
            OzrRowText(row, "OzrRowBand", band, cInk);
            OzrRowText(row, "OzrRowRange", OzrRangeOf(p.ClassName), cMuted);
        }
        m_OzrRows.Fit();
        OzrMarkRows();

        int most = OZR_ROWS_MAX;
        if (total > most && CurrentPane() == OZR_PAGE)
        {
            string cutWord = Widget.TranslateString("#STR_OZR_VPP_H_CUT");
            string cut = cutWord + " " + most.ToString();
            cut = cut + " / " + total.ToString();
            Hint(cut);
        }
    }

    // The picked profile's row is lit (the accent's frame and soft ground, as the
    // template carries them); the others lie on the list's plain ground.
    private void OzrMarkRows()
    {
        if (!m_OzrRows)
            return;

        int cAccent = ARGB(255, 232, 120, 43);
        int cPicked = ARGB(255, 47, 29, 17);
        int cHead = ARGB(255, 19, 19, 18);

        string pick = "";
        if (m_OzrCfg && m_OzrPicked >= 0 && m_OzrPicked < m_OzrCfg.Radios.Count())
            pick = m_OzrPicked.ToString();

        Widget row;
        for (int i = 0; i < m_OzrRows.Count(); i++)
        {
            row = m_OzrRows.Row(i);
            if (!row)
                continue;
            if (pick != "" && m_OzrRows.Key(i) == pick)
            {
                OZ_VppFlex.Paint(row, "OZR_VppProfileRowEdge", cAccent);
                OZ_VppFlex.Paint(row, "OZR_VppProfileRowBg", cPicked);
            }
            else
            {
                OZ_VppFlex.Paint(row, "OZR_VppProfileRowEdge", cHead);
                OZ_VppFlex.Paint(row, "OZR_VppProfileRowBg", cHead);
            }
        }
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
        if (OzrTrimmed("RadF_Min") != OzrMHz(p.MinMHz))
            return true;
        if (OzrTrimmed("RadF_Max") != OzrMHz(p.MaxMHz))
            return true;
        string step = OzrStepText(p.StepMHz);
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
    // first, and the list keeps its light on the profile being edited meanwhile.
    private void OzrPick(int row)
    {
        if (!m_OzrCfg || row < 0 || row >= m_OzrCfg.Radios.Count() || row == m_OzrPicked)
            return;

        if (OzrDirty())
        {
            string text = OzrDropQuestion();
            Confirm(text, "#STR_OZR_VPP_YES_DROP", "ozr:switch:" + row.ToString());
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
        m_OzrFill = true;
        SetEdit("RadF_Class", p.ClassName);
        SetEdit("RadF_Min",   OzrMHz(p.MinMHz));
        SetEdit("RadF_Max",   OzrMHz(p.MaxMHz));
        SetEdit("RadF_Step",  OzrStepText(p.StepMHz));
        m_OzrFill = false;
        OzrMarkRows();
        OzrPaintCard();
    }

    private void OzrClearForm()
    {
        m_OzrPicked = -1;
        m_OzrFill = true;
        SetEdit("RadF_Class", "");
        SetEdit("RadF_Min",   "");
        SetEdit("RadF_Max",   "");
        SetEdit("RadF_Step",  "");
        m_OzrFill = false;
        OzrMarkRows();
        OzrPaintCard();
    }

    // ------------------------------------------------------------ картка

    private void OzrPaintCard()
    {
        if (!m_OzrPane)
            return;

        bool picked = false;
        if (m_OzrCfg && m_OzrPicked >= 0 && m_OzrPicked < m_OzrCfg.Radios.Count())
            picked = true;

        if (picked)
        {
            string title = OzrRowName(m_OzrCfg.Radios[m_OzrPicked]);
            OzrSay("OzrCardTitle", title, ARGB(255, 224, 223, 218));
        }
        else
            OzrSay("OzrCardTitle", "#STR_OZR_VPP_PICK", ARGB(255, 160, 159, 153));
        OzrShow("BtnRadDel", picked);

        OzrPaintGrid();
        OzrPaintChecks();
    }

    // The range from the class's config, not a copy in JSON: a copy would part from the
    // engine, and a difference in THIS number shows nowhere -- the radio just does not
    // reach as far as the page says.
    private void OzrPaintRange(string cls)
    {
        int cInk = ARGB(255, 224, 223, 218);
        int cMuted = ARGB(255, 160, 159, 153);
        int cAlert = ARGB(255, 245, 199, 64);

        if (cls == "")
        {
            OzrSay("RadF_Range", "-", cMuted);
            OzrSay("OzrRangeH", "#STR_OZR_VPP_F_RANGE_HINT", cMuted);
            return;
        }
        string range = OzrRangeOf(cls);
        if (range == "?")
        {
            OzrSay("RadF_Range", "?", cAlert);
            OzrSay("OzrRangeH", "#STR_OZR_VPP_NO_RANGE", cAlert);
            return;
        }
        OzrSay("RadF_Range", range, cInk);
        OzrSay("OzrRangeH", "#STR_OZR_VPP_F_RANGE_HINT", cMuted);
    }

    // One line of the checks and the sign before it: a check mark, a ring for what is
    // true only after the restart, a cross, a faint dot when there is nothing to check;
    // an empty line has no sign.
    private void OzrCheck(int i, string text, int state)
    {
        string name = "RadF_Fit2";
        if (i == 0)
            name = "RadF_Chan";
        else if (i == 1)
            name = "RadF_Fit1";

        int ink = ARGB(255, 224, 223, 218);
        int tint = ARGB(255, 102, 199, 92);
        string image = "check";
        if (state == OZR_CHECK_NONE)
        {
            ink = ARGB(255, 160, 159, 153);
            tint = ARGB(255, 92, 90, 88);
            image = "dot";
        }
        else if (state == OZR_CHECK_WAIT)
        {
            tint = ARGB(255, 245, 199, 64);
            image = "ring";
        }
        else if (state == OZR_CHECK_BAD)
        {
            tint = ARGB(255, 224, 82, 74);
            image = "cross";
        }
        OzrSay(name, text, ink);

        if (!m_OzrPane)
            return;
        ImageWidget sign = ImageWidget.Cast(m_OzrPane.FindAnyWidget("OzrDot" + i.ToString()));
        if (!sign)
            return;
        sign.Show(text != "");
        sign.LoadImageFile(0, "set:ozv_ui image:" + image);
        sign.SetImage(0);
        sign.SetColor(tint);
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
            OzrCheck(0, "-", OZR_CHECK_NONE);
            OzrCheck(1, "#STR_OZR_VPP_EMPTY_FORM", OZR_CHECK_NONE);
            OzrCheck(2, "", OZR_CHECK_NONE);
            return;
        }
        if (hi <= lo)
        {
            OzrCheck(0, "-", OZR_CHECK_BAD);
            OzrCheck(1, "#STR_OZR_VPP_HI_LO", OZR_CHECK_BAD);
            OzrCheck(2, "", OZR_CHECK_NONE);
            return;
        }

        // The whole ether is refused: there is no grid to count this profile's channels in.
        OZR_EtherPlan plan = OzrPlanned();
        if (!plan || !plan.Ok)
        {
            OzrCheck(0, "-", OZR_CHECK_BAD);
            OzrCheck(1, "#STR_OZR_VPP_NO_PLAN", OZR_CHECK_BAD);
            OzrCheck(2, "", OZR_CHECK_NONE);
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
        chan = chan + " " + fromWord;
        chan = chan + " " + OzrMHz(lo);
        chan = chan + " " + toWord;
        chan = chan + " " + OzrMHz(hi);
        OzrCheck(0, chan, OZR_CHECK_OK);

        string strideWord = Widget.TranslateString("#STR_OZR_VPP_STRIDE");
        string etherStep = Widget.TranslateString("#STR_OZR_VPP_ETHER_STEP");
        string every = strideWord + " " + stride.ToString();
        every = every + " × " + etherStep;
        OzrCheck(1, every, OZR_CHECK_OK);

        // The one question that can still be answered "no": whether the profile works
        // NOW or only after the restart. The ether follows it either way, not this second.
        string nowWord = Widget.TranslateString("#STR_OZR_VPP_NOW");
        if (!OZR_ClientGrid.Ready())
        {
            string noGrid = Widget.TranslateString("#STR_OZR_VPP_NO_GRID");
            OzrCheck(2, nowWord + " " + noGrid, OZR_CHECK_NONE);
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
            notNow = notNow + " " + OzrMHz(cLo);
            notNow = notNow + "–" + OzrMHz(cHi);
            OzrCheck(2, notNow, OZR_CHECK_WAIT);
            return;
        }

        string yesWord = Widget.TranslateString("#STR_OZR_VPP_NOW_YES");
        OzrCheck(2, nowWord + " " + yesWord, OZR_CHECK_OK);
    }

    // ------------------------------------------------------------ правки

    private void OzrAskNew()
    {
        if (!m_OzrCfg)
        {
            Hint("#STR_OZR_VPP_H_NOT_LOADED");
            return;
        }

        // A new profile changes the picked one too: unsaved edits are named first (D106).
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
        // The fields as the list now has them ("136" becomes "136.00"): the answer's
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

    // A text of the page by its name: its words and its colour.
    private void OzrSay(string name, string text, int ink)
    {
        if (!m_OzrPane)
            return;
        TextWidget t = TextWidget.Cast(m_OzrPane.FindAnyWidget(name));
        if (!t)
            return;
        t.SetText(text);
        t.SetColor(ink);
    }

    // A text of a list's row.
    private void OzrRowText(Widget row, string name, string text, int ink)
    {
        TextWidget t = TextWidget.Cast(row.FindAnyWidget(name));
        if (!t)
            return;
        t.SetText(text);
        t.SetColor(ink);
    }

    private void OzrShow(string name, bool show)
    {
        if (!m_OzrPane)
            return;
        Widget w = m_OzrPane.FindAnyWidget(name);
        if (w)
            w.Show(show);
    }

    // ------------------------------------------------------------ розмір вікна

    // The window changed size: the page follows by the rule its layout carries; the
    // list's rows are made as wide as the list again.
    override void OnWindowResized(float w, float h)
    {
        super.OnWindowResized(w, h);
        if (m_OzrRows)
            m_OzrRows.Fit();
    }

    // ------------------------------------------------------------ ввід

    // Typing in a field of the card: the checks and the ether after a restart follow it.
    override bool OnChange(Widget w, int x, int y, bool finished)
    {
        if (w && M_SUB_WIDGET && !m_OzrFill)
        {
            string nm = w.GetName();
            if (nm.IndexOf("RadF_") == 0)
            {
                OzrPaintChecks();
                return true;
            }
        }
        return super.OnChange(w, x, y, finished);
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

        // A row of the list: its profile on the card.
        if (m_OzrRows)
        {
            int listRow = m_OzrRows.IndexOf(w);
            if (listRow != -1)
            {
                OzrPick(m_OzrRows.Key(listRow).ToInt());
                return true;
            }
        }

        return super.OnClick(w, x, y, button);
    }
}

#endif
#endif
#endif
