#include "PalladioGameMode.h"
#include "PalladioNavigator.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Canvas.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HttpModule.h"
#include "InputCoreTypes.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"
#include "Modules/ModuleManager.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, PalladioViewport, "PalladioViewport");

namespace
{
FVector VectorField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
{
    const auto& Values = Object->GetArrayField(Field);
    return FVector(Values[0]->AsNumber(), Values[1]->AsNumber(), Values[2]->AsNumber());
}
}

APalladioGameMode::APalladioGameMode()
{
    PrimaryActorTick.bCanEverTick = true;
    DefaultPawnClass = APalladioNavigator::StaticClass();
    HUDClass = APalladioHUD::StaticClass();
}

void APalladioGameMode::StartPlay()
{
    Super::StartPlay();

    FString Property;
    int32 Port = 8765;
    FGuid Parsed;
    FParse::Value(FCommandLine::Get(), TEXT("PalladioPort="), Port);
    if (!FParse::Value(FCommandLine::Get(), TEXT("PalladioProperty="), Property) ||
        !FGuid::ParseExact(Property, EGuidFormats::DigitsWithHyphens, Parsed) ||
        Port < 1 || Port > 65535)
    {
        Status = TEXT("Launch with a Palladio property ID and a valid local port.");
        return;
    }
    Endpoint = FString::Printf(TEXT("http://127.0.0.1:%d/api/properties/%s"), Port,
        *Parsed.ToString(EGuidFormats::DigitsWithHyphensLower));

    Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"));
    ShapeMaterial = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    if (!Cube || !Cone || !ShapeMaterial)
    {
        Status = TEXT("Unreal Engine basic shapes or their material could not be loaded.");
        Endpoint.Reset();
        return;
    }

    auto* Controller = GetWorld()->GetFirstPlayerController();
    if (Controller && Controller->GetPawn())
    {
        const FRotator Rotation(-12, 35, 0);
        Controller->GetPawn()->SetActorLocationAndRotation(FVector(-2200, -1500, 650), Rotation);
        Controller->SetControlRotation(Rotation);
    }

    auto* LandscapeActor = GetWorld()->SpawnActor<AActor>();
    Terrain = NewObject<UProceduralMeshComponent>(LandscapeActor);
    LandscapeActor->SetRootComponent(Terrain);
    Terrain->SetCollisionProfileName(TEXT("BlockAll"));
    Terrain->bUseComplexAsSimpleCollision = true;
    Terrain->RegisterComponent();
    Terrain->SetMaterial(0, Tint(FColor::FromHex(TEXT("728455"))));

    Sun = GetWorld()->SpawnActor<ADirectionalLight>();
    Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    CastChecked<UDirectionalLightComponent>(Sun->GetLightComponent())->SetAtmosphereSunLight(true);
    GetWorld()->SpawnActor<ASkyAtmosphere>();
    auto* Sky = GetWorld()->SpawnActor<ASkyLight>();
    Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);
    Sky->GetLightComponent()->SetRealTimeCaptureEnabled(true);
    Fog = GetWorld()->SpawnActor<AExponentialHeightFog>();
    Request();
}

