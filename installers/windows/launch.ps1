[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "OpenSprite\app"),
    [int]$Port = 8765,
    [switch]$AllowCustomInstallRoot
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

function Write-BootstrapError([string]$Message) {
    try {
        $date = [DateTime]::Now.ToString("yyyy-MM-dd")
        $directory = Join-Path $env:USERPROFILE ".opensprite\logs\backend\$date"
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
        $safe = $Message -replace '(?i)(authorization\s*[:=]\s*bearer\s+)\S+', '$1[REDACTED]' -replace '\bsk-[A-Za-z0-9_-]{8,}\b', '[REDACTED]'
        $line = "{0} ERROR opensprite.bootstrap launcher failed message={1}`r`n" -f [DateTimeOffset]::Now.ToString("o"), $safe
        [IO.File]::AppendAllText((Join-Path $directory "bootstrap.log"), $line, [Text.UTF8Encoding]::new($false))
    }
    catch { }
}

$installRootPath = Resolve-AbsolutePath $InstallRoot
$expectedRoot = Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
if (-not $AllowCustomInstallRoot -and -not (Test-SamePath $installRootPath $expectedRoot)) {
    throw "InstallRoot must be the official OpenSprite app path: $expectedRoot"
}
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Port must be between 1024 and 65535." }

$uvicorn = Join-Path $installRootPath "backend\.venv\Scripts\uvicorn.exe"
$backendRoot = Join-Path $installRootPath "backend"
if (-not (Test-Path -LiteralPath $uvicorn -PathType Leaf)) { Write-BootstrapError "Installed Uvicorn executable is missing."; throw "Installed Uvicorn executable is missing." }

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $listener) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if ($process.CommandLine -like "*$installRootPath*" -and $process.CommandLine -like "*opensprite_backend.installed_runtime*") { return }
    Write-BootstrapError "Port $Port is already owned by another process."
    throw "Port $Port is already owned by another process."
}

try {
    Start-Process -FilePath $uvicorn -ArgumentList @(
        "opensprite_backend.installed_runtime:create_installed_app",
        "--factory",
        "--host", "127.0.0.1",
        "--port", $Port,
        "--no-proxy-headers"
    ) -WorkingDirectory $backendRoot -WindowStyle Hidden | Out-Null
}
catch { Write-BootstrapError $_.Exception.Message; throw }
