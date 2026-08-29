[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "OpenSprite\app"),
    [string]$DataRoot = (Join-Path $env:USERPROFILE ".opensprite"),
    [string]$TaskName = "OpenSprite",
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

if ($PSCmdlet.ShouldProcess($TaskName, "Stop and remove the OpenSprite scheduled task")) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
}

$escapedRoot = [Regex]::Escape($installRootPath)
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match $escapedRoot -and $_.CommandLine -match "opensprite_backend\.installed_runtime"
} | ForEach-Object {
    if ($PSCmdlet.ShouldProcess("PID $($_.ProcessId)", "Stop installed OpenSprite backend")) {
        Stop-Process -Id $_.ProcessId -Force
    }
}

if ((Test-Path -LiteralPath $installRootPath) -and $PSCmdlet.ShouldProcess($installRootPath, "Remove OpenSprite application files")) {
    Remove-Item -LiteralPath $installRootPath -Recurse -Force
}
if ($RemoveUserData -and (Test-Path -LiteralPath $dataRootPath) -and $PSCmdlet.ShouldProcess($dataRootPath, "Permanently remove all OpenSprite user data")) {
    Remove-Item -LiteralPath $dataRootPath -Recurse -Force
}

[pscustomobject]@{
    InstallRootRemoved = -not (Test-Path -LiteralPath $installRootPath)
    UserDataRemoved = if ($RemoveUserData) { -not (Test-Path -LiteralPath $dataRootPath) } else { $false }
    ScheduledTaskRemoved = $null -eq (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
}
