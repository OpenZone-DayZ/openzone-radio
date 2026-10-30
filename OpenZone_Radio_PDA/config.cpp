// Рація всередині КПК -- НЕОБОВ'ЯЗКОВИЙ pbo.
//
// Що тут і чому саме тут. Плата рації -- це код МОДА РАЦІЇ: скриптовий клас
// OZ_Module_Radio живе там і не згадує ні КПК, ні ядра. Але його КОНФІГУРАЦІЙНИЙ
// запис успадковується від OZ_Module_Base -- класу КПК, -- а це вже жорстка
// залежність на рівні конфіга, обійти яку нічим. Тому сюди їде рівно вона: те,
// чим плата ОГОЛОШУЄТЬСЯ модулем відсіку, і те, чим вона в КПК вбудовується --
// договір заліза, пошук у відсіках, сторінка та її канали.
//
// Ставиться, коли крутять і рацію, і КПК. Не ставиться -- і кожен з них
// працює сам по собі, нічого одне про одного не знаючи. Ані @OpenZone_Radio,
// ані @OpenZone_PDA не згадують сусіда жодним рядком.

class CfgPatches
{
    class OpenZone_Radio_PDA
    {
        units[] = {};
        weapons[] = {};
        requiredVersion = 0.1;
        requiredAddons[] =
        {
            "DZ_Data",
            "DZ_Scripts",
            "JM_CF_Scripts",
            "OpenZone_Core",
            "OpenZone_PDA",
            "OpenZone_Radio"
        };
    };
};

class CfgMods
{
    class OpenZone_Radio_PDA
    {
        dir = "OpenZone_Radio_PDA";
        name = "OpenZone Radio in the PDA";
        author = "OpenZone";
        version = "0.1.0";
        type = "mod";

        dependencies[] = {"Game", "World", "Mission"};

        class defs
        {
            // НАШ ЗНАЧОК -- У НАШОМУ НАБОРІ (рішення власника 2026-09-09).
            // Картинка вкладки «Рація» лежала в атласі КПК: мод малював
            // сторінку, а її значок ніс сусід, який про рацію не знає. Тепер
            // набір їде разом зі склейкою, тим самим способом, яким його везе
            // будь-який мод: рядок тут плюс .imageset поруч зі своїм _ca.paa
            // всередині pbo. Реєструє його ТА САМА конструкція, що й у КПК і
            // у VPPAdminTools, -- перелік файлів у defs мода.
            class imageSets { files[] = {"OpenZone_Radio_PDA/gui/imagesets/oz_radio_icons.imageset"}; };
            class gameScriptModule    { value = ""; files[] = {"OpenZone_Radio_PDA/scripts/3_Game"}; };
            class worldScriptModule   { value = ""; files[] = {"OpenZone_Radio_PDA/scripts/4_World"}; };
            class missionScriptModule { value = ""; files[] = {"OpenZone_Radio_PDA/scripts/5_Mission"}; };
        };
    };
};

class CfgVehicles
{
    class OZ_Module_Base;

    // The radio board. Turns the PDA into a transceiver, and it carries its own
    // reach: there is no antenna module any more, because an antenna is not a
    // thing you carry in the bay next to the radio.
    //
    // simulation="itemTransmitter" is the ONE line that matters, and it was
    // expensive to find. The engine picks an entity's native type from this
    // field -- not from the config parent, and not from the script class. A
    // board without it comes out a plain ItemBase however faithfully its
    // script class extends TransmitterBase: measured on the stand, where the
    // cast to a transmitter kept failing while everything else looked right,
    // and a board the engine does not consider a transmitter carries no voice
    // at all.
    class OZ_Module_Radio : OZ_Module_Base
    {
        scope = 2;
        simulation = "itemTransmitter";
        // ВЛАСНА дальність, як у будь-якої рації. Раніше її давав окремий
        // модуль антени в сусідньому відсіку -- поняття, якого в рації немає:
        // антена не річ, яку носять окремо від передавача.
        range = 2500;
        displayName = "$STR_OZR_MOD_RADIO";
        descriptionShort = "$STR_OZR_MOD_RADIO_DESC";
    };
};
