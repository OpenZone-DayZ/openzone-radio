// OpenZone Radio -- the band system.
//
// WHAT THIS PBO IS. The ether: how many channels exist, where they sit, who
// hears whom, and push-to-talk.
//
// WHAT IT IS NOT. The PDA board. The radio as a MODULE in a device bay lives
// in @OpenZone_Radio_PDA, a separate pbo in this same repository, and that one
// does require the PDA. The admin tab is the same story: @OpenZone_Radio_VPP.
//
// IT RUNS ON THE CORE (2026-09-20; the series' note
// docs/specs/2026-09-20-radio-on-core-transport-design.md). Until then this
// header said the mod "stands on its own" and booted against @CF alone --
// true, and paid for with a second transport: seven CF RPCs of its own, a
// client-side pull loop and a throttle, next to the core's envelope the glue
// already used. The ether now rides the core's sync packet and tuning and
// push-to-talk go through the core's service pair, so OpenZone_Core is a hard
// dependency here, as everywhere else in the series.

class CfgPatches
{
    class OpenZone_Radio
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        // Hard dependencies, and hard means a blocking window before the game
        // loads rather than a silent skip. The core is one of them since
        // 2026-09-20 (see the header). What knows about the PDA lives in
        // @OpenZone_Radio_PDA and what knows about VPP in @OpenZone_Radio_VPP:
        // separate pbos of this repository that require both sides hard and
        // are installed only when both run.
        //
        // CF stays: the module is a CF_ModuleWorld, and the core's envelope
        // rides CF's RPCManager.
        requiredAddons[] =
        {
            "DZ_Data",
            "DZ_Scripts",
            "JM_CF_Scripts",
            "OpenZone_Core",
            // Ним оголошений personalradio_staticnoise_SoundShader, від якого
            // успадковується наш сплеск. Без цього рядка базовий клас при
            // бінаризації просто не знайдеться -- і не мовчки: конфіг не
            // збереться. Це четверта ЖОРСТКА залежність, і вона нічого не
            // коштує: pbo ванільний, він є на кожному сервері.
            "DZ_Sounds_Effects"
        };
    };
};

class CfgMods
{
    class OpenZone_Radio
    {
        dir        = "OpenZone_Radio";
        name       = "OpenZone Radio";
        credits    = "Zone Protocol";
        author     = "Zone Protocol";
        type       = "mod";

        dependencies[] = {"Game", "World", "Mission"};

        // The frequency keypad's key. A mod gets exactly one inputs file --
        // a second is not read -- so everything this mod binds goes in here.
        inputs = "OpenZone_Radio/data/inputs.xml";

        class defs
        {
            class gameScriptModule
            {
                value = "";
                files[] = {"OpenZone_Radio/scripts/3_Game"};
            };
            class worldScriptModule
            {
                value = "";
                files[] = {"OpenZone_Radio/scripts/4_World"};
            };
            class missionScriptModule
            {
                value = "";
                files[] = {"OpenZone_Radio/scripts/5_Mission"};
            };
        };
    };
};

// Звук сплеску -- власний набір на власному семплі.
//
// Спершу він грав ванільний personalradio_staticnoise: той уже є в грі, і мод
// лишався без жодного аудіофайла. Ціна виявилась зависокою. Той семпл -- шип
// увімкненої рації (volume = 0.0501, range = 13 у ванільному шейдері), він
// створений щоб НЕ помічатись, і навіть піднятий усемеро звучав як шум, а не
// як клац передавача. Власник приніс справжній семпл рації, і це правильне
// рішення: сплеск -- подія, а не фон.
//
// Семпл: моно, 48 кГц, 0.28 с. Моно навмисне -- набір просторовий
// (spatial = 1 у baseCharacter_SoundSet), а стерео в тривимірній сцені не
// позиціонується.
//
// loop = 0, і це головна відмінність від попередньої версії: ванільний шип
// зациклений, і його доводилось обривати таймером на 140 мс. Справжній
// сплеск має власну довжину, тож обривати нічого -- рушій сам зупинить і
// прибере (SetAutodestroy у PlaySoundSet).
//
// РАДІУС ЛІСЕНКОЮ, а не одним числом, і це вибір між двома звуковими API
// гри, а не лінощі.
//
// У DayZ їх два, і вони дають РІЗНЕ. Набори (CfgSoundSets) дозволяють міняти
// гучність на льоту -- EffectSound.SetSoundVolume, -- але радіус у них
// заданий шейдером і після створення не рухається. Object.PlaySound бере
// радіус аргументом, зате повертає SoundOnVehicle, у якого з усього API одне
// GetSoundLength(): гучності там немає.
//
// Перейти на друге означало б переписати ще й модель затухання, тобто
// переробити звук, який власник щойно прийняв. Тому лишається перше, а
// налаштовуваний радіус робиться ступенями: по набору на відстань, і JSON
// вибирає найближчу. Ступені видно в лозі, щоб «поставив 30, отримав 25» не
// виглядало як несправність.
//
// Два звуки на кожній ступені: початок і кінець передачі звучать по-різному,
// бо на слух саме різниця й розрізняє «почав» і «договорив».
class CfgSoundShaders
{
    class personalradio_staticnoise_SoundShader;

