[CmdletBinding()]
param(
    [ValidatePattern('^(latest|[0-9]+\.[0-9]+\.[0-9]+)$')][string]$Version = 'latest',
    [switch]$InstallPrerequisites,
    [switch]$InstallGit,
    [switch]$NonInteractive,
    [switch]$SkipBrowserLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-DownloadUri([uri]$Uri) {
    if ($Uri.Scheme -ne 'https' -or $Uri.Port -ne 443 -or $Uri.UserInfo -or
        $Uri.DnsSafeHost -notin @('api.github.com', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com')) {
        throw 'Download destination is not an approved GitHub HTTPS endpoint.'
    }
}

function Save-ReleaseDownload([uri]$Uri, [string]$Destination, [long]$MaxBytes) {
    Add-Type -AssemblyName System.Net.Http
    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.SslProtocols = [Security.Authentication.SslProtocols]::Tls12
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromMinutes(10)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd('OpenSprite-Windows-Installer')
    try {
        for ($redirect = 0; $redirect -le 5; $redirect++) {
            Assert-DownloadUri $Uri
            $response = $client.GetAsync($Uri, [Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
            try {
                if ([int]$response.StatusCode -in @(301,302,303,307,308)) {
                    if ($null -eq $response.Headers.Location) { throw 'Missing redirect destination.' }
                    $Uri = [uri]::new($Uri, $response.Headers.Location)
                    continue
                }
                if (-not $response.IsSuccessStatusCode) { throw "GitHub download failed (HTTP $([int]$response.StatusCode))." }
                if ($response.Content.Headers.ContentLength -gt $MaxBytes) { throw 'Download exceeds size limit.' }
                $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
                $outputStream = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew)
                $deadline = [DateTime]::UtcNow.AddMinutes(10)
                try {
                    $buffer = New-Object byte[] 65536
                    [long]$total = 0
                    while ($true) {
                        $readTask = $inputStream.ReadAsync($buffer, 0, $buffer.Length)
                        if (-not $readTask.Wait(30000)) { throw 'Download stalled.' }
                        $count = $readTask.GetAwaiter().GetResult()
                        if ($count -eq 0) { break }
                        $total += $count
                        if ($total -gt $MaxBytes -or [DateTime]::UtcNow -gt $deadline) { throw 'Download size/time limit exceeded.' }
                        $outputStream.Write($buffer, 0, $count)
                    }
                } finally { $outputStream.Dispose(); $inputStream.Dispose() }
                return
            } finally { $response.Dispose() }
        }
        throw 'Too many GitHub redirects.'
    } finally { $client.Dispose(); $handler.Dispose() }
}

function Test-ReleaseChecksum([string]$Archive, [string]$Checksum, [string]$AssetName) {
    $line = [IO.File]::ReadAllText($Checksum).Trim()
    $match = [regex]::Match($line, '^([a-fA-F0-9]{64})  ' + [regex]::Escape($AssetName) + '$')
    if (-not $match.Success -or (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $match.Groups[1].Value) {
        throw 'Release checksum mismatch. Installation stopped.'
    }
}

function Expand-ReleaseArchive([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $root = [IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
    if (Test-Path -LiteralPath $Destination) { throw 'Extraction destination must not exist.' }
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        if ($zip.Entries.Count -eq 0 -or $zip.Entries.Count -gt 10000) { throw 'Invalid archive entry count.' }
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        [long]$total = 0
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            if ($name.EndsWith('/') -or $name.Contains('\') -or $name.StartsWith('/') -or $name.Contains(':')) { throw 'Invalid ZIP path.' }
            foreach ($part in $name.Split('/')) {
                if (-not $part -or $part -in @('.', '..') -or $part -match '[<>"|?*\x00-\x1f]' -or $part -match '[. ]$' -or $part -match '^(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)') { throw 'Unsafe ZIP path.' }
            }
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $name))
            if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or -not $seen.Add($target)) { throw 'ZIP path escape or duplicate.' }
            $kind = ($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($kind -notin @(0, 0x8000) -or ($entry.ExternalAttributes -band 0x400)) { throw 'ZIP links and special files are not permitted.' }
            $total += $entry.Length
            if ($entry.Length -gt 50MB -or $total -gt 200MB) { throw 'Expanded release exceeds size limit.' }
        }
        New-Item -ItemType Directory -Path $Destination | Out-Null
        foreach ($entry in $zip.Entries) {
            $target = Join-Path $Destination $entry.FullName
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
        }
    } finally { $zip.Dispose() }
}

function Remove-BootstrapTemp([string]$Path) {
    $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    $full = [IO.Path]::GetFullPath($Path)
    if ((Split-Path -Parent $full) -ne $temp -or (Split-Path -Leaf $full) -notmatch '^opensprite-download-[a-f0-9]{32}$') { throw 'Unsafe bootstrap cleanup path.' }
    if (Test-Path -LiteralPath $full) {
        $entries = @((Get-Item -LiteralPath $full)) + @(Get-ChildItem -LiteralPath $full -Force -Recurse)
        if (@($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Refusing to clean reparse-point tree.' }
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

function Get-MissingPrerequisites([bool]$IncludeGit = $false) {
    $missing = @()
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($null -eq $node) { $missing += 'OpenJS.NodeJS.LTS' }
    else {
        & $node.Source -e "const [a,b]=process.versions.node.split('.').map(Number);if(!((a===20&&b>=19)||(a===22&&b>=12)||a>22))process.exit(1)"
        if ($LASTEXITCODE -ne 0) { throw 'Node.js is too old. Upgrade to 22.12+ and rerun; existing tools are not overwritten automatically.' }
        if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { $missing += 'OpenJS.NodeJS.LTS' }
    }
    if (-not (Get-Command uv.exe -ErrorAction SilentlyContinue)) { $missing += 'astral-sh.uv' }
    if ($IncludeGit -and -not (Get-Command git.exe -ErrorAction SilentlyContinue)) { $missing += 'Git.Git' }
    return $missing
}

function Ensure-BootstrapPrerequisites([bool]$Consent, [bool]$Quiet, [bool]$IncludeGit = $false) {
    $missing = @(Get-MissingPrerequisites $IncludeGit)
    if (-not $missing.Count) { return }
    Write-Host "Missing prerequisites: $($missing -join ', ')"
    if (-not $Consent) {
        if ($Quiet) { throw 'Prerequisites missing. Install the listed packages, or explicitly pass -InstallPrerequisites.' }
        $Consent = (Read-Host 'Install these packages using winget? [y/N]') -eq 'y'
    }
    if (-not $Consent) { throw 'Prerequisite installation declined. No application changes made.' }
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($null -eq $winget) { throw 'winget is unavailable. Install the listed packages manually, reopen PowerShell and retry.' }
    foreach ($id in $missing) {
        & $winget.Source install --id $id --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) { throw "Prerequisite installation failed: $id. Reopen PowerShell after resolving it." }
    }
    $env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:PATH
    if (@(Get-MissingPrerequisites $IncludeGit).Count) { throw 'Tools are not yet on PATH. Reopen PowerShell and retry.' }
}

function Invoke-OpenSpriteBootstrap {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'This installer supports Windows only.' }
    $mutex = [Threading.Mutex]::new($false, 'Local\OpenSprite.Windows.Install')
    $held = $false
    $temp = $null
    $stage = 'preflight'
    $failed = $false
    try {
        try { $held = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $held = $true }
        if (-not $held) { throw 'Another OpenSprite installation is running.' }
        Write-Host '[1/6] Checking prerequisites'
        Ensure-BootstrapPrerequisites ([bool]$InstallPrerequisites) ([bool]$NonInteractive) ([bool]$InstallGit)
        $temp = Join-Path ([IO.Path]::GetTempPath()) ('opensprite-download-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $temp | Out-Null
        $stage = 'release metadata'
        Write-Host '[2/6] Resolving and downloading the release'
        $api = if ($Version -eq 'latest') { 'https://api.github.com/repos/HsinPu/OpenSprite/releases/latest' } else { "https://api.github.com/repos/HsinPu/OpenSprite/releases/tags/v$Version" }
        $metadata = Join-Path $temp 'release.json'
        Save-ReleaseDownload ([uri]$api) $metadata 2MB
        $release = Get-Content -LiteralPath $metadata -Raw | ConvertFrom-Json
        if ($release.draft -or $release.prerelease -or $release.tag_name -notmatch '^v([0-9]+\.[0-9]+\.[0-9]+)$') { throw 'A stable versioned Release is required.' }
        $resolved = $Matches[1]
        if ($Version -ne 'latest' -and $Version -ne $resolved) { throw 'Release version mismatch.' }
        $asset = "OpenSprite-$resolved-windows.zip"
        foreach ($name in @($asset, "$asset.sha256")) {
            if (@($release.assets | Where-Object { $_.name -ceq $name }).Count -ne 1) { throw "Release asset missing: $name" }
            Save-ReleaseDownload ([uri]"https://github.com/HsinPu/OpenSprite/releases/download/v$resolved/$name") (Join-Path $temp $name) $(if ($name.EndsWith('.zip')) { 100MB } else { 1024 })
        }
        $stage = 'validation'
        Write-Host '[3/6] Verifying checksum and extracting'
        Test-ReleaseChecksum (Join-Path $temp $asset) (Join-Path $temp "$asset.sha256") $asset
        $source = Join-Path $temp 'source'
        Expand-ReleaseArchive (Join-Path $temp $asset) $source
        $manifest = Get-Content -LiteralPath (Join-Path $source 'release-source.json') -Raw | ConvertFrom-Json
        if ($manifest.version -ne $resolved -or $manifest.revision -notmatch '^[a-f0-9]{40}$') { throw 'Release provenance mismatch.' }
        $stage = 'installation'
        Write-Host "[4/6] Installing OpenSprite $resolved (startup and health checks included)"
        & (Join-Path $source 'installers\windows\install.ps1') -SourceRoot $source -SkipBrowserLaunch:$SkipBrowserLaunch
        Write-Host '[5/6] Installation and health checks completed'
    } catch {
        $failed = $true
        # Do not persist exception bodies, signed download URLs, or credentials.
        Write-Warning "Installation stopped during $stage. Existing installer recovery applies if cutover began."
        throw
    } finally {
        if ($null -ne $temp) {
            Write-Host '[6/6] Cleaning download temporary files'
            try {
                Remove-BootstrapTemp $temp
                if ($failed) {
                    New-Item -ItemType Directory -Path $temp | Out-Null
                    [IO.File]::WriteAllText((Join-Path $temp 'failure.txt'), "OpenSprite installation failed during: $stage. See console for recovery warnings. No credentials are recorded.")
                    Write-Warning "Failure stage recorded at: $temp\failure.txt"
                }
            } catch { Write-Warning "Temporary files retained for manual inspection: $temp" }
        }
        if ($held) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

if ($MyInvocation.InvocationName -ne '.') { Invoke-OpenSpriteBootstrap }