void APalladioGameMode::Request(const FString& EditBody)
{
    if (bBusy || Endpoint.IsEmpty())
    {
        return;
    }

    const bool bEdit = !EditBody.IsEmpty();
    bBusy = true;
    auto Http = FHttpModule::Get().CreateRequest();
    Http->SetURL(Endpoint + (bEdit ? TEXT("/edit") : TEXT("/unreal")));
    Http->SetVerb(bEdit ? TEXT("POST") : TEXT("GET"));
    Http->SetTimeout(8.0f);
    if (bEdit)
    {
        Http->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
        Http->SetContentAsString(EditBody);
    }
    Http->OnProcessRequestComplete().BindWeakLambda(this,
        [this, bEdit](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
        {
            bBusy = false;
            if (!bSucceeded || !Response.IsValid())
            {
                bReloadRequired |= bEdit;
                Status = bEdit ? TEXT("Save outcome unknown. Press R to reload.")
                    : TEXT("Palladio server unavailable. Start it and press R.");
                return;
            }
            TSharedPtr<FJsonObject> Payload;
            const auto Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
            const bool bParsed = FJsonSerializer::Deserialize(Reader, Payload) && Payload.IsValid();
            if (Response->GetResponseCode() != 200 || !bParsed)
            {
                bReloadRequired |= bEdit;
                if (!bParsed || !Payload->TryGetStringField(TEXT("error"), Status))
                {
                    Status = FString::Printf(TEXT("Invalid server response (HTTP %d). Press R to reload."),
                        Response->GetResponseCode());
                }
                return;
            }
            if (bEdit)
            {
                bReloadRequired = true;
                Request();
                return;
            }
            const TArray<TSharedPtr<FJsonValue>>* Elements = nullptr;
            if (!Payload->TryGetArrayField(TEXT("elements"), Elements) ||
                !Payload->HasTypedField<EJson::Array>(TEXT("vertices_cm")) ||
                !Payload->HasTypedField<EJson::Array>(TEXT("triangles")) ||
                !Payload->HasTypedField<EJson::Object>(TEXT("baseline_environment")))
            {
                Status = TEXT("Start the server from the Unreal viewport branch and press R.");
                return;
            }
            Current = Payload;
            bReloadRequired = false;
            Status.Reset();
            Display(Current);
        });

    if (!Http->ProcessRequest() && bBusy)
    {
        bBusy = false;
        Status = TEXT("Could not start the server request. Press R to retry.");
    }
}

UMaterialInstanceDynamic* APalladioGameMode::Tint(FColor Color)
{
    auto* Material = UMaterialInstanceDynamic::Create(ShapeMaterial, this);
    Material->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(Color));
    return Material;
}

void APalladioGameMode::AddShape(UStaticMesh* Mesh, const FVector& Center, const FVector& Dimensions,
    double Yaw, FColor Color, bool bSelected, bool bBlocksWalking)
{
    auto* Actor = GetWorld()->SpawnActor<AStaticMeshActor>(Center, FRotator(0, Yaw, 0));
    auto* Component = Actor->GetStaticMeshComponent();
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetStaticMesh(Mesh);
    Component->SetCollisionProfileName(bBlocksWalking ? TEXT("BlockAll") : TEXT("NoCollision"));
    Actor->SetActorScale3D(Dimensions / Mesh->GetBoundingBox().GetSize());
    Component->SetMaterial(0, Tint(bSelected ? FColor::FromHex(TEXT("F0BC6A")) : Color));
    Shapes.Add(Actor);
}

void APalladioGameMode::AddMesh(const TSharedPtr<FJsonObject>& Element, bool bSelected)
{
    FVector Base = VectorField(Element, TEXT("center_cm"));
    Base.Z -= VectorField(Element, TEXT("dimensions_cm")).Z / 2;
    auto* Actor = GetWorld()->SpawnActor<AActor>(Base, FRotator(0, Element->GetNumberField(TEXT("yaw_degrees")), 0));
    auto* Mesh = NewObject<UProceduralMeshComponent>(Actor);
    Mesh->SetMobility(EComponentMobility::Movable);
    Actor->SetRootComponent(Mesh);
    Mesh->SetCollisionProfileName(TEXT("BlockAll"));
    Mesh->bUseComplexAsSimpleCollision = true;
    Mesh->RegisterComponent();
    // A plain AActor has no root when spawned; set its transform after attaching one.
    Actor->SetActorLocationAndRotation(Base, FRotator(0, Element->GetNumberField(TEXT("yaw_degrees")), 0));
    int32 SectionIndex = 0;
    for (const auto& Value : Element->GetArrayField(TEXT("mesh_sections")))
    {
        const auto& Section = Value->AsObject();
        TArray<FVector> Vertices;
        TArray<int32> Indices;
        for (const auto& PointValue : Section->GetArrayField(TEXT("vertices_cm")))
        {
            const auto& Point = PointValue->AsArray();
            Vertices.Emplace(Point[0]->AsNumber(), Point[1]->AsNumber(), Point[2]->AsNumber());
        }
        for (const auto& Index : Section->GetArrayField(TEXT("triangles"))) Indices.Add(static_cast<int32>(Index->AsNumber()));
        TArray<FVector> Normals;
        Normals.Init(FVector::ZeroVector, Vertices.Num());
        for (int32 Index = 0; Index < Indices.Num(); Index += 3)
        {
            const int32 A = Indices[Index], B = Indices[Index + 1], C = Indices[Index + 2];
            const FVector Normal = FVector::CrossProduct(Vertices[C] - Vertices[A], Vertices[B] - Vertices[A]);
            Normals[A] += Normal; Normals[B] += Normal; Normals[C] += Normal;
        }
        for (FVector& Normal : Normals) Normal.Normalize();
        Mesh->CreateMeshSection_LinearColor(SectionIndex, Vertices, Indices, Normals,
            TArray<FVector2D>(), TArray<FLinearColor>(), TArray<FProcMeshTangent>(), true);
        Mesh->SetMaterial(SectionIndex, Tint(bSelected ? FColor::FromHex(TEXT("F0BC6A")) : FColor::FromHex(Section->GetStringField(TEXT("color")))));
        ++SectionIndex;
    }
    Shapes.Add(Actor);
}