    class OZR_Squelch_R5: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch", 1}
        };
        volume = 0.5;
        range  = 5;
    };

    class OZR_SquelchOff_R5: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch_off", 1}
        };
        volume = 0.5;
        range  = 5;
    };

    class OZR_Squelch_R10: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch", 1}
        };
        volume = 0.5;
        range  = 10;
    };

    class OZR_SquelchOff_R10: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch_off", 1}
        };
        volume = 0.5;
        range  = 10;
    };

    class OZR_Squelch_R15: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch", 1}
        };
        volume = 0.5;
        range  = 15;
    };

    class OZR_SquelchOff_R15: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch_off", 1}
        };
        volume = 0.5;
        range  = 15;
    };

    class OZR_Squelch_R20: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch", 1}
        };
        volume = 0.5;
        range  = 20;
    };

    class OZR_SquelchOff_R20: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch_off", 1}
        };
        volume = 0.5;
        range  = 20;
    };

    class OZR_Squelch_R25: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch", 1}
        };
        volume = 0.5;
        range  = 25;
    };

    class OZR_SquelchOff_R25: personalradio_staticnoise_SoundShader
    {
        samples[] =
        {
            {"OpenZone_Radio\sounds\ozr_squelch_off", 1}
        };
        volume = 0.5;
        range  = 25;
    };
};

class CfgSoundSets
{
    class personalradio_staticnoise_SoundSet;

    class OZR_Squelch_R5_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_Squelch_R5"};
        loop = 0;
    };

    class OZR_SquelchOff_R5_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_SquelchOff_R5"};
        loop = 0;
    };

    class OZR_Squelch_R10_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_Squelch_R10"};
        loop = 0;
    };

    class OZR_SquelchOff_R10_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_SquelchOff_R10"};
        loop = 0;
    };

    class OZR_Squelch_R15_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_Squelch_R15"};
        loop = 0;
    };

    class OZR_SquelchOff_R15_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_SquelchOff_R15"};
        loop = 0;
    };

    class OZR_Squelch_R20_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_Squelch_R20"};
        loop = 0;
    };

    class OZR_SquelchOff_R20_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_SquelchOff_R20"};
        loop = 0;
    };

    class OZR_Squelch_R25_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_Squelch_R25"};
        loop = 0;
    };

    class OZR_SquelchOff_R25_SoundSet: personalradio_staticnoise_SoundSet
    {
        soundShaders[] = {"OZR_SquelchOff_R25"};
        loop = 0;
    };
};

// THE MODELS. Every range class has a handheld of its own, built for this mod
// in Blender from the scripts in models/ (models/assets/<radio>/scripts; how
// to rebuild them: models/README.md). What ships sits under model/<radio>:
// the binarized p3d, its model.cfg, and data/ with the textures and the
// three materials the damage levels switch between. Every path baked into
// a p3d starts with OpenZone_Radio\model\ -- move a folder and the models
// have to be rebuilt, not just moved.
//
// All six carry one invented brand, OZ-COM, and a model name printed on the
// case; the item name repeats it (stringtable.csv, STR_OZR_RADIO_*).
//
// The frequency window (K) shows the face of the radio in hands
// (5_Mission/OpenZone_Radio/OZR_FreqMenuFace.c). Per class:
//   ozrFaceLayout    the window layout (gui/layouts/oz_face_<s>.layout,
//                    written by models/tools/make_hud_layouts.py)
//   ozrFaceImage     the face picture (gui/faces, .edds like vanilla GUI)
//   ozrFaceMode      "keypad" -- the frequency is typed; "step" -- no
//                    digits, the arrows switch the channel at once
//   ozrFaceHint      the hint line under the radio (stringtable.csv)
// A class without ozrFaceLayout keeps the plain keypad window.
// ozrPowerGesture = "press": switched on and off with the GPS receiver's
// button press (4_World/OpenZone_Radio/OZR_PowerGesture.c) instead of the
// vanilla "turn item on" gesture.
class CfgVehicles
{
    class PersonalRadio;

