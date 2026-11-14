[CmdletBinding()]
param(
    [string]$PythonExe,
    [switch]$BrowserSmoke,
    [switch]$BuildUnreal,
    [string]$UnrealRoot,
    [ValidatePattern('^[a-fA-F0-9]{7,40}$')][string]$ExpectedHead,
    [string]$ReportDirectory
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Palladio.Common.ps1')
$Repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Python = Get-PalladioPython -PythonExe $PythonExe
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js to run the JavaScript checks.' }
if (-not $ReportDirectory) { $ReportDirectory = Join-Path $Repo ('.palladio/checks/' + [guid]::NewGuid().ToString('N')) }
$ReportDirectory = [IO.Path]::GetFullPath($ReportDirectory)
New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
$Result = [ordered]@{ started = [DateTime]::UtcNow.ToString('o'); checkout = $Repo; head = 'unknown'; python = $Python; passed = $false; checks = @(); browser = 'not run'; unreal = 'not run'; real_model = 'manual acceptance required' }
$PreviousScreenshot = $env:PALLADIO_SCREENSHOT
Push-Location $Repo
Start-Transcript -Path (Join-Path $ReportDirectory 'console.txt') | Out-Null
try {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $Head = & git rev-parse HEAD
        if ($LASTEXITCODE -ne 0) { throw 'Could not identify the checkout.' }
        $Result.head = ([string]$Head).Trim()
        $Result.dirty = [bool](& git status --porcelain)
    }
    if ($ExpectedHead -and -not $Result.head.StartsWith($ExpectedHead, [StringComparison]::OrdinalIgnoreCase)) { throw 'Checkout does not match -ExpectedHead.' }
    Write-Host "Validating $($Result.head) from $Repo"
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE." }
    $Result.checks += 'Python regressions passed'
    $Suites = @(Get-ChildItem -LiteralPath 'tests' -Filter '*.cjs' | Sort-Object Name)
    foreach ($Suite in $Suites) {
        & node $Suite.FullName
        if ($LASTEXITCODE -ne 0) { throw "JavaScript checks failed: $($Suite.Name)." }
    }
    $Result.checks += "$($Suites.Count) Node suites passed"
    foreach ($Module in (Get-ChildItem -LiteralPath 'palladio/web' -Filter '*.js' | Sort-Object Name)) {
        & node --check $Module.FullName
        if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax check failed: $($Module.Name)." }
    }
    $Result.checks += 'JavaScript syntax passed'
    if ($BrowserSmoke) {
        $env:PALLADIO_SCREENSHOT = Join-Path $ReportDirectory 'browser.png'
        & $Python 'tests/browser_smoke.py'
        if ($LASTEXITCODE -ne 0) { throw 'Rendered browser check failed. Playwright and Chromium must already be installed.' }
        $Result.browser = 'passed'
    }
    if ($BuildUnreal) {
        $Engine = Resolve-PalladioUnreal -UnrealRoot $UnrealRoot
        $Project = Join-Path $Repo 'unreal/PalladioViewport.uproject'
        & (Join-Path $Engine 'Engine/Build/BatchFiles/Build.bat') PalladioViewportEditor Win64 Development "-Project=$Project" -WaitMutex
        if ($LASTEXITCODE -ne 0) { throw "Unreal build failed with exit code $LASTEXITCODE." }
        $Result.unreal = 'compiled; interactive acceptance still required'
    }
    $Result.passed = $true
    Write-Host 'Requested local checks passed. Review the report for checks not run.'
} catch {
    $Result.error = $_.Exception.Message
    throw
} finally {
    $Result.finished = [DateTime]::UtcNow.ToString('o')
    $Result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $ReportDirectory 'report.json') -Encoding UTF8
    $env:PALLADIO_SCREENSHOT = $PreviousScreenshot
    Stop-Transcript | Out-Null
    Pop-Location
    Write-Host "Keep results: $ReportDirectory"
}
