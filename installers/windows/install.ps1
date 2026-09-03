[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [string]$SourceRoot = (Join-Path $PSScriptRoot "..\.."),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "OpenSprite\app"),
    [string]$StartupName = "OpenSprite",
    [int]$Port = 8765,
    [switch]$NoStart,
    [switch]$ResetLocalAccess,
    [string]$UserDataRoot = (Join-Path $env:USERPROFILE ".opensprite"),
    [switch]$SkipStartupRegistration,
    [switch]$AllowCustomInstallRoot,
    [switch]$AllowCustomUserDataRoot,
    [switch]$SkipAccessBootstrap,
    [switch]$SkipBrowserLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "access.ps1")

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

function Get-OpenSpriteStartup([string]$Name) {
    $runPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $item = Get-ItemProperty -Path $runPath -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $item) { return $null }
    return $item.PSObject.Properties[$Name].Value
}

function Remove-OpenSpriteStartup([string]$Name) {
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $Name -ErrorAction SilentlyContinue
}

function New-OpenSpriteStartupValue([string]$Root, [int]$ListenPort) {
    $launcher = Join-Path $Root "installers\windows\launch.ps1"
    $powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
    $value = "`"$powershell`" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$launcher`""
    $expectedRoot = Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
    if (-not (Test-SamePath $Root $expectedRoot)) {
        $value += " -InstallRoot `"$Root`" -AllowCustomInstallRoot"
    }
    if ($ListenPort -ne 8765) {
        $value += " -Port $ListenPort"
    }
    return $value
}

function Register-OpenSpriteStartup([string]$Root, [string]$Name, [int]$ListenPort) {
    $launcher = Join-Path $Root "installers\windows\launch.ps1"
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Installed launcher is missing." }
    $value = New-OpenSpriteStartupValue $Root $ListenPort
    if ($value.Length -gt 260) {
        throw "OpenSprite Run command exceeds the Windows 260-character limit."
    }
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $Name -Value $value
}

function Stop-InstalledRuntime([string]$Root) {
    $escapedRoot = [Regex]::Escape($Root)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match $escapedRoot -and $_.CommandLine -match "opensprite_backend\.installed_runtime"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Remove-DirectoryWithRetry([string]$Path, [string]$Parent, [int]$Attempts = 120) {
    Assert-ChildPath $Path $Parent
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return $true
        }
        catch {
            if ($attempt -eq $Attempts) {
                Write-Warning "Installed successfully, but a temporary rollback directory remains locked: $Path"
                return $false
            }
            Start-Sleep -Milliseconds 250
        }
    }
    return $false
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
$userDataRootPath = Resolve-AbsolutePath $UserDataRoot
$expectedRoot = Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite\app")
$expectedUserDataRoot = Resolve-AbsolutePath (Join-Path $env:USERPROFILE ".opensprite")
if (-not $AllowCustomInstallRoot -and -not (Test-SamePath $installRootPath $expectedRoot)) {
    throw "InstallRoot must be the official OpenSprite app path: $expectedRoot"
}
if (-not $AllowCustomUserDataRoot -and -not (Test-SamePath $userDataRootPath $expectedUserDataRoot)) {
    throw "UserDataRoot must be the official OpenSprite data path: $expectedUserDataRoot"
}
if ($ResetLocalAccess -and -not (Test-SamePath $userDataRootPath $expectedUserDataRoot)) {
    throw "ResetLocalAccess is restricted to the official OpenSprite data path: $expectedUserDataRoot"
}
if ($SkipAccessBootstrap -and (-not $AllowCustomUserDataRoot -or -not $NoStart)) {
    throw "SkipAccessBootstrap is reserved for non-starting isolated tests with a custom user-data root."
}
if ($ResetLocalAccess -and $SkipAccessBootstrap) { throw "ResetLocalAccess cannot be combined with SkipAccessBootstrap." }
if ($SkipStartupRegistration -and -not $NoStart) {
    throw "SkipStartupRegistration requires NoStart."
}
if ($Port -lt 1024 -or $Port -gt 65535) {
    throw "Port must be between 1024 and 65535."
}
foreach ($required in @("backend\pyproject.toml", "backend\uv.lock", "backend\src", "frontend\package.json", "frontend\package-lock.json", "frontend\src", "frontend\index.html", "frontend\tsconfig.json", "frontend\vite.config.ts")) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRootPath $required))) {
        throw "SourceRoot is not a complete OpenSprite checkout: $required"
    }
}
$pyprojectText = Get-Content -LiteralPath (Join-Path $sourceRootPath "backend\pyproject.toml") -Raw
$versionMatch = [Regex]::Match($pyprojectText, '(?m)^version\s*=\s*"([^\"]+)"\s*$')
if (-not $versionMatch.Success) { throw "Unable to resolve the OpenSprite product version." }
$productVersion = $versionMatch.Groups[1].Value
$revision = "unknown"
$dirty = $true
$gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
if ($null -eq $gitCommand) { $gitCommand = Get-Command git -ErrorAction SilentlyContinue }
if ($null -ne $gitCommand) {
    $gitSafeDirectory = $sourceRootPath.Replace("\", "/")
    $resolvedRevision = (& $gitCommand.Source -c "safe.directory=$gitSafeDirectory" -C $sourceRootPath rev-parse --short=8 HEAD 2>$null)
    if ($LASTEXITCODE -eq 0 -and -not [String]::IsNullOrWhiteSpace($resolvedRevision)) {
        $revision = $resolvedRevision.Trim().ToLowerInvariant()
        $gitStatus = (& $gitCommand.Source -c "safe.directory=$gitSafeDirectory" -C $sourceRootPath status --porcelain -- `
            backend/src backend/pyproject.toml backend/uv.lock `
            frontend/src frontend/package.json frontend/package-lock.json `
            frontend/index.html frontend/tsconfig.json frontend/vite.config.ts `
            installers/windows 2>$null)
        $dirty = $LASTEXITCODE -ne 0 -or -not [String]::IsNullOrWhiteSpace(($gitStatus -join "`n"))
    }
}

