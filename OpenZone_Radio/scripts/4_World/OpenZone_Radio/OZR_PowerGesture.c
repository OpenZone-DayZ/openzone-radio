// The switch-on and switch-off gesture, per model.
//
// Vanilla switches every radio on with the generic "turn item on" gesture
// (CMD_ACTIONMOD_ITEM_ON/OFF). A push-button radio suits a thumb press better: the GPS
// receiver's gesture (ActionTurnOnWhileInHands picks it for GPSReceiver). Which gesture a
// class gets is the ozrPowerGesture field of its config: "press" - the button; no field -
// the vanilla gesture.
//
// Vanilla's per-item override (ItemBase.OverrideActionAnimation) is keyed by script type,
// and the OZ_Radio_* sets have no script classes of their own - they are all PersonalRadio.
// So the override happens in the action itself, by the item class's config.

class OZR_PowerGesture
{
    // The gesture command for the item, or -1 - keep the vanilla one.
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

// The button gesture exists only in the GPS receiver's animation set
// (player_main_1h_GPSReciever.asi). A radio in hand takes the generic one-handed set, which
// lacks it - overriding the command alone played nothing (checked by the owner 2026-09-25).
// So the push-button sets get the GPS set and the GPS grip pose (GPSReciever.anm) - they are
// held like a GPS receiver.
modded class ModItemRegisterCallbacks
{
    override void RegisterOneHanded(DayZPlayerType pType, DayzPlayerItemBehaviorCfg pBehavior)
    {
        super.RegisterOneHanded(pType, pBehavior);

        string asi = "dz/anims/workspaces/player/player_main/props/player_main_1h_GPSReciever.asi";
        string anm = "dz/anims/anm/player/ik/gear/GPSReciever.anm";   // and the GPS grip - the owner's choice, 2026-09-25
        array<string> press = {"OZ_Radio_250m"};   // the push-button sets: those with ozrPowerGesture = "press"
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
