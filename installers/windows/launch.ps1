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

$installRootPath = Resolve-AbsolutePath $InstallRoot
$expectedRoot = Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
if (-not $AllowCustomInstallRoot -and -not (Test-SamePath $installRootPath $expectedRoot)) {
    throw "InstallRoot must be the official OpenSprite app path: $expectedRoot"
}
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Port must be between 1024 and 65535." }

$uvicorn = Join-Path $installRootPath "backend\.venv\Scripts\uvicorn.exe"
$backendRoot = Join-Path $installRootPath "backend"
if (-not (Test-Path -LiteralPath $uvicorn -PathType Leaf)) { throw "Installed Uvicorn executable is missing." }

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $listener) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if ($process.CommandLine -like "*$installRootPath*" -and $process.CommandLine -like "*opensprite_backend.installed_runtime*") { return }
    throw "Port $Port is already owned by another process."
}

Start-Process -FilePath $uvicorn -ArgumentList @(
    "opensprite_backend.installed_runtime:create_installed_app",
    "--factory",
    "--host", "127.0.0.1",
    "--port", $Port,
    "--no-proxy-headers"
) -WorkingDirectory $backendRoot -WindowStyle Hidden | Out-Null