$installParent = Split-Path -Parent $installRootPath
if (-not $AllowCustomInstallRoot) {
    Assert-ChildPath $installRootPath (Resolve-AbsolutePath (Join-Path $env:LOCALAPPDATA "OpenSprite"))
}
$stagingRoot = Join-Path $installParent (".app-staging-" + [Guid]::NewGuid().ToString("N"))
$previousRoot = Join-Path $installParent (".app-previous-" + [Guid]::NewGuid().ToString("N"))
$hadPreviousInstall = Test-Path -LiteralPath $installRootPath
$previousStartupValue = Get-OpenSpriteStartup $StartupName
$installedNewRoot = $false
$cutoverStarted = $false
$previousCleanupComplete = $true

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
    Copy-RequiredItem (Join-Path $sourceRootPath "installers\windows\access.ps1") (Join-Path $stagingRoot "installers\windows")
    Copy-RequiredItem (Join-Path $sourceRootPath "installers\windows\launch.ps1") (Join-Path $stagingRoot "installers\windows")
    Copy-RequiredItem (Join-Path $sourceRootPath "installers\windows\uninstall.ps1") (Join-Path $stagingRoot "installers\windows")
    $installedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $buildInfo = [ordered]@{
        version = $productVersion
        revision = $revision
        dirty = [bool]$dirty
        installedAt = $installedAt
    } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText(
        (Join-Path $stagingRoot "build-info.json"),
        $buildInfo,
        [Text.UTF8Encoding]::new($false)
    )

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

    if (-not $SkipStartupRegistration) {
        $cutoverStarted = $true
        Remove-OpenSpriteStartup $StartupName
        if ($hadPreviousInstall) { Stop-InstalledRuntime $installRootPath }
    }
    if ($hadPreviousInstall) { Move-Item -LiteralPath $installRootPath -Destination $previousRoot }
    Move-Item -LiteralPath $stagingRoot -Destination $installRootPath
    $installedNewRoot = $true

    $uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($null -eq $uvCommand) { $uvCommand = Get-Command uv -ErrorAction Stop }
    Invoke-Checked $uvCommand.Source @("sync", "--project", (Join-Path $installRootPath "backend"), "--no-dev")
    $installedPython = Join-Path $installRootPath "backend\.venv\Scripts\python.exe"
    Invoke-Checked $installedPython @("-c", "from opensprite_backend.installed_runtime import default_frontend_dist; assert default_frontend_dist().joinpath('index.html').is_file()")
    $installedVersion = (& $installedPython -c "from importlib.metadata import version; print(version('opensprite-backend'))").Trim()
    if ($LASTEXITCODE -ne 0 -or $installedVersion -ne $productVersion) {
        throw "Installed package version does not match build metadata."
    }

    if (-not $SkipStartupRegistration) {
        Register-OpenSpriteStartup $installRootPath $StartupName $Port
        if (-not $NoStart) {
            & (Join-Path $installRootPath "installers\windows\launch.ps1") -InstallRoot $installRootPath -Port $Port
            Wait-OpenSpriteHealth $Port
        }
    }

    $accessPath = Join-Path $userDataRootPath "config\access.json"
    $needsBootstrap = $ResetLocalAccess -or -not (Test-Path -LiteralPath $accessPath -PathType Leaf)
    if ($needsBootstrap -and -not $SkipAccessBootstrap) {
        if ($NoStart) { throw "A new local access password must be configured while OpenSprite is running. Remove -NoStart or use the isolated-test bootstrap bypass." }
        $bootstrapToken = New-LocalAccessBootstrap $userDataRootPath -Reset:$ResetLocalAccess
        try {
            if (-not $SkipBrowserLaunch) {
                Start-Process -FilePath "http://localhost:$Port/#setup=$bootstrapToken"
            }
        }
        finally { $bootstrapToken = $null }
    }

    if (Test-Path -LiteralPath $previousRoot) {
        $previousCleanupComplete = Remove-DirectoryWithRetry $previousRoot $installParent
    }
    [pscustomobject]@{
        InstallRoot = $installRootPath
        StartupName = if ($SkipStartupRegistration) { $null } else { $StartupName }
        Started = -not $NoStart
        PreviousCleanupComplete = $previousCleanupComplete
        Version = $productVersion
        Revision = $revision
        Dirty = [bool]$dirty
        Url = "http://localhost:$Port/"
    }
}
catch {
    $failure = $_
    if (-not $SkipStartupRegistration -and $cutoverStarted) {
        Remove-OpenSpriteStartup $StartupName
        Stop-InstalledRuntime $installRootPath
    }
    if ($installedNewRoot -and (Test-Path -LiteralPath $installRootPath)) {
        Assert-ChildPath $installRootPath $installParent
        Remove-Item -LiteralPath $installRootPath -Recurse -Force
    }
    if (Test-Path -LiteralPath $previousRoot) {
        Move-Item -LiteralPath $previousRoot -Destination $installRootPath
    }
    if (-not $SkipStartupRegistration -and $cutoverStarted -and $null -ne $previousStartupValue -and (Test-Path -LiteralPath $installRootPath)) {
        Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $StartupName -Value $previousStartupValue
        if (-not $NoStart) {
            & (Join-Path $installRootPath "installers\windows\launch.ps1") -InstallRoot $installRootPath -Port $Port
        }
    }
    throw $failure
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Assert-ChildPath $stagingRoot $installParent
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
