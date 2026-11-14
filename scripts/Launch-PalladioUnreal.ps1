[CmdletBinding()]
param(
    [string] $UnrealRoot,

    [guid] $PropertyId = [guid]::Empty,

    [ValidateRange(1, 65535)]
    [int] $Port = 8765
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Palladio.Common.ps1')
$UnrealRoot = Resolve-PalladioUnreal -UnrealRoot $UnrealRoot
if ($PropertyId -eq [guid]::Empty) {
    $Properties = @(Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/properties" -TimeoutSec 5)
    if ($Properties.Count -eq 0) { throw 'Create and save a property in the browser first.' }
    $PropertyId = [guid]$Properties[0].id
    Write-Host "Opening $($Properties[0].name)"
}
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../unreal/PalladioViewport.uproject')).Path
$build = Join-Path $UnrealRoot 'Engine/Build/BatchFiles/Build.bat'
$editor = Join-Path $UnrealRoot 'Engine/Binaries/Win64/UnrealEditor.exe'
if (!(Test-Path -LiteralPath $build -PathType Leaf) -or !(Test-Path -LiteralPath $editor -PathType Leaf)) {
    throw 'Pass the installed Unreal Engine directory to -UnrealRoot, for example C:\Program Files\Epic Games\UE_5.7.'
}

try {
    $view = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/properties/$PropertyId/unreal" -TimeoutSec 5
} catch {
    throw "Could not load property $PropertyId on port $Port. Start Palladio from this checkout and verify the property ID. $($_.Exception.Message)"
}
if ($null -eq $view.vertices_cm) {
    throw 'The running server did not return a Palladio Unreal scene. Restart it from this checkout.'
}

& $build PalladioViewportEditor Win64 Development "-Project=$project" -WaitMutex
if ($LASTEXITCODE -ne 0) {
    throw "Unreal build failed with exit code $LASTEXITCODE."
}
Start-Process -FilePath $editor -ArgumentList @(
    "`"$project`"",
    '-game',
    '-windowed',
    '-ResX=1280',
    '-ResY=800',
    "-PalladioProperty=$PropertyId",
    "-PalladioPort=$Port"
)
