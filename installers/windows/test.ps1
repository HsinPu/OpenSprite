[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$installScript = Join-Path $PSScriptRoot "install.ps1"
$uninstallScript = Join-Path $PSScriptRoot "uninstall.ps1"
$launchScript = Join-Path $PSScriptRoot "launch.ps1"
foreach ($script in @($installScript, $uninstallScript, $launchScript)) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors) | Out-Null
    if ($errors.Count -gt 0) {
        throw "PowerShell parser errors in $script`: $($errors -join '; ')"
    }
}

$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd("\")
$testRoot = [System.IO.Path]::GetFullPath((Join-Path $tempRoot ("opensprite-installer-test-" + [Guid]::NewGuid().ToString("N"))))
if (-not $testRoot.StartsWith($tempRoot + "\", [System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $testRoot) -notlike "opensprite-installer-test-*") {
    throw "Unsafe installer test root: $testRoot"
}
$installRoot = Join-Path $testRoot "app"
$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
try {
    & $installScript -SourceRoot $sourceRoot -InstallRoot $installRoot -AllowCustomInstallRoot -SkipStartupRegistration -NoStart | Out-Null
    foreach ($required in @(
        "backend\.venv\Scripts\python.exe",
        "backend\src\opensprite_backend\installed_runtime.py",
        "frontend\dist\index.html",
        "installers\windows\uninstall.ps1",
        "installers\windows\launch.ps1"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $installRoot $required) -PathType Leaf)) {
            throw "Isolated install is missing: $required"
        }
    }
    if (Test-Path -LiteralPath (Join-Path $installRoot "frontend\node_modules")) {
        throw "Runtime install must not retain frontend node_modules."
    }
    $python = Join-Path $installRoot "backend\.venv\Scripts\python.exe"
    & $python -c "from opensprite_backend.installed_runtime import default_frontend_dist; assert default_frontend_dist().joinpath('index.html').is_file()"
    if ($LASTEXITCODE -ne 0) { throw "Installed Python runtime check failed." }

    & $uninstallScript -InstallRoot $installRoot -AllowCustomInstallRoot -StartupName ("OpenSprite-Test-" + [Guid]::NewGuid().ToString("N")) -Confirm:$false | Out-Null
    if (Test-Path -LiteralPath $installRoot) {
        throw "Isolated uninstall did not remove the application root."
    }
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        if (-not $testRoot.StartsWith($tempRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe test cleanup." }
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}

Write-Output "Windows installer isolation test passed."
