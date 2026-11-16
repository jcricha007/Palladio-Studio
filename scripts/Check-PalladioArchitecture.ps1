[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{40}$')][string]$ExpectedHead,
    [string]$PythonExe,
    [string]$UnrealRoot,
    [string]$ReportDirectory,
    [ValidateRange(1,65535)][int]$Port = 8877,
    [switch]$BrowserSmoke,
    [switch]$SkipUnreal,
    [switch]$Open
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Palladio.Common.ps1')
$Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required to verify this checkout.' }
$Head = & git -C $Repo rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or ([string]$Head).Trim() -ne $ExpectedHead) { throw 'Checkout does not match the reviewed commit.' }
$Dirty = & git -C $Repo status --porcelain --untracked-files=normal
if ($LASTEXITCODE -ne 0) { throw 'Could not check the working tree.' }
if ($Dirty) { throw 'Use an isolated clean worktree for acceptance. Your current changes have not been modified.' }
$Python = Get-PalladioPython -PythonExe $PythonExe
if (-not $SkipUnreal) { $UnrealRoot = Resolve-PalladioUnreal -UnrealRoot $UnrealRoot }
if (-not $ReportDirectory) { $ReportDirectory = Join-Path $env:LOCALAPPDATA ('Palladio/checks/architecture-' + [guid]::NewGuid().ToString('N')) }
$ReportDirectory = [IO.Path]::GetFullPath($ReportDirectory)
$FixturePath = Join-Path $ReportDirectory 'acceptance.sqlite3'
if ((Test-Path -LiteralPath $FixturePath) -or (Test-Path -LiteralPath (Join-Path $ReportDirectory 'report.json'))) {
    throw 'Use a new report directory to preserve the previous results and review property.'
}
$Checks = @{ PythonExe = $Python; ExpectedHead = $ExpectedHead; ReportDirectory = $ReportDirectory }
if ($BrowserSmoke) { $Checks.BrowserSmoke = $true }
if (-not $SkipUnreal) { $Checks.BuildUnreal = $true; $Checks.UnrealRoot = $UnrealRoot }
& (Join-Path $PSScriptRoot 'Validate-Palladio.ps1') @Checks
Push-Location $Repo
try {
    $FixtureText = & $Python -m palladio.acceptance --library $FixturePath
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance property creation failed. Keep the report directory for inspection.' }
    $Fixture = ($FixtureText -join "`n") | ConvertFrom-Json
    $FixtureText | Set-Content -LiteralPath (Join-Path $ReportDirectory 'acceptance.json') -Encoding UTF8
    Copy-Item -LiteralPath (Join-Path $Repo 'docs/ARCHITECTURE_ACCEPTANCE.md') -Destination (Join-Path $ReportDirectory 'WALKTHROUGH.md')
    Write-Host "Checks complete. Keep results: $ReportDirectory"
    Write-Host 'Interactive acceptance has not been recorded. Follow WALKTHROUGH.md and keep screenshots or errors there.'
    if ($Open) {
        $Launch = @{ PythonExe = $Python; LibraryPath = $FixturePath; Port = $Port; PropertyId = [guid]$Fixture.property_id }
        if (-not $SkipUnreal) { $Launch.WithUnreal = $true; $Launch.UnrealRoot = $UnrealRoot }
        & (Join-Path $PSScriptRoot 'Start-PalladioStudio.ps1') @Launch
    }
} finally { Pop-Location }