    // THE FOUR RETIRED RANGE CLASSES, kept as comments by the owner's decision of
    // 2026-09-25 rather than deleted: the six sets above are the ones with a
    // model, and reviving one of these is a matter of uncommenting it here, in
    // OZR_Profiles.c and in packaging/types.xml (their strings are still in the
    // table). They would look like the vanilla walkie-talkie. Items of these
    // classes in saved worlds and inventories are gone while they stay off.
    // class OZ_Radio_50m : PersonalRadio
    // {
    //     scope = 2;
    //     displayName = "$STR_OZR_RADIO_50";
    //     descriptionShort = "$STR_OZR_RADIO_DESC";
    //     range = 50;
    // };

    // class OZ_Radio_100m : PersonalRadio
    // {
    //     scope = 2;
    //     displayName = "$STR_OZR_RADIO_100";
    //     descriptionShort = "$STR_OZR_RADIO_DESC";
    //     range = 100;
    // };

    // class OZ_Radio_200m : PersonalRadio
    // {
    //     scope = 2;
    //     displayName = "$STR_OZR_RADIO_200";
    //     descriptionShort = "$STR_OZR_RADIO_DESC";
    //     range = 200;
    // };

    // class OZ_Radio_750m : PersonalRadio
    // {
    //     scope = 2;
    //     displayName = "$STR_OZR_RADIO_750";
    //     descriptionShort = "$STR_OZR_RADIO_DESC";
    //     range = 750;
    // };

