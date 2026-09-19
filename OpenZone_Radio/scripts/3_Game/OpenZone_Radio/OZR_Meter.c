// Counters for the lag debug mode.
//
// WHAT THIS IS FOR. When a server stalls with many players on it, the
// question is never "how expensive is one call" -- that can be measured on an
// empty stand -- but "how many times per minute does it fire with sixty people
// online", which cannot. These counters answer the second question on the
// live server, in one log line a minute, and cost one static bool read per
// hooked call while switched off.
//
// WHY NOT THE ENGINE'S OWN EnProfiler. It only exists in the Diag build: the
// retail DayZServer_x64.exe carries none of its bindings (checked against the
// binary 2026-09-12), so a debug mode built on it would be dead on every real
// server.
//
// Switched on by `Profiler` in OZ_Radio_Settings.json (OZR_Settings.ServerLoad
// is the only caller of SetOn). Everything here is server-side bookkeeping;
// the client never sees it.
class OZR_Meter
{
    // What is counted. Order is the order in the report.
    static const int EEINIT   = 0;   // a radio entity created on the server
    static const int STORE    = 1;   // a radio loaded from storage
    static const int WORK_ON  = 2;   // a radio powered up
    static const int WORK_OFF = 3;   // a radio powered down
    static const int SPEAK    = 4;   // OZR_SetSpeaking: an EnableBroadcast edge
    static const int KNOB     = 5;   // vanilla SetNextFrequency (the tune action)
    static const int TUNE     = 6;   // a keypad tune request (the core's service pair)
    static const int PTT      = 7;   // a PTT edge from a client (the same pair)
    static const int COUNT    = 8;

    private static bool s_On = false;

    // Counts and accumulated milliseconds since the last report. Fixed-size
    // arrays sized at first use, so switching the meter on costs one
    // allocation per run and the hooks allocate nothing.
    private static ref array<int> s_Hits;
    private static ref array<int> s_Ms;
    private static int s_Since = 0;

    static void SetOn(bool on)
    {
        s_On = on;
        if (!on)
            return;

        if (!s_Hits)
        {
            s_Hits = new array<int>();
            s_Ms   = new array<int>();
            for (int i = 0; i < COUNT; i++)
            {
                s_Hits.Insert(0);
                s_Ms.Insert(0);
            }
        }
        s_Since = GetGame().GetTime();
    }

    static bool On()
    {
        return s_On;
    }

    // Count one occurrence. The first line is the whole cost while the meter
    // is off.
    static void Hit(int what)
    {
        if (!s_On)
            return;
        s_Hits.Set(what, s_Hits[what] + 1);
    }

    // For paths worth timing end to end: `int t = Begin();` at the top,
    // `End(what, t)` before every return. Zero when off, so End() can tell a
    // call that began while the meter was off from one that took no time.
    static int Begin()
    {
        if (!s_On)
            return 0;
        return GetGame().GetTime();
    }

    static void End(int what, int began)
    {
        if (!s_On || began == 0)
            return;
        s_Hits.Set(what, s_Hits[what] + 1);
        s_Ms.Set(what, s_Ms[what] + GetGame().GetTime() - began);
    }

    // One line, then the window starts over. Counters that stayed at zero are
    // left out: the line exists to be read at a glance, and forty zeros are
    // noise.
    static string Report(int players)
    {
        int now = GetGame().GetTime();
        int span = (now - s_Since) / 1000;
        s_Since = now;

        string line = "meter: " + span.ToString() + "s players=" + players.ToString();

        for (int i = 0; i < COUNT; i++)
        {
            int n = s_Hits[i];
            if (n == 0)
                continue;

            line += " | " + Name(i) + " " + n.ToString();
            if (s_Ms[i] > 0)
                line += " (" + s_Ms[i].ToString() + " ms)";

            s_Hits.Set(i, 0);
            s_Ms.Set(i, 0);
        }
        return line;
    }

    private static string Name(int what)
    {
        switch (what)
        {
            case EEINIT:   return "eeinit";
            case STORE:    return "store";
            case WORK_ON:  return "power-on";
            case WORK_OFF: return "power-off";
            case SPEAK:    return "air";
            case KNOB:     return "knob";
            case TUNE:     return "tune-req";
            case PTT:      return "ptt";
        }
        return "?";
    }
}
