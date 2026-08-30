[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Remove-DirectoryWithRetry([string]$Path, [int]$Attempts = 120) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq $Attempts) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}

function Move-FileWithRetry([string]$Path, [string]$Destination, [int]$Attempts = 120) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Move-Item -LiteralPath $Path -Destination $Destination -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq $Attempts) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}

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

$officialInstallRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
)
$sourceRootForCommand = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\..")
)
$command = @"
. '$($installScript.Replace("'", "''"))' -SourceRoot '$($sourceRootForCommand.Replace("'", "''"))' -InstallRoot '$($officialInstallRoot.Replace("'", "''"))' -WhatIf | Out-Null
New-OpenSpriteStartupValue '$($officialInstallRoot.Replace("'", "''"))' 8765
"@
$startupValue = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command $command
if ($LASTEXITCODE -ne 0) {
    throw "Unable to render the official Windows Run command."
}
if ($startupValue.Length -gt 260) {
    throw "Official Windows Run command exceeds 260 characters: $($startupValue.Length)"
}
$expectedPowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
if (-not $startupValue.StartsWith("`"$expectedPowerShell`" ", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Official Windows Run command must use the absolute Windows PowerShell path."
}
if ($startupValue.Contains(" -InstallRoot ") -or $startupValue.Contains(" -Port ")) {
    throw "Official Windows Run command must omit redundant default arguments."
}

$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd("\")
$testRoot = [System.IO.Path]::GetFullPath((Join-Path $tempRoot ("opensprite-installer-test-" + [Guid]::NewGuid().ToString("N"))))
if (-not $testRoot.StartsWith($tempRoot + "\", [System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $testRoot) -notlike "opensprite-installer-test-*") {
    throw "Unsafe installer test root: $testRoot"
}
$installRoot = Join-Path $testRoot "app"
$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$quarantinedRuntimes = @()
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

    $nativeRuntimeBinaries = @(Get-ChildItem -LiteralPath (Join-Path $installRoot "backend\.venv") -File -Recurse -Filter "*.pyd")
    foreach ($nativeRuntimeBinary in $nativeRuntimeBinaries) {
        $quarantinedRuntime = Join-Path $tempRoot ("OpenSprite-installer-quarantine-" + [Guid]::NewGuid().ToString("N") + ".pyd")
        Move-FileWithRetry $nativeRuntimeBinary.FullName $quarantinedRuntime
        $quarantinedRuntimes += $quarantinedRuntime
    }

    & $uninstallScript -InstallRoot $installRoot -AllowCustomInstallRoot -StartupName ("OpenSprite-Test-" + [Guid]::NewGuid().ToString("N")) -Confirm:$false | Out-Null
    if (Test-Path -LiteralPath $installRoot) {
        throw "Isolated uninstall did not remove the application root."
    }
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        if (-not $testRoot.StartsWith($tempRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe test cleanup." }
        Remove-DirectoryWithRetry $testRoot
    }
    foreach ($quarantinedRuntime in $quarantinedRuntimes) {
        if (Test-Path -LiteralPath $quarantinedRuntime) {
            try { Remove-Item -LiteralPath $quarantinedRuntime -Force -ErrorAction Stop }
            catch { Write-Warning "Windows still holds an isolated native test binary: $quarantinedRuntime" }
        }
    }
}

Write-Output "Windows installer isolation test passed."
