using UnrealBuildTool;

public class PalladioViewportTarget : TargetRules
{
    public PalladioViewportTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        ExtraModuleNames.Add("PalladioViewport");
    }
}
