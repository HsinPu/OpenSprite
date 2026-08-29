[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [string]$SourceRoot = (Join-Path $PSScriptRoot "..\.."),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "OpenSprite\app"),
    [string]$TaskName = "OpenSprite",
    [int]$Port = 8765,
    [switch]$NoStart,
    [switch]$SkipScheduledTask,
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

function Assert-ChildPath([string]$Path, [string]$Parent) {
    $prefix = $Parent.TrimEnd("\") + "\"
    if (-not $Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the expected parent: $Path"
    }
}

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable"
    }
}

function Copy-RequiredItem([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Required source item is missing: $Source"
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Stop-OpenSpriteTask([string]$Name) {
    $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }
}

function Register-OpenSpriteTask([string]$Root, [string]$Name, [int]$ListenPort) {
    $uvicorn = Join-Path $Root "backend\.venv\Scripts\uvicorn.exe"
    if (-not (Test-Path -LiteralPath $uvicorn -PathType Leaf)) {
        throw "Installed Uvicorn executable is missing: $uvicorn"
    }
    $arguments = "opensprite_backend.installed_runtime:create_installed_app --factory --host 127.0.0.1 --port $ListenPort --no-proxy-headers"
    $action = New-ScheduledTaskAction -Execute $uvicorn -Argument $arguments -WorkingDirectory (Join-Path $Root "backend")
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 3650)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
}

function Wait-OpenSpriteHealth([int]$ListenPort, [int]$TimeoutSeconds = 20) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$ListenPort/healthz" -Headers @{ Host = "127.0.0.1:$ListenPort" }
            $index = Invoke-WebRequest -Uri "http://127.0.0.1:$ListenPort/" -Headers @{ Host = "127.0.0.1:$ListenPort" } -UseBasicParsing
            if ($health.status -eq "ok" -and $index.StatusCode -eq 200 -and $index.Content -match "OpenSprite") {
                return
            }
        }
        catch {
            if ([DateTime]::UtcNow -ge $deadline) { throw }
        }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "OpenSprite did not become healthy before the timeout."
}

$sourceRootPath = Resolve-AbsolutePath $SourceRoot
$installRootPath = Resolve-AbsolutePath $InstallRoot
$expectedRoot = Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
if (-not $AllowCustomInstallRoot -and -not (Test-SamePath $installRootPath $expectedRoot)) {
    throw "InstallRoot must be the official OpenSprite app path: $expectedRoot"
}
if ($SkipScheduledTask -and -not $NoStart) {
    throw "SkipScheduledTask requires NoStart."
}
if ($Port -lt 1024 -or $Port -gt 65535) {
    throw "Port must be between 1024 and 65535."
}
foreach ($required in @("backend\pyproject.toml", "backend\uv.lock", "backend\src", "frontend\package.json", "frontend\package-lock.json", "frontend\src", "frontend\index.html", "frontend\tsconfig.json", "frontend\vite.config.ts")) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRootPath $required))) {
        throw "SourceRoot is not a complete OpenSprite checkout: $required"
    }
}