void APalladioGameMode::BuildLandscape(const TSharedPtr<FJsonObject>& View)
{
    TArray<FVector> Vertices;
    TArray<int32> Indices;
    for (const auto& Value : View->GetArrayField(bBaseline && View->HasField(TEXT("baseline_vertices_cm")) ? TEXT("baseline_vertices_cm") : TEXT("vertices_cm")))
    {
        const auto& Point = Value->AsArray();
        Vertices.Emplace(Point[0]->AsNumber(), Point[1]->AsNumber(), Point[2]->AsNumber());
    }
    for (const auto& Value : View->GetArrayField(TEXT("triangles")))
    {
        Indices.Add(static_cast<int32>(Value->AsNumber()));
    }

    TArray<FVector> Normals;
    Normals.Init(FVector::ZeroVector, Vertices.Num());
    for (int32 Index = 0; Index < Indices.Num(); Index += 3)
    {
        const int32 A = Indices[Index], B = Indices[Index + 1], C = Indices[Index + 2];
        const FVector Normal = FVector::CrossProduct(Vertices[C] - Vertices[A], Vertices[B] - Vertices[A]);
        Normals[A] += Normal;
        Normals[B] += Normal;
        Normals[C] += Normal;
    }
    for (FVector& Normal : Normals)
    {
        Normal.Normalize();
    }
    Terrain->CreateMeshSection_LinearColor(0, Vertices, Indices, Normals,
        TArray<FVector2D>(), TArray<FLinearColor>(), TArray<FProcMeshTangent>(), true);

    if (View->GetBoolField(TEXT("coastal")))
    {
        AddShape(Cube, FVector(0, 9950, -805), FVector(34000, 16100, 10), 0, FColor(61, 110, 122));
    }
    for (const auto& Value : View->GetArrayField(bBaseline && View->HasField(TEXT("baseline_vegetation")) ? TEXT("baseline_vegetation") : TEXT("vegetation")))
    {
        const auto& Tree = Value->AsObject();
        const FVector Base = VectorField(Tree, TEXT("base_cm"));
        const double Height = Tree->GetNumberField(TEXT("height_cm"));
        AddShape(Cube, Base + FVector(0, 0, Height * .26), FVector(22, 22, Height * .52),
            0, FColor(92, 66, 43), false, true);
        AddShape(Cone, Base + FVector(0, 0, Height * .62), FVector(Height * .42, Height * .42, Height * .76),
            0, FColor(61, 100, 59));
    }


}

