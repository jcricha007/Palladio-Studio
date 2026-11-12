#include "PalladioNavigator.h"

#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

namespace
{
constexpr double EyeOffset = 66.0;
constexpr double MouseSensitivity = 0.16;
const FVector WalkStart(-1000.0, 0.0, 400.0);

double KeyAxis(const APlayerController& Player, const FKey& Positive, const FKey& Negative)
{
    return static_cast<double>(Player.IsInputKeyDown(Positive)) -
        static_cast<double>(Player.IsInputKeyDown(Negative));
}
}

APalladioNavigator::APalladioNavigator()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(25.0f, 96.0f);
    SetActorEnableCollision(false);

    auto* Movement = GetCharacterMovement();
    Movement->DefaultLandMovementMode = MOVE_Flying;
    Movement->MaxFlySpeed = 1100.0f;
    Movement->BrakingDecelerationFlying = 2400.0f;
    Movement->MaxWalkSpeed = 420.0f;
    Movement->MaxStepHeight = 32.0f;

    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("PropertyCamera"));
    Camera->SetupAttachment(GetCapsuleComponent());
    Camera->SetRelativeLocation(FVector(0, 0, EyeOffset));
    Camera->bUsePawnControlRotation = true;
}

bool APalladioNavigator::TryWalkAt(const FVector& Probe)
{
    const auto* Capsule = GetCapsuleComponent();
    const FCollisionShape Shape = FCollisionShape::MakeCapsule(
        Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight());
    FHitResult Floor;
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(PalladioWalkFloor), false, this);
    if (!GetWorld()->SweepSingleByChannel(Floor, Probe, Probe - FVector(0, 0, 30000),
        FQuat::Identity, ECC_Pawn, Shape, Query) || Floor.bStartPenetrating ||
        Floor.ImpactNormal.Z < GetCharacterMovement()->GetWalkableFloorZ())
    {
        return false;
    }

    const FVector Landing = Floor.Location + FVector(0, 0, 3);
    if (GetWorld()->OverlapBlockingTestByChannel(Landing, FQuat::Identity, ECC_Pawn, Shape, Query))
    {
        return false;
    }
    SetActorLocation(Landing, false, nullptr, ETeleportType::TeleportPhysics);
    return true;
}

bool APalladioNavigator::SetNavigation(EPalladioNavigation Next)
{
    if (Next == Navigation)
    {
        return true;
    }
    if (Next == EPalladioNavigation::Walk &&
        !TryWalkAt(Camera->GetComponentLocation()) && !TryWalkAt(WalkStart))
    {
        return false;
    }

    Navigation = Next;
    auto* Movement = GetCharacterMovement();
    Movement->StopMovementImmediately();
    SetActorEnableCollision(Next == EPalladioNavigation::Walk);
    Movement->SetMovementMode(Next == EPalladioNavigation::Walk ? MOVE_Walking :
        Next == EPalladioNavigation::Orbit ? MOVE_None : MOVE_Flying);

    if (Next == EPalladioNavigation::Orbit)
    {
        const FVector Offset = OrbitFocus - Camera->GetComponentLocation();
        OrbitDistance = FMath::Clamp(Offset.Size(), 400.0, 14000.0);
        const FRotator View = Offset.IsNearlyZero() ? FRotator(-25, 35, 0) : Offset.Rotation();
        UpdateOrbit(FRotator(FMath::Clamp(View.Pitch, -80.0, 25.0), View.Yaw, 0));
    }
    return true;
}

void APalladioNavigator::SetOrbitFocus(const FVector& Focus)
{
    OrbitFocus = Focus;
    if (Navigation == EPalladioNavigation::Orbit)
    {
        UpdateOrbit(GetControlRotation());
    }
}

void APalladioNavigator::UpdateOrbit(const FRotator& Rotation)
{
    Controller->SetControlRotation(Rotation);
    const FVector CameraLocation = OrbitFocus - Rotation.Vector() * OrbitDistance;
    SetActorLocation(CameraLocation - FVector(0, 0, EyeOffset));
}

FString APalladioNavigator::NavigationLabel() const
{
    switch (Navigation)
    {
    case EPalladioNavigation::Orbit: return TEXT("Orbit");
    case EPalladioNavigation::Walk: return TEXT("Walk");
    default: return TEXT("Fly");
    }
}

void APalladioNavigator::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const auto* Player = Cast<APlayerController>(Controller);
    if (!Player)
    {
        return;
    }

    float MouseX = 0.0f, MouseY = 0.0f;
    Player->GetInputMouseDelta(MouseX, MouseY);
    const bool bOrbit = Navigation == EPalladioNavigation::Orbit;
    FRotator View = GetControlRotation().GetNormalized();
    View.Yaw += MouseX * MouseSensitivity;
    View.Pitch = FMath::Clamp(View.Pitch + MouseY * MouseSensitivity, -85.0, bOrbit ? 25.0 : 85.0);
    View.Roll = 0;

    if (bOrbit)
    {
        const double Scroll = static_cast<double>(Player->WasInputKeyJustPressed(EKeys::MouseScrollDown)) -
            static_cast<double>(Player->WasInputKeyJustPressed(EKeys::MouseScrollUp));
        const double Zoom = KeyAxis(*Player, EKeys::S, EKeys::W) * DeltaSeconds * 1.6 + Scroll * .12;
        OrbitDistance = FMath::Clamp(OrbitDistance * FMath::Exp(Zoom), 400.0, 14000.0);
        UpdateOrbit(View);
        return;
    }

    Controller->SetControlRotation(View);
    const bool bWalk = Navigation == EPalladioNavigation::Walk;
    const FRotator Heading(0, View.Yaw, 0);
    AddMovementInput(bWalk ? Heading.Vector() : View.Vector(), KeyAxis(*Player, EKeys::W, EKeys::S));
    AddMovementInput(FRotationMatrix(Heading).GetUnitAxis(EAxis::Y), KeyAxis(*Player, EKeys::D, EKeys::A));
    if (!bWalk)
    {
        AddMovementInput(FVector::UpVector, KeyAxis(*Player, EKeys::E, EKeys::Q));
    }
    else if (GetActorLocation().Z < -3000.0)
    {
        GetCharacterMovement()->StopMovementImmediately();
        if (!TryWalkAt(WalkStart))
        {
            SetNavigation(EPalladioNavigation::Fly);
            SetActorLocation(WalkStart);
        }
    }
}
