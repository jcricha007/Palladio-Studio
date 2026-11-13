[CmdletBinding()]
param(
    [string]$PythonExe = 'py',
    [switch]$BrowserSmoke
)

$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    Write-Host 'Running Palladio checks from this checkout.'
    & $PythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE." }
    foreach ($Suite in (Get-ChildItem -LiteralPath 'tests' -Filter '*.cjs' | Sort-Object Name)) {
        & node $Suite.FullName
        if ($LASTEXITCODE -ne 0) { throw "JavaScript checks failed: $($Suite.Name)." }
    }
    foreach ($Module in (Get-ChildItem -LiteralPath 'palladio/web' -Filter '*.js' | Sort-Object Name)) {
        & node --check $Module.FullName
        if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax check failed: $($Module.Name)." }
    }
    if ($BrowserSmoke) {
        & $PythonExe 'tests/browser_smoke.py'
        if ($LASTEXITCODE -ne 0) { throw 'Rendered browser check failed. Read the error above; Playwright and Chromium must already be installed.' }
    }
    Write-Host 'Local checks passed. Unreal and real-model acceptance are separate checks.'
} finally {
    Pop-Location
}
