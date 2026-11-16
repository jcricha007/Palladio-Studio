[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$')][string]$Model = 'gpt-oss:20b',
    [ValidateRange(1,65535)][int]$OllamaPort = 11435,
    [ValidateRange(1,65535)][int]$Port = 8765,
    [string]$PythonExe,
    [string]$LibraryPath,
    [switch]$SetupOnly,
    [switch]$WithUnreal,
    [string]$UnrealRoot
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Palladio.Common.ps1')
$Python = Get-PalladioPython -PythonExe $PythonExe
$Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ($Model -match '(?i)cloud|https?') { throw 'Choose a local Ollama weight model, not a cloud alias.' }
if ($Port -eq $OllamaPort) { throw 'Studio and Ollama need different ports.' }

# Official portable Windows release, pinned and checked before execution.
# https://api.github.com/repos/ollama/ollama/releases/tags/v0.40.16
$Version = 'v0.40.16'
$Sha256 = '50fcf5ad54277f2fa5d173ebfc93bcb017adbc0c9ef2314daabc96ca9e6aa64e'
$Download = "https://github.com/ollama/ollama/releases/download/$Version/ollama-windows-amd64.zip"
$RuntimeRoot = Join-Path $env:LOCALAPPDATA 'Palladio/runtime'
$Install = Join-Path $RuntimeRoot "ollama/$Version"
$Exe = Join-Path $Install 'ollama.exe'
$Marker = Join-Path $Install 'verified-release.sha256'
$Models = Join-Path $env:LOCALAPPDATA 'Palladio/models'
$Logs = Join-Path $RuntimeRoot "ollama-server-$OllamaPort"
$Endpoint = "http://127.0.0.1:$OllamaPort"
$PidFile = Join-Path $Logs 'server.json'
$Server = $null
$StartedHere = $false
$Ready = $false
$Names = @('OLLAMA_HOST','OLLAMA_MODELS','OLLAMA_NO_CLOUD','OLLAMA_NUM_PARALLEL','OLLAMA_MAX_LOADED_MODELS','OLLAMA_CONTEXT_LENGTH','OLLAMA_KEEP_ALIVE')
$Previous = @{}
foreach ($Name in $Names) { $Previous[$Name] = [Environment]::GetEnvironmentVariable($Name,'Process') }
try {
    New-Item -ItemType Directory -Path $RuntimeRoot,$Install,$Models,$Logs -Force | Out-Null
    if (!(Test-Path -LiteralPath $Exe) -or !(Test-Path -LiteralPath $Marker) -or (Get-Content -Raw -LiteralPath $Marker).Trim() -ne $Sha256) {
        $Drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($Install))
        if ($Drive.AvailableFreeSpace -lt 24GB) { throw 'Keep at least 24 GB free for the portable runtime and default model.' }
        $Archive = Join-Path $RuntimeRoot "ollama-$Version.zip"
        if (!(Test-Path -LiteralPath $Archive) -or (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $Sha256) {
            Write-Host 'Downloading the official Ollama runtime (about 1.6 GB)...'
            Invoke-WebRequest -Uri $Download -OutFile $Archive -UseBasicParsing
        }
        if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $Sha256) { throw 'Ollama checksum mismatch. No downloaded code was run.' }
        Expand-Archive -LiteralPath $Archive -DestinationPath $Install -Force
        if (!(Test-Path -LiteralPath $Exe)) { throw 'Ollama archive did not contain the expected executable.' }
        Set-Content -LiteralPath $Marker -Value $Sha256 -Encoding ASCII
    }
    $env:OLLAMA_HOST = "127.0.0.1:$OllamaPort"
    $env:OLLAMA_MODELS = $Models
    $env:OLLAMA_NO_CLOUD = '1'
    $env:OLLAMA_NUM_PARALLEL = '1'
    $env:OLLAMA_MAX_LOADED_MODELS = '1'
    $env:OLLAMA_CONTEXT_LENGTH = '16384'
    $env:OLLAMA_KEEP_ALIVE = '0'
    # Reuse only the process this launcher recorded, including its start time.
    if (Test-Path -LiteralPath $PidFile) {
        try {
            $Record = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json
            $Candidate = Get-Process -Id $Record.pid -ErrorAction Stop
            if ($Candidate.Path -eq $Exe -and $Candidate.StartTime.ToUniversalTime().Ticks -eq $Record.start_ticks) { $Server = $Candidate }
        } catch { $Server = $null }
    }
    if (-not $Server) {
        $Probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$OllamaPort)
        try { $Probe.Start() } catch { throw "Port $OllamaPort is occupied by another process. Choose -OllamaPort; no process was stopped." } finally { $Probe.Stop() }
        $Server = Start-Process -FilePath $Exe -ArgumentList 'serve' -WorkingDirectory $Install -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'output.log') -RedirectStandardError (Join-Path $Logs 'error.log')
        $StartedHere = $true
        @{pid=$Server.Id;start_ticks=$Server.StartTime.ToUniversalTime().Ticks} | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding UTF8
    }
    $Health = $null
    for ($Attempt=0; $Attempt -lt 60; $Attempt++) {
        if ($Server.HasExited) { throw "Ollama exited. Read $Logs/error.log" }
        try { $Health = Invoke-RestMethod "$Endpoint/api/version" -TimeoutSec 1 } catch { $Health = $null }
        if ($Health) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $Health -or $Health.version -ne $Version.TrimStart('v')) { throw "The managed Ollama runtime did not become ready at $Endpoint." }
    Write-Host "Installing $Model (gpt-oss:20b is about 14 GB; interrupted pulls can resume)..."
    & $Exe pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'The model download failed. Rerun this script to resume.' }
    Push-Location $Repo
    try {
        & $Python -m palladio.model_check --model $Model --port $OllamaPort
        if ($LASTEXITCODE -ne 0) { throw 'The model was downloaded but did not pass the Palladio proposal check. Read the report before using it.' }
    } finally { Pop-Location }
    $Ready = $true
    Write-Host "Local model ready at $Endpoint. Open Design assistant > Local Ollama > Refresh models > $Model."
    Write-Host 'This managed runtime stays available in the background. Model memory is released after each request.'
    if (-not $SetupOnly) {
        $Launch = @{PythonExe=$Python;Port=$Port;OllamaPort=$OllamaPort}
        if ($LibraryPath) { $Launch.LibraryPath=$LibraryPath }
        if ($WithUnreal) { $Launch.WithUnreal=$true; $Launch.UnrealRoot=$UnrealRoot }
        & (Join-Path $PSScriptRoot 'Start-PalladioStudio.ps1') @Launch
    }
} finally {
    foreach ($Name in $Names) { [Environment]::SetEnvironmentVariable($Name,$Previous[$Name],'Process') }
    if ($StartedHere -and -not $Ready -and $Server -and -not $Server.HasExited) { Stop-Process -Id $Server.Id }
}
