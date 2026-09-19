// How this mod presents itself in the launcher and the in-game mod list.
//
// Without this file DayZ shows the folder name -- "@OpenZone_Radio" -- and
// nothing else: no author, no version, no description. That is acceptable on
// a private stand and not acceptable on the Workshop, where the mod list is
// the only place a server owner looks before deciding to trust it.
//
// The picture and logo paths are left out deliberately rather than pointed at
// files that do not exist: DayZ draws a blank for a missing texture and says
// nothing, so a wrong path is worse than none. Add them here when art exists.

name        = "OpenZone Radio";
author      = "Zone Protocol";
authorID    = "";
version     = "0.1";

// SAY THE DEPENDENCY OUT LOUD, because the Workshop cannot carry it.
//
// The eight-frequency limit lives in the game executable, so widening the band
// needs a native library, and a DLL is not something the Workshop hosts. A
// server owner who installs this and sees eight channels must be able to find
// out why WITHOUT reading the log first -- so the answer is here too.
description = "Radio channels beyond the vanilla eight. Requires Community Framework and OpenZone Core. Needs a server-side native library from the repository to widen the band -- without it the mod runs and leaves the vanilla eight alone. github.com/covalschi/openzone-radio";

tooltip     = "OpenZone Radio";
overview    = "DayZ ships with eight radio frequencies. This makes it as many as you configure. Any server, any map, configured from JSON. Requires OpenZone Core. Widening the band needs a server-side native library from the repository; clients need nothing.";
