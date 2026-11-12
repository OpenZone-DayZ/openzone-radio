// The radio's card on Ядро › Огляд (the core's OZ_AdminFacts, VPP rework 2026-11-12,
// design 4.3): the profiles, the channels they make (the ether derived from them, the
// grid the server writes for its next start), the ether the engine runs now; the
// problems the last load found in the profiles and the settings.
//
// "Reload every module" reads both files again as the start does -- the radio's loader
// writes a file only when it is missing or older -- then derives the ether and writes the
// grid file for the next start, as an apply from the window does, and sends the profiles
// to everyone online. The ether itself changes with the next start of the server
// PROCESS: the native patch reads the grid file then, and the card says so.
//
// Registered at the server mission start of OZR_Module, after the files are read. The
// radio has required the core since 2026-09-20, so the core's registry is there.
class OZR_Facts : OZ_AdminFactsProvider
{
    override void Fill(OZ_AdminModuleCard card)
    {
        card.Id = "radio";
        card.Name = "#STR_OZR_VPP_MOD";

        // Pages in the window come with this repository's VPP glue.
        card.Pages = 0;
#ifdef OpenZone_Radio_VPP
        card.Pages = 1;
#endif

        int found = OZR_CfgProblems.Of("RadioProfiles");
        found += OZR_CfgProblems.Of("Radio");
        card.Problems = found;

        OZR_Profiles cfg = OZR_Profiles.Get();
        int profiles = 0;
        if (cfg && cfg.Radios)
            profiles = cfg.Radios.Count();
        card.Add("#STR_OZR_FACT_PROFILES", profiles.ToString());

        string channels = "#STR_OZR_FACT_REFUSED";
        if (cfg)
        {
            array<ref OZR_RadioProfile> radios = cfg.Radios;
            OZR_EtherPlan plan = OZR_Ether.Derive(radios);
            if (plan.Ok)
                channels = plan.Count.ToString();
        }
        card.Add("#STR_OZR_FACT_CHANNELS", channels);

        string ether = "#STR_OZR_FACT_UNEVEN";
        if (OZR_Grid.Ready())
            ether = OZR_Grid.Count().ToString();
        card.Add("#STR_OZR_FACT_ETHER", ether);
    }

    override bool Reload(array<string> said)
    {
        OZR_Settings.ServerLoad();
#ifdef OpenZone_Radio_PDA
        // The family's one switch: with the radio's PDA glue loaded the core decides the
        // level (OZRP_Module.OnMissionStart); the radio's own setting decides it alone.
        OZR_Log.SetDebug(OZ_Log.IsDebug());
#endif

        OZR_Profiles.ServerLoad();
        OZR_EtherServer.Publish(OZR_Profiles.Get());
        OZR_EtherServer.Broadcast();

        if (!OZR_EtherServer.Matches())
            said.Insert("#STR_OZR_FACT_RESTART");
        return true;
    }
}
