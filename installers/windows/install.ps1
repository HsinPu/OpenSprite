[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [string]$SourceRoot,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "OpenSprite\app"),
    [string]$StartupName = "OpenSprite",
    [int]$Port = 8765,
    [switch]$NoStart,
    [switch]$InstallPrerequisites,
    [switch]$InstallGit,
    [switch]$NonInteractive,
    [switch]$ResetLocalAccess,
    [ValidateSet("TrustedLocal", "Password")][string]$AccessMode,
    [string]$UserDataRoot = (Join-Path $env:USERPROFILE ".opensprite"),
    [switch]$SkipStartupRegistration,
    [switch]$AllowCustomInstallRoot,
    [switch]$AllowCustomUserDataRoot,
    [switch]$SkipAccessBootstrap,
    [switch]$SkipBrowserLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ([String]::IsNullOrWhiteSpace($SourceRoot)) { $SourceRoot = Join-Path $PSScriptRoot "..\.." }
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

function Get-InstallTool([string[]]$Names, [string]$Hint) {
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command }
    }
    throw "Missing prerequisite: $Hint. Install it and reopen PowerShell before retrying."
}

function Invoke-RecoveryStep([string]$Name, [scriptblock]$Action) {
    try { & $Action | Out-Null; return $true }
    catch { Write-Warning "Rollback step failed ($Name): $($_.Exception.Message)"; return $false }
}

function Restore-ApplicationRoot([string]$Root, [string]$Previous, [string]$Parent, [bool]$NewRootInstalled) {
    Assert-ChildPath $Root $Parent
    Assert-ChildPath $Previous $Parent
    if ($NewRootInstalled -and (Test-Path -LiteralPath $Root)) {
        # Rename instead of deleting locked native binaries before restoring the old app.
        $failedRoot = Join-Path $Parent (".app-failed-" + [Guid]::NewGuid().ToString("N"))
        Assert-ChildPath $failedRoot $Parent
        [IO.Directory]::Move($Root, $failedRoot)
        Write-Warning "Failed installation retained for recovery: $failedRoot"
    }
    if (Test-Path -LiteralPath $Previous) {
        [IO.Directory]::Move($Previous, $Root)
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

function Get-PreviousStartupPort([string]$StartupValue) {
    # Read the numeric switch only; never execute registry text.
    $match = [regex]::Match($StartupValue, '(?i)(?:^|\s)-Port\s+(\d+)(?=\s|$)')
    if (-not $match.Success) { return 8765 }
    $value = 0
    if (-not [int]::TryParse($match.Groups[1].Value, [ref]$value) -or $value -lt 1024 -or $value -gt 65535) {
        throw "Previous startup port is invalid; refusing to replace the installation."
    }
    return $value
}

function Stop-InstalledRuntime([string]$Root) {
    $escapedRoot = [Regex]::Escape($Root)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match $escapedRoot -and $_.CommandLine -match "opensprite_backend\.installed_runtime"
    } | ForEach-Object {
        $runtime = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        if ($null -ne $runtime) {
            Stop-Process -InputObject $runtime -Force -ErrorAction Stop
            if (-not $runtime.WaitForExit(10000)) { throw "OpenSprite runtime did not exit within 10 seconds." }
        }
    }
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
                Write-Warning "A temporary installation directory remains locked: $Path"
                return $false
            }
            Start-Sleep -Milliseconds 250
        }
    }
    return $false
}

