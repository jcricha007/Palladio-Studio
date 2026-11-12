#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "PalladioNavigator.generated.h"

class UCameraComponent;

enum class EPalladioNavigation : uint8
{
    Fly,
    Orbit,
    Walk
};

UCLASS()
class APalladioNavigator : public ACharacter
{
    GENERATED_BODY()

public:
    APalladioNavigator();
    virtual void Tick(float DeltaSeconds) override;

    bool SetNavigation(EPalladioNavigation Next);
    void SetOrbitFocus(const FVector& Focus);
    FString NavigationLabel() const;

private:
    bool TryWalkAt(const FVector& Probe);
    void UpdateOrbit(const FRotator& Rotation);

    UPROPERTY()
    TObjectPtr<UCameraComponent> Camera;

    EPalladioNavigation Navigation = EPalladioNavigation::Fly;
    FVector OrbitFocus = FVector::ZeroVector;
    double OrbitDistance = 2400.0;
};
