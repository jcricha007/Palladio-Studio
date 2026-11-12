using UnrealBuildTool;

public class PalladioViewportEditorTarget : TargetRules
{
    public PalladioViewportEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        ExtraModuleNames.Add("PalladioViewport");
    }
}
