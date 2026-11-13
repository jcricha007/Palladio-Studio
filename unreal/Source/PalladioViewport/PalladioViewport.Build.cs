using UnrealBuildTool;

public class PalladioViewport : ModuleRules
{
    public PalladioViewport(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] {
            "HTTP", "Json", "InputCore", "PhysicsCore", "ProceduralMeshComponent"
        });
    }
}
