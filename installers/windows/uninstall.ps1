[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "OpenSprite\app"),
    [string]$DataRoot = (Join-Path $env:USERPROFILE ".opensprite"),
    [string]$StartupName = "OpenSprite",
    [switch]$RemoveUserData,
    [switch]$AllowCustomInstallRoot,
    [switch]$AllowCustomDataRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath([string]$Path) {
    return [System.IO.Path]::GetFullPath(
        $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    )
}

function Test-SamePath([string]$Left, [string]$Right) {
    return [System.StringComparer]::OrdinalIgnoreCase.Equals(
        $Left.TrimEnd("\"),
        $Right.TrimEnd("\")
    )
}

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

function Get-RemovalStatus([bool]$Existed, [bool]$Exists) {
    if ($Exists) { return 'Retained' }
    if ($Existed) { return 'Removed' }
    return 'Already absent'
}

$installRootPath = Resolve-AbsolutePath $InstallRoot
$dataRootPath = Resolve-AbsolutePath $DataRoot
$expectedInstallRoot = Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
$expectedDataRoot = Resolve-AbsolutePath (Join-Path $env:USERPROFILE ".opensprite")
if (-not $AllowCustomInstallRoot -and -not (Test-SamePath $installRootPath $expectedInstallRoot)) {
    throw "InstallRoot must be the official OpenSprite app path: $expectedInstallRoot"
}
if ($RemoveUserData -and -not $AllowCustomDataRoot -and -not (Test-SamePath $dataRootPath $expectedDataRoot)) {
    throw "DataRoot must be the official OpenSprite user-data path: $expectedDataRoot"
}

$appExisted = Test-Path -LiteralPath $installRootPath
$dataExisted = Test-Path -LiteralPath $dataRootPath
$startupExisted = $null -ne (Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $StartupName -ErrorAction SilentlyContinue)
$uninstallCompleted = $false

try {
    if ($PSCmdlet.ShouldProcess($StartupName, "Remove the OpenSprite current-user startup entry")) {
        Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $StartupName -ErrorAction SilentlyContinue
    }

    $escapedRoot = [Regex]::Escape($installRootPath)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match $escapedRoot -and $_.CommandLine -match "opensprite_backend\.installed_runtime"
    } | ForEach-Object {
        if ($PSCmdlet.ShouldProcess("PID $($_.ProcessId)", "Stop installed OpenSprite backend")) {
            try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }
            catch {
                # Stopping the launcher can also end a child captured by the CIM query.
                # Only an already-exited PID is success; access/other failures must abort.
                if ($_.FullyQualifiedErrorId -notlike 'NoProcessFoundForGivenId,*') { throw }
            }
        }
    }

    if ((Test-Path -LiteralPath $installRootPath) -and $PSCmdlet.ShouldProcess($installRootPath, "Remove OpenSprite application files")) {
        Remove-DirectoryWithRetry $installRootPath
    }
    if ($RemoveUserData -and (Test-Path -LiteralPath $dataRootPath) -and $PSCmdlet.ShouldProcess($dataRootPath, "Permanently remove all OpenSprite user data")) {
        Remove-DirectoryWithRetry $dataRootPath
    }
    $uninstallCompleted = $true
} finally {
    $appRemains = Test-Path -LiteralPath $installRootPath
    $dataRemains = Test-Path -LiteralPath $dataRootPath
    $startupRemains = $null -ne (Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $StartupName -ErrorAction SilentlyContinue)
    Write-Host ''
    Write-Host 'OpenSprite uninstall summary (current state)'
    if (-not $uninstallCompleted) { Write-Host '  Uninstall stopped before completion. Remaining folders may contain partially removed files.' }
    if ($WhatIfPreference) { Write-Host '  Preview only; no changes were made.' }
    Write-Host "  Application: $(Get-RemovalStatus $appExisted $appRemains) -- $installRootPath"
    Write-Host "  Startup entry: $(Get-RemovalStatus $startupExisted $startupRemains) -- HKCU:\Software\Microsoft\Windows\CurrentVersion\Run [$StartupName]"
    Write-Host "  User data: $(Get-RemovalStatus $dataExisted $dataRemains) -- $dataRootPath"
    Write-Host '    Includes settings, encrypted credentials and key, conversations, schedules,'
    Write-Host '    managed workspace files, skills, agents, archives, logs, state and cache.'
    if ($dataRemains -and ($uninstallCompleted -or -not $RemoveUserData)) { Write-Host '  Retained user data can be reused after reinstalling OpenSprite.' }
    Write-Host '  Not removed: Git, Node.js, uv, shared tool caches, source checkouts and external workspace folders.'
    if (($appRemains -or $startupRemains) -and -not $WhatIfPreference) {
        Write-Warning 'Uninstall is incomplete: application files or the startup entry remain.'
    }
}
$remainingStartup = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $StartupName -ErrorAction SilentlyContinue
[pscustomobject]@{
    InstallRootRemoved = -not (Test-Path -LiteralPath $installRootPath)
    UserDataRemoved = if ($RemoveUserData) { -not (Test-Path -LiteralPath $dataRootPath) } else { $false }
    StartupEntryRemoved = $null -eq $remainingStartup
}