void APalladioGameMode::Display(const TSharedPtr<FJsonObject>& View)
{
    for (AActor* Shape : Shapes)
    {
        Shape->Destroy();
    }
    Shapes.Reset();
    BuildLandscape(View);

    const auto& Elements = View->GetArrayField(TEXT("elements"));
    if (!Elements.ContainsByPredicate([this](const auto& Value)
        { return Value->AsObject()->GetStringField(TEXT("id")) == Selection; }))
    {
        Selection = Elements.IsEmpty() ? FString() : Elements[0]->AsObject()->GetStringField(TEXT("id"));
    }
    FVector Focus = FVector::ZeroVector;
    if (!bBaseline)
    {
        for (const auto& Value : Elements)
        {
            const auto& Element = Value->AsObject();
            const FVector Center = VectorField(Element, TEXT("center_cm"));
            const bool bSelected = Element->GetStringField(TEXT("id")) == Selection;
            if (Element->HasTypedField<EJson::Array>(TEXT("mesh_sections"))) AddMesh(Element, bSelected);
            else AddShape(Cube, Center, VectorField(Element, TEXT("dimensions_cm")),
                Element->GetNumberField(TEXT("yaw_degrees")), FColor::FromHex(Element->GetStringField(TEXT("color"))),
                bSelected, true);
            if (bSelected)
            {
                Focus = Center;
            }
        }
    }

    auto* Player = GetWorld()->GetFirstPlayerController();
    if (auto* Navigator = Player ? Cast<APalladioNavigator>(Player->GetPawn()) : nullptr)
    {
        Navigator->SetOrbitFocus(Focus);
    }

    const auto& Environment = View->GetObjectField(bBaseline ? TEXT("baseline_environment") : TEXT("environment"));
    const double Hour = Environment->GetNumberField(TEXT("hour"));
    const FString Weather = Environment->GetStringField(TEXT("weather"));
    const double Daylight = FMath::Sin((Hour - 6.0) * UE_PI / 12.0);
    Sun->SetActorRotation(FRotator(-65.0 * Daylight, (Hour - 12.0) * 15.0, 0));
    Sun->GetLightComponent()->SetIntensity(FMath::Max(0.0, Daylight) * (Weather == TEXT("clear") ? 4.0 : 1.6));
    Fog->GetComponent()->SetFogDensity(Weather == TEXT("fog") ? .075f : Weather == TEXT("rain") ? .025f : .008f);
}

void APalladioGameMode::MoveSelection(const FVector& DeltaMetres)
{
    if (bBaseline || bReloadRequired)
    {
        return;
    }
    for (const auto& Value : Current->GetArrayField(TEXT("elements")))
    {
        const auto& Element = Value->AsObject();
        if (Element->GetStringField(TEXT("id")) == Selection)
        {
            const FVector Center = VectorField(Element, TEXT("center_cm"));
            const FVector Dimensions = VectorField(Element, TEXT("dimensions_cm"));
            const FVector Base(Center.X / 100, (Center.Z - Dimensions.Z / 2) / 100, Center.Y / 100);
            FString EditId = Selection;
            FString Action = TEXT("update");
            FVector EditBase = Base;
            if (Element->HasTypedField<EJson::String>(TEXT("edit_id")))
            {
                EditId = Element->GetStringField(TEXT("edit_id"));
                Action = Element->GetStringField(TEXT("edit_action"));
                EditBase = VectorField(Element, TEXT("edit_position"));
            }
            const FVector Position = EditBase + DeltaMetres;
            const FString Field = Action == TEXT("assembly_update") ? TEXT("assembly") : TEXT("element");
            Request(FString::Printf(
                TEXT("{\"revision\":%d,\"commands\":[{\"action\":\"%s\",\"id\":\"%s\",")
                TEXT("\"%s\":{\"position\":[%.8f,%.8f,%.8f]}}]}"),
                Current->GetIntegerField(TEXT("revision")), *Action, *EditId, *Field, Position.X, Position.Y, Position.Z));
            return;
        }
    }
}

void APalladioGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    auto* Player = GetWorld()->GetFirstPlayerController();
    if (!Player)
    {
        return;
    }
    if (auto* Navigator = Cast<APalladioNavigator>(Player->GetPawn()); Navigator && Current.IsValid())
    {
        if (Player->WasInputKeyJustPressed(EKeys::One))
        {
            Navigator->SetNavigation(EPalladioNavigation::Fly);
            NavigationStatus.Reset();
        }
        else if (Player->WasInputKeyJustPressed(EKeys::Two))
        {
            Navigator->SetNavigation(EPalladioNavigation::Orbit);
            NavigationStatus.Reset();
        }
        else if (Player->WasInputKeyJustPressed(EKeys::Three))
        {
            NavigationStatus = Navigator->SetNavigation(EPalladioNavigation::Walk)
                ? FString() : FString(TEXT("No clear walking surface below the camera or at the site entrance."));
        }
    }
    if (bBusy)
    {
        return;
    }
    if (Player->WasInputKeyJustPressed(EKeys::R))
    {
        Request();
        return;
    }
    if (!Current.IsValid())
    {
        return;
    }
    if (Player->WasInputKeyJustPressed(EKeys::B))
    {
        bBaseline = !bBaseline;
        Display(Current);
    }
    const auto& Elements = Current->GetArrayField(TEXT("elements"));
    if (!bBaseline && !Elements.IsEmpty() && Player->WasInputKeyJustPressed(EKeys::Tab))
    {
        const int32 Index = Elements.IndexOfByPredicate([this](const auto& Value)
            { return Value->AsObject()->GetStringField(TEXT("id")) == Selection; });
        Selection = Elements[(Index + 1) % Elements.Num()]->AsObject()->GetStringField(TEXT("id"));
        Display(Current);
    }
    const double X = double(Player->WasInputKeyJustPressed(EKeys::Right)) - double(Player->WasInputKeyJustPressed(EKeys::Left));
    const double Z = double(Player->WasInputKeyJustPressed(EKeys::Up)) - double(Player->WasInputKeyJustPressed(EKeys::Down));
    if (X != 0 || Z != 0)
    {
        MoveSelection(FVector(X * .5, 0, Z * .5));
    }
}

FString APalladioGameMode::Caption() const
{
    if (!Current.IsValid())
    {
        return Status;
    }
    FString SelectedName;
    if (!bBaseline)
    {
        for (const auto& Value : Current->GetArrayField(TEXT("elements")))
        {
            const auto& Element = Value->AsObject();
            if (Element->GetStringField(TEXT("id")) == Selection)
            {
                SelectedName = TEXT("  |  ") + Element->GetStringField(TEXT("name"));
                break;
            }
        }
    }
    const auto* Player = GetWorld()->GetFirstPlayerController();
    const auto* Navigator = Player ? Cast<APalladioNavigator>(Player->GetPawn()) : nullptr;
    const FString Mode = Navigator ? Navigator->NavigationLabel() : FString();
    return FString::Printf(TEXT("%s  |  Revision %d  |  %s  |  %s%s\n%s\n%s"),
        *Current->GetStringField(TEXT("name")), Current->GetIntegerField(TEXT("revision")),
        bBaseline ? TEXT("Original site") : TEXT("Design"), *Mode, *SelectedName,
        bBusy ? TEXT("Synchronizing...") : *Status, *NavigationStatus);
}

void APalladioHUD::DrawHUD()
{
    Super::DrawHUD();
    if (const auto* Mode = GetWorld()->GetAuthGameMode<APalladioGameMode>())
    {
        DrawText(Mode->Caption(), FLinearColor::White, 20, 20, GEngine->GetSmallFont(), 1.3f);
        DrawText(TEXT("1 Fly (WASD, Q/E)   |   2 Orbit (mouse, scroll or W/S)   |   3 Walk (WASD)"),
            FLinearColor::White, 20, Canvas->ClipY - 55, GEngine->GetSmallFont(), 1.1f);
        DrawText(TEXT("Tab Select   |   Arrows Move 0.5 m   |   B Original site   |   R Reload"),
            FLinearColor::White, 20, Canvas->ClipY - 35, GEngine->GetSmallFont(), 1.1f);
    }
}
