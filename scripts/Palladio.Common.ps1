# Shared launcher helpers; importing this file starts no processes or servers.
function Get-PalladioPython {
    param([string]$PythonExe)
    $Prefix = @()
    if ($PythonExe) {
        $Command = $PythonExe
        if ([IO.Path]::GetFileNameWithoutExtension($PythonExe) -eq 'py') { $Prefix = @('-3') }
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $Command = 'py'; $Prefix = @('-3')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Command = 'python'
    } else { throw 'Install Python 3.11 or newer with the Windows py launcher, or pass -PythonExe.' }
    $Resolved = & $Command @Prefix -c "import sys; assert sys.version_info >= (3,11), 'Palladio needs Python 3.11 or newer'; print(sys.executable)"
    if ($LASTEXITCODE -ne 0 -or -not $Resolved) { throw 'Python 3.11 or newer is required.' }
    return ([string]$Resolved).Trim()
}

function Resolve-PalladioUnreal {
    param([string]$UnrealRoot)
    $Candidates = @()
    if ($UnrealRoot) { $Candidates = @($UnrealRoot) }
    else {
        $Manifest = Join-Path $env:ProgramData 'Epic/UnrealEngineLauncher/LauncherInstalled.dat'
        if (Test-Path -LiteralPath $Manifest -PathType Leaf) {
            try {
                $Installs = (Get-Content -Raw -LiteralPath $Manifest | ConvertFrom-Json).InstallationList
                $Candidates += @($Installs | Where-Object { $_.AppName -match '^UE_5\.7($|\.)' -and $_.InstallLocation } | ForEach-Object { $_.InstallLocation })
            } catch { Write-Warning 'Epic install records could not be read; checking the standard install location.' }
        }
        $Candidates += (Join-Path $env:ProgramFiles 'Epic Games/UE_5.7')
    }
    foreach ($Candidate in $Candidates) {
        $Build = Join-Path $Candidate 'Engine/Build/BatchFiles/Build.bat'
        $Editor = Join-Path $Candidate 'Engine/Binaries/Win64/UnrealEditor.exe'
        $VersionFile = Join-Path $Candidate 'Engine/Build/Build.version'
        if ((Test-Path -LiteralPath $Build -PathType Leaf) -and (Test-Path -LiteralPath $Editor -PathType Leaf) -and (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
            $Version = Get-Content -Raw -LiteralPath $VersionFile | ConvertFrom-Json
            if ($Version.MajorVersion -eq 5 -and $Version.MinorVersion -eq 7) { return (Resolve-Path -LiteralPath $Candidate).Path }
        }
    }
    throw 'A complete Unreal Engine 5.7 installation was not found. Check Epic Games Launcher > Unreal Engine > Library, then pass its installation folder to -UnrealRoot.'
}