$installParent = Split-Path -Parent $installRootPath
if (-not $AllowCustomInstallRoot) {
    Assert-ChildPath $installRootPath (Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite"))
}
$stagingRoot = Join-Path $installParent (".app-staging-" + [Guid]::NewGuid().ToString("N"))
$previousRoot = Join-Path $installParent (".app-previous-" + [Guid]::NewGuid().ToString("N"))
$hadPreviousInstall = Test-Path -LiteralPath $installRootPath
$hadPreviousTask = $null -ne (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
$installedNewRoot = $false

if (-not $PSCmdlet.ShouldProcess($installRootPath, "Build and install OpenSprite")) {
    return
}

try {
    New-Item -ItemType Directory -Path $installParent -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $stagingRoot "backend") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $stagingRoot "frontend") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $stagingRoot "installers\windows") -Force | Out-Null

    Copy-RequiredItem (Join-Path $sourceRootPath "backend\src") (Join-Path $stagingRoot "backend")
    foreach ($file in @("pyproject.toml", "uv.lock", "README.md")) {
        Copy-RequiredItem (Join-Path $sourceRootPath "backend\$file") (Join-Path $stagingRoot "backend")
    }
    Copy-RequiredItem (Join-Path $sourceRootPath "frontend\src") (Join-Path $stagingRoot "frontend")
    foreach ($file in @("package.json", "package-lock.json", "index.html", "tsconfig.json", "vite.config.ts", "README.md")) {
        Copy-RequiredItem (Join-Path $sourceRootPath "frontend\$file") (Join-Path $stagingRoot "frontend")
    }
    Copy-RequiredItem (Join-Path $sourceRootPath "installers\windows\install.ps1") (Join-Path $stagingRoot "installers\windows")
    Copy-RequiredItem (Join-Path $sourceRootPath "installers\windows\uninstall.ps1") (Join-Path $stagingRoot "installers\windows")

    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $npmCommand) { $npmCommand = Get-Command npm -ErrorAction Stop }
    Invoke-Checked $npmCommand.Source @("--prefix", (Join-Path $stagingRoot "frontend"), "ci", "--ignore-scripts")
    Invoke-Checked $npmCommand.Source @("--prefix", (Join-Path $stagingRoot "frontend"), "run", "build")
    $nodeModules = Resolve-AbsolutePath (Join-Path $stagingRoot "frontend\node_modules")
    Assert-ChildPath $nodeModules $stagingRoot
    Remove-Item -LiteralPath $nodeModules -Recurse -Force
    if (-not (Test-Path -LiteralPath (Join-Path $stagingRoot "frontend\dist\index.html") -PathType Leaf)) {
        throw "Frontend build did not produce dist/index.html."
    }

    if (-not $SkipScheduledTask) { Stop-OpenSpriteTask $TaskName }
    if ($hadPreviousInstall) { Move-Item -LiteralPath $installRootPath -Destination $previousRoot }
    Move-Item -LiteralPath $stagingRoot -Destination $installRootPath
    $installedNewRoot = $true

    $uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($null -eq $uvCommand) { $uvCommand = Get-Command uv -ErrorAction Stop }
    Invoke-Checked $uvCommand.Source @("sync", "--project", (Join-Path $installRootPath "backend"), "--no-dev")
    $installedPython = Join-Path $installRootPath "backend\.venv\Scripts\python.exe"
    Invoke-Checked $installedPython @("-c", "from opensprite_backend.installed_runtime import default_frontend_dist; assert default_frontend_dist().joinpath('index.html').is_file()")

    if (-not $SkipScheduledTask) {
        Register-OpenSpriteTask $installRootPath $TaskName $Port
        if (-not $NoStart) {
            Start-ScheduledTask -TaskName $TaskName
            Wait-OpenSpriteHealth $Port
        }
    }

    if (Test-Path -LiteralPath $previousRoot) {
        Assert-ChildPath $previousRoot $installParent
        Remove-Item -LiteralPath $previousRoot -Recurse -Force
    }
    [pscustomobject]@{
        InstallRoot = $installRootPath
        TaskName = if ($SkipScheduledTask) { $null } else { $TaskName }
        Started = -not $NoStart
        Url = "http://127.0.0.1:$Port/"
    }
}
catch {
    if (-not $SkipScheduledTask) { Stop-OpenSpriteTask $TaskName }
    if ($installedNewRoot -and (Test-Path -LiteralPath $installRootPath)) {
        Assert-ChildPath $installRootPath $installParent
        Remove-Item -LiteralPath $installRootPath -Recurse -Force
    }
    if (Test-Path -LiteralPath $previousRoot) {
        Move-Item -LiteralPath $previousRoot -Destination $installRootPath
        if (-not $SkipScheduledTask -and $hadPreviousTask) {
            Register-OpenSpriteTask $installRootPath $TaskName $Port
            if (-not $NoStart) { Start-ScheduledTask -TaskName $TaskName }
        }
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Assert-ChildPath $stagingRoot $installParent
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
