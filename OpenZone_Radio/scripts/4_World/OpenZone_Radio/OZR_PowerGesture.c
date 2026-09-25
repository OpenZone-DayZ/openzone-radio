// Жест включения и выключения рации - свой у модели.
//
// Ваниль включает любую рацию общим жестом «включить предмет» (CMD_ACTIONMOD_ITEM_ON/OFF).
// Кнопочным рациям больше подходит нажатие кнопки большим пальцем - жест GPS-приёмника
// (ActionTurnOnWhileInHands выбирает его для GPSReceiver). Какой жест у класса - поле
// ozrPowerGesture в его конфиге: "press" - кнопка; нет поля - ванильный жест.
//
// Ванильная подмена по предмету (ItemBase.OverrideActionAnimation) ключуется скриптовым
// типом, а у раций OZ_Radio_* своих скриптовых классов нет - все они PersonalRadio. Поэтому
// подменяем в самом действии, по конфигу класса предмета.

class OZR_PowerGesture
{
    // Команда жеста для предмета, или -1 - оставить ванильную.
    static int For(ActionData data)
    {
        if (!data || !data.m_MainItem || !data.m_Player)
            return -1;

        string gesture = GetGame().ConfigGetTextOut("CfgVehicles " + data.m_MainItem.GetType() + " ozrPowerGesture");
        if (gesture != "press")
            return -1;

        if (data.m_Player.IsPlayerInStance(DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT))
            return DayZPlayerConstants.CMD_ACTIONMOD_PRESS_TRIGGER;
        return DayZPlayerConstants.CMD_ACTIONFB_PRESS_TRIGGER;
    }
}

// Жест кнопки есть только в наборе анимаций GPS-приёмника (player_main_1h_GPSReciever.asi).
// Рация в руке берёт общий однорочный набор, где его нет, - подмена команды одна ничего не
// проигрывала (проверено пользователем 25.09). Поэтому кнопочные рации получают набор GPS
// и позу хвата GPS (GPSReciever.anm) - держатся как GPS-приёмник.
modded class ModItemRegisterCallbacks
{
    override void RegisterOneHanded(DayZPlayerType pType, DayzPlayerItemBehaviorCfg pBehavior)
    {
        super.RegisterOneHanded(pType, pBehavior);

        string asi = "dz/anims/workspaces/player/player_main/props/player_main_1h_GPSReciever.asi";
        string anm = "dz/anims/anm/player/ik/gear/GPSReciever.anm";   // и хват как у GPS - выбор пользователя 25.09
        array<string> press = {"OZ_Radio_250m"};   // кнопочные - те, у кого ozrPowerGesture = "press"
        foreach (string cls : press)
            pType.AddItemInHandsProfileIK(cls, asi, pBehavior, anm);
    }
}

modded class ActionTurnOnTransmitter
{
    override protected int GetCommandOverride(ActionData actionData)
    {
        int cmd = OZR_PowerGesture.For(actionData);
        if (cmd != -1)
            return cmd;
        return super.GetCommandOverride(actionData);
    }
}

modded class ActionTurnOffTransmitter
{
    override protected int GetCommandOverride(ActionData actionData)
    {
        int cmd = OZR_PowerGesture.For(actionData);
        if (cmd != -1)
            return cmd;
        return super.GetCommandOverride(actionData);
    }
}
