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
$accessScript = Join-Path $PSScriptRoot "access.ps1"
$uninstallScript = Join-Path $PSScriptRoot "uninstall.ps1"
$launchScript = Join-Path $PSScriptRoot "launch.ps1"
foreach ($script in @($installScript, $accessScript, $uninstallScript, $launchScript)) {
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
$userDataRoot = Join-Path $testRoot ".opensprite"
$sourceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$quarantinedRuntimes = @()
try {
    . $accessScript
    New-Item -ItemType Directory -Path (Join-Path $userDataRoot "config") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $userDataRoot "data") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $userDataRoot "logs") -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $userDataRoot "config\access.json"), "old-access", [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $userDataRoot "config\settings.json"), "keep-settings", [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $userDataRoot "data\opensprite.db"), "keep-database", [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $userDataRoot "logs\keep.log"), "keep-log", [Text.UTF8Encoding]::new($false))
    $rawBootstrap = New-LocalAccessBootstrap $userDataRoot -Reset
    $storedBootstrap = Get-Content -LiteralPath (Join-Path $userDataRoot "state\access-bootstrap.json") -Raw
    if (Test-Path -LiteralPath (Join-Path $userDataRoot "config\access.json")) { throw "Access reset retained the old password hash." }
    if ($storedBootstrap.Contains($rawBootstrap)) { throw "Bootstrap state contains the raw token." }
    foreach ($preserved in @("config\settings.json", "data\opensprite.db", "logs\keep.log")) {
        if (-not (Test-Path -LiteralPath (Join-Path $userDataRoot $preserved) -PathType Leaf)) { throw "Access reset removed preserved data: $preserved" }
    }
    $firstBootstrap = $storedBootstrap
    $rawBootstrap = $null
    $replacementBootstrap = New-LocalAccessBootstrap $userDataRoot
    $storedBootstrap = Get-Content -LiteralPath (Join-Path $userDataRoot "state\access-bootstrap.json") -Raw
    if ($storedBootstrap -eq $firstBootstrap) { throw "Existing bootstrap state was not atomically replaced." }
    if ($storedBootstrap.Contains($replacementBootstrap)) { throw "Replacement bootstrap state contains the raw token." }
    $replacementBootstrap = $null

    & $installScript -SourceRoot $sourceRoot -InstallRoot $installRoot -UserDataRoot $userDataRoot -AllowCustomInstallRoot -AllowCustomUserDataRoot -SkipAccessBootstrap -SkipStartupRegistration -NoStart | Out-Null
    foreach ($required in @(
        "build-info.json",
        "backend\.venv\Scripts\python.exe",
        "backend\src\opensprite_backend\installed_runtime.py",
        "frontend\dist\index.html",
        "installers\windows\uninstall.ps1",
        "installers\windows\launch.ps1",
        "installers\windows\access.ps1"
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
    $buildInfo = Get-Content -LiteralPath (Join-Path $installRoot "build-info.json") -Raw | ConvertFrom-Json
    $installedVersion = (& $python -c "from importlib.metadata import version; print(version('opensprite-backend'))").Trim()
    if ($LASTEXITCODE -ne 0 -or $buildInfo.version -ne $installedVersion) {
        throw "Installed build metadata version mismatch."
    }
    if ($buildInfo.revision -notmatch '^(?:[0-9a-f]{7,40}|unknown)$' -or $buildInfo.dirty -isnot [bool] -or [String]::IsNullOrWhiteSpace($buildInfo.installedAt)) {
        throw "Installed build metadata is malformed."
    }

    $nativeRuntimeBinaries = @(Get-ChildItem -LiteralPath (Join-Path $installRoot "backend\.venv") -File -Recurse -Filter "*.pyd")
    $pywin32System32 = Join-Path $installRoot "backend\.venv\Lib\site-packages\pywin32_system32"
    if (Test-Path -LiteralPath $pywin32System32 -PathType Container) {
        $nativeRuntimeBinaries += @(Get-ChildItem -LiteralPath $pywin32System32 -File -Filter "*.dll")
    }
    foreach ($nativeRuntimeBinary in $nativeRuntimeBinaries) {
        $quarantinedRuntime = Join-Path $tempRoot ("OpenSprite-installer-quarantine-" + [Guid]::NewGuid().ToString("N") + $nativeRuntimeBinary.Extension)
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