    // 500 m -- Bazar (Базар): a consumer FRS/GMRS handheld after the Midland LXT600.
    class OZ_Radio_500m : PersonalRadio
    {
        scope = 2;
        displayName = "$STR_OZR_RADIO_500";
        descriptionShort = "$STR_OZR_RADIO_DESC_500";
        range = 500;
        model = "\OpenZone_Radio\model\lxt\oz_radio_lxt.p3d";
        ozrFaceLayout = "OpenZone_Radio/gui/layouts/oz_face_lxt.layout";
        ozrFaceImage = "OpenZone_Radio/gui/faces/oz_face_lxt.edds";
        ozrFaceMode = "step";
        ozrFaceHint = "#STR_OZR_HINT_STEP";
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 50;
                    healthLevels[] = {{1.0,{"OpenZone_Radio\model\lxt\data\oz_radio_lxt.rvmat"}},{0.7,{"OpenZone_Radio\model\lxt\data\oz_radio_lxt.rvmat"}},{0.5,{"OpenZone_Radio\model\lxt\data\oz_radio_lxt_damage.rvmat"}},{0.3,{"OpenZone_Radio\model\lxt\data\oz_radio_lxt_damage.rvmat"}},{0.0,{"OpenZone_Radio\model\lxt\data\oz_radio_lxt_destruct.rvmat"}}};
                };
            };
        };
    };

    // 1 km -- Balabolka (Балаболка): a cheap dual-band handheld after the Baofeng UV-5R.
    class OZ_Radio_1000m : PersonalRadio
    {
        scope = 2;
        displayName = "$STR_OZR_RADIO_1000";
        descriptionShort = "$STR_OZR_RADIO_DESC_1000";
        range = 1000;
        model = "\OpenZone_Radio\model\uv5r\oz_radio_uv5r.p3d";
        ozrFaceLayout = "OpenZone_Radio/gui/layouts/oz_face_uv5r.layout";
        ozrFaceImage = "OpenZone_Radio/gui/faces/oz_face_uv5r.edds";
        ozrFaceMode = "keypad";
        ozrFaceHint = "#STR_OZR_HINT_MENU";
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 50;
                    healthLevels[] = {{1.0,{"OpenZone_Radio\model\uv5r\data\oz_radio_uv5r.rvmat"}},{0.7,{"OpenZone_Radio\model\uv5r\data\oz_radio_uv5r.rvmat"}},{0.5,{"OpenZone_Radio\model\uv5r\data\oz_radio_uv5r_damage.rvmat"}},{0.3,{"OpenZone_Radio\model\uv5r\data\oz_radio_uv5r_damage.rvmat"}},{0.0,{"OpenZone_Radio\model\uv5r\data\oz_radio_uv5r_destruct.rvmat"}}};
                };
            };
        };
    };

    // 5 km -- Terran (Терран): a service radio after the Motorola XTS5000.
    class OZ_Radio_5000m : PersonalRadio
    {
        scope = 2;
        displayName = "$STR_OZR_RADIO_5000";
        descriptionShort = "$STR_OZR_RADIO_DESC_5000";
        range = 5000;
        model = "\OpenZone_Radio\model\xts\oz_radio_xts.p3d";
        ozrFaceLayout = "OpenZone_Radio/gui/layouts/oz_face_xts.layout";
        ozrFaceImage = "OpenZone_Radio/gui/faces/oz_face_xts.edds";
        ozrFaceMode = "keypad";
        ozrFaceHint = "#STR_OZR_HINT_ENTER";
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 50;
                    healthLevels[] = {{1.0,{"OpenZone_Radio\model\xts\data\oz_radio_xts.rvmat"}},{0.7,{"OpenZone_Radio\model\xts\data\oz_radio_xts.rvmat"}},{0.5,{"OpenZone_Radio\model\xts\data\oz_radio_xts_damage.rvmat"}},{0.3,{"OpenZone_Radio\model\xts\data\oz_radio_xts_damage.rvmat"}},{0.0,{"OpenZone_Radio\model\xts\data\oz_radio_xts_destruct.rvmat"}}};
                };
            };
        };
    };

    // 250 m -- Sheptun (Шептун): a toy PMR walkie-talkie after the T-388, dirty and cracked.
    class OZ_Radio_250m : PersonalRadio
    {
        scope = 2;
        displayName = "$STR_OZR_RADIO_250";
        descriptionShort = "$STR_OZR_RADIO_DESC_250";
        range = 250;
        model = "\OpenZone_Radio\model\pmr_t388\oz_radio_t388.p3d";
        ozrFaceLayout = "OpenZone_Radio/gui/layouts/oz_face_t388.layout";
        ozrFaceImage = "OpenZone_Radio/gui/faces/oz_face_t388.edds";
        ozrFaceMode = "step";
        ozrFaceHint = "#STR_OZR_HINT_STEP";
        ozrPowerGesture = "press";   // on/off by a button press, the GPS receiver's gesture
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 50;
                    healthLevels[] = {{1.0,{"OpenZone_Radio\model\pmr_t388\data\oz_radio_t388.rvmat"}},{0.7,{"OpenZone_Radio\model\pmr_t388\data\oz_radio_t388.rvmat"}},{0.5,{"OpenZone_Radio\model\pmr_t388\data\oz_radio_t388_damage.rvmat"}},{0.3,{"OpenZone_Radio\model\pmr_t388\data\oz_radio_t388_damage.rvmat"}},{0.0,{"OpenZone_Radio\model\pmr_t388\data\oz_radio_t388_destruct.rvmat"}}};
                };
            };
        };
    };

    // 2 km -- Skrynia (Скриня): a rugged olive dual-band after the Baofeng UV-S9.
    class OZ_Radio_2000m : PersonalRadio
    {
        scope = 2;
        displayName = "$STR_OZR_RADIO_2000";
        descriptionShort = "$STR_OZR_RADIO_DESC_2000";
        range = 2000;
        model = "\OpenZone_Radio\model\uvs9\oz_radio_uvs9.p3d";
        ozrFaceLayout = "OpenZone_Radio/gui/layouts/oz_face_uvs9.layout";
        ozrFaceImage = "OpenZone_Radio/gui/faces/oz_face_uvs9.edds";
        ozrFaceMode = "keypad";
        ozrFaceHint = "#STR_OZR_HINT_MENU";
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 50;
                    healthLevels[] = {{1.0,{"OpenZone_Radio\model\uvs9\data\oz_radio_uvs9.rvmat"}},{0.7,{"OpenZone_Radio\model\uvs9\data\oz_radio_uvs9.rvmat"}},{0.5,{"OpenZone_Radio\model\uvs9\data\oz_radio_uvs9_damage.rvmat"}},{0.3,{"OpenZone_Radio\model\uvs9\data\oz_radio_uvs9_damage.rvmat"}},{0.0,{"OpenZone_Radio\model\uvs9\data\oz_radio_uvs9_destruct.rvmat"}}};
                };
            };
        };
    };

    // 10 km -- Crystal (Кристал): a military handheld after the AN/PRC-152.
    class OZ_Radio_10000m : PersonalRadio
    {
        scope = 2;
        displayName = "$STR_OZR_RADIO_10000";
        descriptionShort = "$STR_OZR_RADIO_DESC_10000";
        range = 10000;
        model = "\OpenZone_Radio\model\prc152\oz_radio_prc152.p3d";
        ozrFaceLayout = "OpenZone_Radio/gui/layouts/oz_face_prc152.layout";
        ozrFaceImage = "OpenZone_Radio/gui/faces/oz_face_prc152.edds";
        ozrFaceMode = "keypad";
        ozrFaceHint = "#STR_OZR_HINT_ENT";
        class DamageSystem
        {
            class GlobalHealth
            {
                class Health
                {
                    hitpoints = 50;
                    healthLevels[] = {{1.0,{"OpenZone_Radio\model\prc152\data\oz_radio_prc152.rvmat"}},{0.7,{"OpenZone_Radio\model\prc152\data\oz_radio_prc152.rvmat"}},{0.5,{"OpenZone_Radio\model\prc152\data\oz_radio_prc152_damage.rvmat"}},{0.3,{"OpenZone_Radio\model\prc152\data\oz_radio_prc152_damage.rvmat"}},{0.0,{"OpenZone_Radio\model\prc152\data\oz_radio_prc152_destruct.rvmat"}}};
                };
            };
        };
    };
};
