// The script colours of the radio's page in the OpenZone admin window: the window's
// metal (VPP rework 2026-11-12, design 2.3), the same values as the vpp* names of the
// core's tokens, which this repository's ui/tokens.json repeats for the page's
// description. The engine reads neither file: a vpp* value changed there is changed here
// too.

#ifdef AVPPAdminTools
#ifdef OpenZone_VPP
#ifndef NO_GUI

class OZR_VppMetal
{
    // --- text
    static const int TEXT   = 0xFFE0DFDA;   // vppText    0.88  0.875 0.855
    static const int MUTED  = 0xFFA09F99;   // vppMuted   0.627 0.624 0.6
    static const int FAINT  = 0xFF5C5A58;   // vppFaint   0.36  0.353 0.345

    // --- states
    static const int ALERT  = 0xFFF5C740;   // vppAlert   0.96  0.78  0.25
    static const int OK     = 0xFF66C75C;   // vppOk      0.4   0.78  0.36
    static const int BAD    = 0xFFE0524A;   // vppBad     0.88  0.32  0.29
}

#endif
#endif
#endif
