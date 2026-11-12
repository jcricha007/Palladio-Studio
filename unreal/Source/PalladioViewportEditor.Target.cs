using UnrealBuildTool;

public class PalladioViewportEditorTarget : TargetRules
{
    public PalladioViewportEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
        ExtraModuleNames.Add("PalladioViewport");
    }
}
