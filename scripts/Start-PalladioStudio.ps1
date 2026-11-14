[CmdletBinding()]
param(
    [string]$PythonExe,
    [string]$LibraryPath,
    [ValidateRange(1,65535)][int]$Port = 8765,
    [ValidateRange(1,65535)][int]$OllamaPort = 11434,
    [switch]$NoBrowser,
    [switch]$WithUnreal,
    [string]$UnrealRoot,
    [guid]$PropertyId = [guid]::Empty
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Palladio.Common.ps1')
$Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Python = Get-PalladioPython -PythonExe $PythonExe
if (-not $LibraryPath) { $LibraryPath = Join-Path $Repo '.palladio/properties.sqlite3' }
$LibraryPath = [IO.Path]::GetFullPath($LibraryPath)
if ($WithUnreal) { $UnrealRoot = Resolve-PalladioUnreal -UnrealRoot $UnrealRoot }
$Probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
try { $Probe.Start() } catch { throw "Port $Port is already in use. Stop the existing studio in its terminal, or choose -Port. No existing process was stopped." } finally { $Probe.Stop() }
Push-Location $Repo
$Server = $null
try {
    $ReportText = & $Python -m palladio.diagnostics --library $LibraryPath --backup-before-upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Library preflight failed. The studio has not started.' }
    $Report = ($ReportText -join "`n") | ConvertFrom-Json
    if ($Report.backup) { Write-Host "Pre-upgrade backup: $($Report.backup)" }
    Write-Host "Studio: http://127.0.0.1:$Port"
    Write-Host "Checkout: $Repo"
    Write-Host "Library: $LibraryPath"
    Write-Host "Keep this terminal open. Ctrl+C stops this studio server."
    if (-not $WithUnreal) {
        $Arguments = @('-m','palladio','--port',"$Port",'--ollama-port',"$OllamaPort",'--library',$LibraryPath)
        if ($NoBrowser) { $Arguments += '--no-browser' }
        & $Python @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Studio exited with code $LASTEXITCODE." }
        return
    }
    $LogRoot = Join-Path $Repo ('.palladio/runtime/' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    $Arguments = @('-m','palladio','--port',"$Port",'--ollama-port',"$OllamaPort",'--library',('"' + $LibraryPath + '"'),'--no-browser')
    $Server = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Repo -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $LogRoot 'server.log') -RedirectStandardError (Join-Path $LogRoot 'server-errors.log')
    $Health = $null
    for ($Attempt=0; $Attempt -lt 40; $Attempt++) {
        if ($Server.HasExited) { throw "The studio failed to start. Read $LogRoot" }
        try { $Health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 1 } catch { $Health = $null }
        if ($Health) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $Health -or $Health.app -ne 'Palladio Studio' -or $Health.api_version -ne 2 -or $Health.source_root -ne $Repo -or $Health.library_path -ne $LibraryPath) { throw "The server did not report this checkout and library. Read $LogRoot" }
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
    $Properties = @(Invoke-RestMethod "http://127.0.0.1:$Port/api/properties" -TimeoutSec 5)
    if ($PropertyId -eq [guid]::Empty -and $Properties.Count -gt 0) { $PropertyId = [guid]$Properties[0].id }
    if ($PropertyId -eq [guid]::Empty) {
        Write-Host 'Create and save a property in the browser. Then run Launch-PalladioUnreal.ps1 in another terminal.'
    } else {
        try { & (Join-Path $PSScriptRoot 'Launch-PalladioUnreal.ps1') -UnrealRoot $UnrealRoot -PropertyId $PropertyId -Port $Port }
        catch { Write-Warning "Unreal launch failed: $($_.Exception.Message) The browser studio remains running." }
    }
    Write-Host "Server logs: $LogRoot"
    while (-not $Server.WaitForExit(500)) { }
    if ($Server.ExitCode -ne 0) { throw "Studio exited with code $($Server.ExitCode). Read $LogRoot" }
} finally {
    if ($Server -and -not $Server.HasExited) { Stop-Process -Id $Server.Id -ErrorAction SilentlyContinue }
    Pop-Location
}
