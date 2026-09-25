// The frequency window with the face of the radio.
//
// K opens one window for every radio: OZR_FreqMenu (OZR_FreqMenu.c) with a shared keypad.
// This file gives that same window the face of the radio in hands: its own layout
// (gui/layouts/oz_face_<s>.layout, written by models/tools/make_hud_layouts.py), the frequency
// on the radio's own screen, the keys on the case. The face pictures are gui/faces/oz_face_<s>.edds.
//
// A separate file and a modded class rather than an edit of OZR_FreqMenu.c: a window without a
// face (a class without ozrFaceLayout) stays exactly what it was, and everything about faces
// lives in one place. In Enforce a modded class sees both the private fields and the private
// methods of the original (DayZ wiki, Enforce Script Syntax, "Modded private members"). The file
// MUST compile AFTER OZR_FreqMenu.c: inside a folder the order is alphabetical, and the name
// OZR_FreqMenuFace.c sorts after it; do not rename it to anything that would sort earlier.
// Typing, the band check and the request to the server stay the window's own: the layout's keys
// carry the names of its buttons - Btn0..Btn9, BtnUp, BtnDown, BtnGo, BtnDot, BtnClose, DragBar.
// What is added here:
//   - BtnBack: erase a digit, and when there is nothing to erase - leave (EXIT on the Baofeng,
//     CLR on the PRC);
//   - a radio without digits (ozrFaceMode = "step"): an arrow switches the channel AT ONCE, the
//     window stays open;
//   - auto-dot: once the integer part can grow no further within the band, the dot follows;
//   - two screen rows: on a radio with digits the current frequency on top and the typed one
//     below; on a radio without digits the channel number large and the frequency small.
//
// Which face a class has is in its config: ozrFaceLayout, ozrFaceMode, ozrFaceHint. A class
// without ozrFaceLayout gets the plain window as it was.

modded class OZR_FreqMenu
{
    protected bool       m_OZR_Face;
    protected bool       m_OZR_Step;
    protected string     m_OZR_Hint;
    protected TextWidget m_OZR_Main;
    protected TextWidget m_OZR_Sub;

    // A step sent to the server and not back yet. Two quick presses would otherwise both count
    // from the same old channel and land on one channel instead of two. It never reaches the
    // screen: the screen, like the plain window's, shows only what is confirmed.
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
            // The face did not build; the plain window beats none.
            OZR_Log.Error("face keypad: " + layout + " produced no widgets, falling back to the stock keypad");
            return super.Init();
        }

        m_OZR_Face = true;
        m_OZR_Step = mode == "step";
        m_Card  = layoutRoot;
        m_Title = TextWidget.Cast(layoutRoot.FindAnyWidget("TitleText"));
        m_Hint  = TextWidget.Cast(layoutRoot.FindAnyWidget("HintText"));
        // The face has neither the plain window's display nor its band bar: the screen is drawn
        // by Paint below, and nobody must overwrite its rows.
        m_Freq = null;
        m_Band = null;
        m_OZR_Main = TextWidget.Cast(layoutRoot.FindAnyWidget("LcdMain"));
        m_OZR_Sub  = TextWidget.Cast(layoutRoot.FindAnyWidget("LcdSub"));

        OZR_Load("Face", image);

        OZR_Log.Dbg("face keypad: " + layout + " (" + mode + ")");
        return layoutRoot;
    }

    // The picture goes into the ImageWidget from script, not only from the layout's image0: that
    // way the path comes from the class config, and a miss shows in the log instead of as a
    // blank on screen.
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

    // The radio in hands: the same check as Grab(), but Init runs before OnShow.
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

        // The plain window's hint says to press TUNE, but this radio has an enter key of its
        // own. The refusal ("out of band") stays the window's.
        if (m_Hint)
        {
            if (m_HintKey == "#STR_OZR_KEYPAD_HINT" && m_OZR_Hint != "")
                m_Hint.SetText(m_OZR_Hint);
            else
                m_Hint.SetText(m_HintKey);
        }
    }

    // The channel number within the radio's own band, counted from one. Empty until the band
    // is known.
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

        // Auto-dot: the dot appears by itself only once the integer part can grow no further -
        // with one more digit it would surely pass the top of this radio's band. The band can be
        // anything (two-, three- or four-digit frequencies), so the rule is the bound itself, not
        // a digit count: with 136-156 after "136" (1360 > 156), with 80-1200 after "850", while
        // "85" is ambiguous there (85.125 or 850) - the player puts the dot, and every radio with
        // digits has a dot key.
        if (name.Length() == 4 && name.Substring(0, 3) == "Btn" && !m_Dialled && m_Profile)
        {
            if (m_Typed != "" && m_Typed.IndexOf(".") < 0 && OZR_IntComplete())
                m_Typed = m_Typed + ".";
        }

        return super.OnClick(w, x, y, button);
    }

    // The integer part is complete: appending any digit would pass the top of the band.
    protected bool OZR_IntComplete()
    {
        int top = m_Profile.MaxMHz;
        int typed = m_Typed.ToInt();
        return typed * 10 > top;
    }

    // Step to the neighbouring channel AT ONCE, without TUNE: a radio without digits has nothing
    // to type, and a confirmation per step would be one press too many. The window stays open,
    // so steps can follow one another.
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
