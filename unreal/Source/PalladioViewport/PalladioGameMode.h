#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "PalladioGameMode.generated.h"

class ADirectionalLight;
class AExponentialHeightFog;
class FJsonObject;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UProceduralMeshComponent;
class UStaticMesh;

UCLASS()
class APalladioGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    APalladioGameMode();
    virtual void StartPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    FString Caption() const;

private:
    void Request(const FString& EditBody = FString());
    void BuildLandscape(const TSharedPtr<FJsonObject>& View);
    void Display(const TSharedPtr<FJsonObject>& View);
    void MoveSelection(const FVector& DeltaMetres);
    void AddShape(UStaticMesh* Mesh, const FVector& Center, const FVector& Dimensions,
        double Yaw, FColor Color, bool bSelected = false);
    UMaterialInstanceDynamic* Tint(FColor Color);

    UPROPERTY()
    TObjectPtr<UProceduralMeshComponent> Terrain;
    UPROPERTY()
    TObjectPtr<ADirectionalLight> Sun;
    UPROPERTY()
    TObjectPtr<AExponentialHeightFog> Fog;
    UPROPERTY()
    TObjectPtr<UStaticMesh> Cube;
    UPROPERTY()
    TObjectPtr<UStaticMesh> Cone;
    UPROPERTY()
    TObjectPtr<UMaterialInterface> ShapeMaterial;
    UPROPERTY()
    TArray<TObjectPtr<AActor>> Shapes;

    FString Endpoint;
    FString Status = TEXT("Loading property...");
    FString Selection;
    TSharedPtr<FJsonObject> Current;
    bool bBusy = false;
    bool bBaseline = false;
    bool bReloadRequired = false;
};

UCLASS()
class APalladioHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};
