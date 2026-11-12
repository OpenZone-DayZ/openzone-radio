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
    static const int TEXT   = ARGB(255, 224, 223, 218);   // vppText    0.88  0.875 0.855
    static const int MUTED  = ARGB(255, 160, 159, 153);   // vppMuted   0.627 0.624 0.6
    static const int FAINT  = ARGB(255,  92,  90,  88);   // vppFaint   0.36  0.353 0.345

    // --- states
    static const int ALERT  = ARGB(255, 245, 199,  64);   // vppAlert   0.96  0.78  0.25
    static const int OK     = ARGB(255, 102, 199,  92);   // vppOk      0.4   0.78  0.36
    static const int BAD    = ARGB(255, 224,  82,  74);   // vppBad     0.88  0.32  0.29
}

#endif
#endif
#endif