function Wait-OpenSpriteHealth([int]$ListenPort, [int]$TimeoutSeconds = 300) {
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

function Clear-PreviousInstallations([string]$Parent, [string]$CurrentPrevious) {
    foreach ($item in Get-ChildItem -LiteralPath $Parent -Directory -Force) {
        if ($item.Name -notmatch '^\.app-previous-[a-f0-9]{32}$' -or $item.FullName -eq $CurrentPrevious) { continue }
        Assert-ChildPath $item.FullName $Parent
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        $info = Join-Path $item.FullName 'build-info.json'
        if (-not (Test-Path -LiteralPath $info -PathType Leaf)) { continue }
        try {
            if (@(Get-ChildItem -LiteralPath $item.FullName -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { continue }
            $record = Get-Content -LiteralPath $info -Raw | ConvertFrom-Json
            if ($record.version -notmatch '^\d+\.\d+\.\d+$' -or -not $record.installedAt -or -not (Test-Path -LiteralPath (Join-Path $item.FullName 'installers\windows\launch.ps1'))) { continue }
            $null = Remove-DirectoryWithRetry $item.FullName $Parent -Attempts 4
        } catch { Write-Warning "Previous installation retained: $($item.FullName)" }
    }
}

$installMutex = [Threading.Mutex]::new($false, 'Local\OpenSprite.Windows.Install')
$installLockHeld = $false
try {
try { $installLockHeld = $installMutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $installLockHeld = $true }
if (-not $installLockHeld) { throw 'Another OpenSprite installation is running.' }
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
if ($ResetLocalAccess -and $AccessMode -eq "TrustedLocal") { throw "ResetLocalAccess cannot be combined with TrustedLocal mode." }
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
$accessPath = Join-Path $userDataRootPath "config\access.json"
$bootstrapPath = Join-Path $userDataRootPath "state\access-bootstrap.json"
$policyPath = Join-Path $userDataRootPath "config\access-policy.json"
$selectedAccessMode = $AccessMode
if ([String]::IsNullOrWhiteSpace($selectedAccessMode)) {
    if (Test-Path -LiteralPath $policyPath -PathType Leaf) {
        try { $existingPolicy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json }
        catch { throw "Existing access policy is malformed." }
        $propertyNames = @($existingPolicy.PSObject.Properties.Name)
        if ($propertyNames.Count -ne 2 -or $propertyNames -notcontains "version" -or $propertyNames -notcontains "mode" -or $existingPolicy.version -ne 1 -or $existingPolicy.mode -notin @("trusted_local", "password_required")) { throw "Existing access policy is malformed." }
        $selectedAccessMode = if ($existingPolicy.mode -eq "trusted_local") { "TrustedLocal" } else { "Password" }
    }
    elseif ((Test-Path -LiteralPath $accessPath -PathType Leaf) -or (Test-Path -LiteralPath $bootstrapPath -PathType Leaf)) { $selectedAccessMode = "Password" }
    else { $selectedAccessMode = "TrustedLocal" }
}
$pyprojectText = Get-Content -LiteralPath (Join-Path $sourceRootPath "backend\pyproject.toml") -Raw
$versionMatch = [Regex]::Match($pyprojectText, '(?m)^version\s*=\s*"([^\"]+)"\s*$')
if (-not $versionMatch.Success) { throw "Unable to resolve the OpenSprite product version." }
$productVersion = $versionMatch.Groups[1].Value
$revision = "unknown"
$dirty = $true
$releaseSourcePath = Join-Path $sourceRootPath 'release-source.json'
if (Test-Path -LiteralPath $releaseSourcePath -PathType Leaf) {
    $releaseSource = Get-Content -LiteralPath $releaseSourcePath -Raw | ConvertFrom-Json
    if ($releaseSource.version -ne $productVersion -or $releaseSource.revision -notmatch '^[a-f0-9]{40}$') { throw 'Invalid release source metadata.' }
    $revision = $releaseSource.revision.Substring(0, 8)
    $dirty = $false
}
$gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
if ($null -eq $gitCommand) { $gitCommand = Get-Command git -ErrorAction SilentlyContinue }
if ($null -ne $gitCommand -and -not (Test-Path -LiteralPath $releaseSourcePath)) {
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
$preparedEnvironment = Join-Path $installParent (".app-prepared-" + [Guid]::NewGuid().ToString("N"))
$previousRoot = Join-Path $installParent (".app-previous-" + [Guid]::NewGuid().ToString("N"))
$hadPreviousInstall = Test-Path -LiteralPath $installRootPath
$previousStartupValue = Get-OpenSpriteStartup $StartupName
$previousPort = Get-PreviousStartupPort ([string]$previousStartupValue)
$installedNewRoot = $false
$cutoverStarted = $false
$previousCleanupComplete = $true
$previousPolicyBytes = if (Test-Path -LiteralPath $policyPath -PathType Leaf) { [IO.File]::ReadAllBytes($policyPath) } else { $null }
$previousAccessBytes = if (Test-Path -LiteralPath $accessPath -PathType Leaf) { [IO.File]::ReadAllBytes($accessPath) } else { $null }
$previousBootstrapBytes = if (Test-Path -LiteralPath $bootstrapPath -PathType Leaf) { [IO.File]::ReadAllBytes($bootstrapPath) } else { $null }
$policyMutated = $false
$bootstrapMutated = $false
$accessMutated = $false

if (-not $PSCmdlet.ShouldProcess($installRootPath, "Build and install OpenSprite")) {
    return
}

# Scope bootstrap parameters locally; dot sourcing never downloads a release.
& {
    param($Consent, $Quiet, $IncludeGit)
    . (Join-Path $PSScriptRoot "bootstrap.ps1")
    Ensure-BootstrapPrerequisites $Consent $Quiet $IncludeGit
} ([bool]$InstallPrerequisites) ([bool]$NonInteractive) ([bool]$InstallGit)

# Resolve and exercise prerequisites before creating staging or stopping an existing app.
$nodeCommand = Get-InstallTool @("node.exe", "node") "Node.js (^20.19.0 or >=22.12.0)"
$npmCommand = Get-InstallTool @("npm.cmd", "npm") "npm (included with Node.js)"
$uvCommand = Get-InstallTool @("uv.exe", "uv") "uv"
Invoke-Checked $nodeCommand.Source @("-e", "const [a,b]=process.versions.node.split('.').map(Number);if(!((a===20&&b>=19)||(a===22&&b>=12)||a>22))process.exit(1)")
Invoke-Checked $npmCommand.Source @("--version")
Invoke-Checked $uvCommand.Source @("--version")

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
    Copy-RequiredItem (Join-Path $sourceRootPath "installers\windows\bootstrap.ps1") (Join-Path $stagingRoot "installers\windows")
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

    Invoke-Checked $npmCommand.Source @("--prefix", (Join-Path $stagingRoot "frontend"), "ci", "--ignore-scripts")
    Invoke-Checked $npmCommand.Source @("--prefix", (Join-Path $stagingRoot "frontend"), "run", "build")
    $nodeModules = Resolve-AbsolutePath (Join-Path $stagingRoot "frontend\node_modules")
    Assert-ChildPath $nodeModules $stagingRoot
    Remove-Item -LiteralPath $nodeModules -Recurse -Force
    if (-not (Test-Path -LiteralPath (Join-Path $stagingRoot "frontend\dist\index.html") -PathType Leaf)) {
        throw "Frontend build did not produce dist/index.html."
    }

    # Resolve/download/build Python dependencies before stopping the old service.
    # Virtual environments embed absolute paths, so recreate at the final path
    # using the warmed cache instead of moving the staging environment.
    $previousProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
    try {
        $env:UV_PROJECT_ENVIRONMENT = $preparedEnvironment
        Invoke-Checked $uvCommand.Source @("sync", "--project", (Join-Path $stagingRoot "backend"), "--no-dev", "--frozen")
    } finally { $env:UV_PROJECT_ENVIRONMENT = $previousProjectEnvironment }

    if (-not $SkipStartupRegistration) {
        $cutoverStarted = $true
        Remove-OpenSpriteStartup $StartupName
        if ($hadPreviousInstall) { Stop-InstalledRuntime $installRootPath }
    }

    $policyMode = if ($selectedAccessMode -eq "TrustedLocal") { "trusted_local" } else { "password_required" }
    $policyMutated = $true
    Set-LocalAccessPolicy $userDataRootPath $policyMode
    if ($selectedAccessMode -eq "TrustedLocal" -and (Test-Path -LiteralPath $bootstrapPath -PathType Leaf)) {
        Remove-Item -LiteralPath $bootstrapPath -Force
        $bootstrapMutated = $true
    }
    if ($hadPreviousInstall) { Move-Item -LiteralPath $installRootPath -Destination $previousRoot }
    Move-Item -LiteralPath $stagingRoot -Destination $installRootPath
    $installedNewRoot = $true

    Invoke-Checked $uvCommand.Source @("sync", "--project", (Join-Path $installRootPath "backend"), "--no-dev", "--frozen")
    $installedPython = Join-Path $installRootPath "backend\.venv\Scripts\python.exe"
    Invoke-Checked $installedPython @("-c", "from opensprite_backend.installed_runtime import default_frontend_dist; assert default_frontend_dist().joinpath('index.html').is_file()")
    $installedVersion = (& $installedPython -c "from importlib.metadata import version; print(version('opensprite-backend'))").Trim()
    if ($LASTEXITCODE -ne 0 -or $installedVersion -ne $productVersion) {
        throw "Installed package version does not match build metadata."
    }

    if (-not $SkipStartupRegistration) {
        Register-OpenSpriteStartup $installRootPath $StartupName $Port
        if (-not $NoStart) {
            & (Join-Path $installRootPath "installers\windows\launch.ps1") -InstallRoot $installRootPath -Port $Port -AllowCustomInstallRoot:$AllowCustomInstallRoot
            Wait-OpenSpriteHealth $Port
        }
    }

    $needsBootstrap = $selectedAccessMode -eq "Password" -and ($ResetLocalAccess -or -not (Test-Path -LiteralPath $accessPath -PathType Leaf))
    if ($needsBootstrap -and -not $SkipAccessBootstrap) {
        if ($NoStart) { throw "A new local access password must be configured while OpenSprite is running. Remove -NoStart or use the isolated-test bootstrap bypass." }
        $bootstrapMutated = $true
        $accessMutated = $ResetLocalAccess
        $bootstrapToken = New-LocalAccessBootstrap $userDataRootPath -Reset:$ResetLocalAccess
        try {
            if (-not $SkipBrowserLaunch) {
                Start-Process -FilePath "http://localhost:$Port/#setup=$bootstrapToken"
            }
        }
        finally { $bootstrapToken = $null }
    }
    elseif ($selectedAccessMode -eq "TrustedLocal" -and -not $NoStart -and -not $SkipBrowserLaunch) {
        Start-Process -FilePath "http://localhost:$Port/"
    }

    if (Test-Path -LiteralPath $previousRoot) {
        $previousCleanupComplete = Remove-DirectoryWithRetry $previousRoot $installParent
    }
    if (-not $NoStart) {
        try { Clear-PreviousInstallations $installParent $previousRoot }
        catch { Write-Warning 'Installation is healthy; older backup cleanup could not be completed.' }
    }
    [pscustomobject]@{
        InstallRoot = $installRootPath
        StartupName = if ($SkipStartupRegistration) { $null } else { $StartupName }
        Started = -not $NoStart
        PreviousCleanupComplete = $previousCleanupComplete
        Version = $productVersion
        Revision = $revision
        Dirty = [bool]$dirty
        AccessMode = $selectedAccessMode
        Url = "http://localhost:$Port/"
    }
}
catch {
    $failure = $_
    if (-not $SkipStartupRegistration -and $cutoverStarted) {
        $null = Invoke-RecoveryStep "remove startup" { Remove-OpenSpriteStartup $StartupName }
        $runtimeStopped = Invoke-RecoveryStep "stop failed runtime" { Stop-InstalledRuntime $installRootPath }
        if (-not $runtimeStopped) {
            Write-Warning "Runtime shutdown could not be confirmed. Application and access-state rollback were skipped; backups are retained for manual recovery."
            throw $failure
        }
    }
    $rootRestored = Invoke-RecoveryStep "restore application (backup: $previousRoot)" { Restore-ApplicationRoot $installRootPath $previousRoot $installParent $installedNewRoot }
    $stateRestored = $true
    if ($policyMutated) {
      $ok = Invoke-RecoveryStep "restore access policy" {
        if ($null -eq $previousPolicyBytes) { if (Test-Path -LiteralPath $policyPath) { Remove-Item -LiteralPath $policyPath -Force -ErrorAction Stop } }
        else { [IO.File]::WriteAllBytes($policyPath, $previousPolicyBytes) }
      }
      $stateRestored = $stateRestored -and $ok
    }
    if ($bootstrapMutated) {
      $ok = Invoke-RecoveryStep "restore bootstrap" {
        if ($null -eq $previousBootstrapBytes) { if (Test-Path -LiteralPath $bootstrapPath) { Remove-Item -LiteralPath $bootstrapPath -Force -ErrorAction Stop } }
        else {
            New-Item -ItemType Directory -Path (Split-Path -Parent $bootstrapPath) -Force | Out-Null
            [IO.File]::WriteAllBytes($bootstrapPath, $previousBootstrapBytes)
        }
      }
      $stateRestored = $stateRestored -and $ok
    }
    if ($accessMutated) {
      $ok = Invoke-RecoveryStep "restore access" {
        if ($null -eq $previousAccessBytes) { if (Test-Path -LiteralPath $accessPath) { Remove-Item -LiteralPath $accessPath -Force -ErrorAction Stop } }
        else {
            New-Item -ItemType Directory -Path (Split-Path -Parent $accessPath) -Force | Out-Null
            [IO.File]::WriteAllBytes($accessPath, $previousAccessBytes)
        }
      }
      $stateRestored = $stateRestored -and $ok
    }
    if (-not $SkipStartupRegistration -and $cutoverStarted -and $null -ne $previousStartupValue -and $rootRestored -and $stateRestored -and (Test-Path -LiteralPath $installRootPath)) {
        $null = Invoke-RecoveryStep "restore startup" { Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $StartupName -Value $previousStartupValue }
        if (-not $NoStart -and $runtimeStopped) {
            $null = Invoke-RecoveryStep "restart previous runtime" { & (Join-Path $installRootPath "installers\windows\launch.ps1") -InstallRoot $installRootPath -Port $previousPort -AllowCustomInstallRoot:$AllowCustomInstallRoot }
        }
    }
    throw $failure
}
finally {
    if (Test-Path -LiteralPath $preparedEnvironment) {
        $null = Remove-DirectoryWithRetry $preparedEnvironment $installParent -Attempts 4
    }
    if (Test-Path -LiteralPath $stagingRoot) {
        Assert-ChildPath $stagingRoot $installParent
        $null = Invoke-RecoveryStep "clean staging" { Remove-Item -LiteralPath $stagingRoot -Recurse -Force }
    }
}
} finally {
    if ($installLockHeld) { $installMutex.ReleaseMutex() }
    $installMutex.Dispose()
}
