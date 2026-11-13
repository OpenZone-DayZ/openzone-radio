// The radio page's class field in the window's live class search (the core's OZ_ClassPick,
// design docs/specs/2026-11-13-openzone-vpp-class-search-design.md in the series' docs).

#ifdef AVPPAdminTools
#ifdef OpenZone_VPP
#ifndef NO_GUI

modded class OZ_VppAdminMenu
{
    override void ClassFields(OZ_ClassPick pick)
    {
        super.ClassFields(pick);
        // The radio a profile is for.
        pick.Bind("RadF_Class", OZ_ClassIndex.ITEM);
    }
}

#endif
#endif
#endif
