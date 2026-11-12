using UnrealBuildTool;

public class PalladioViewportTarget : TargetRules
{
    public PalladioViewportTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("PalladioViewport");
    }
}
