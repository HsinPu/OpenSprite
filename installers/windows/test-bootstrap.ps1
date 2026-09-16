[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap.ps1')
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Assert-Rejected([scriptblock]$Action) {
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    Assert-True $rejected 'Expected operation to be rejected.'
}
function New-TestZip([string]$Path, [hashtable]$Files, [int]$Attributes = 0) {
    $zip = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $Files.Keys) {
            $entry = $zip.CreateEntry($name)
            $entry.ExternalAttributes = $Attributes
            $writer = [IO.StreamWriter]::new($entry.Open())
            try { $writer.Write($Files[$name]) } finally { $writer.Dispose() }
        }
    } finally { $zip.Dispose() }
}

$root = Join-Path ([IO.Path]::GetTempPath()) ('opensprite-download-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    foreach ($file in @('bootstrap.ps1','package.ps1','install.ps1')) {
        $tokens = $null; $errors = $null
        [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file), [ref]$tokens, [ref]$errors) | Out-Null
        Assert-True ($errors.Count -eq 0) "Parser errors in $file : $errors"
    }
    Assert-DownloadUri ([uri]'https://github.com/HsinPu/OpenSprite/releases/latest')
    foreach ($uri in @('http://github.com/a','https://evil.example/a','https://github.com:444/a','https://user@github.com/a')) {
        Assert-Rejected { Assert-DownloadUri ([uri]$uri) }
    }
    $archive = Join-Path $root 'valid.zip'
    New-TestZip $archive @{ 'folder/file.txt'='hello' }
    $checksum = Join-Path $root 'valid.zip.sha256'
    [IO.File]::WriteAllText($checksum, ((Get-FileHash $archive).Hash + '  valid.zip'))
    Test-ReleaseChecksum $archive $checksum 'valid.zip'
    Assert-Rejected { Test-ReleaseChecksum $archive $checksum 'other.zip' }
    [IO.File]::WriteAllText($checksum, (('0' * 64) + '  valid.zip'))
    Assert-Rejected { Test-ReleaseChecksum $archive $checksum 'valid.zip' }
    Expand-ReleaseArchive $archive (Join-Path $root 'safe')
    Assert-True ((Get-Content (Join-Path $root 'safe/folder/file.txt') -Raw) -eq 'hello') 'Archive content mismatch.'
    Assert-Rejected { Expand-ReleaseArchive $archive (Join-Path $root 'safe') }
    $i = 0
    foreach ($name in @('../escape','/root','C:/escape','a\escape','a/../b','a//b','a/NUL.txt','a/file.','a/file:stream','a/')) {
        $bad = Join-Path $root "bad-$i.zip"
        New-TestZip $bad @{ $name='bad' }
        Assert-Rejected { Expand-ReleaseArchive $bad (Join-Path $root "bad-$i") }
        $i++
    }
    $bad = Join-Path $root 'link.zip'
    New-TestZip $bad @{ 'link'='target' } ([int]0xA0000000)
    Assert-Rejected { Expand-ReleaseArchive $bad (Join-Path $root 'link') }
    $bad = Join-Path $root 'corrupt.zip'
    [IO.File]::WriteAllText($bad, 'not zip')
    Assert-Rejected { Expand-ReleaseArchive $bad (Join-Path $root 'corrupt') }
    Assert-Rejected { Remove-BootstrapTemp (Split-Path -Parent $root) }
    & {
        function Get-MissingPrerequisites { return 'test.missing' }
        Assert-Rejected { Ensure-BootstrapPrerequisites $false $true }
        function Get-Command { param($Name, $ErrorAction) return $null }
        Assert-Rejected { Ensure-BootstrapPrerequisites $true $true }
    }

    # Exercise orchestration without network, winget, runtime or user-data writes.
    $script:fixture = Join-Path $root 'fixture.zip'
    $manifest = @{ version='1.2.3'; revision=('a' * 40) } | ConvertTo-Json
    New-TestZip $script:fixture @{
        'release-source.json'=$manifest
        'installers/windows/install.ps1'='param($SourceRoot, [switch]$SkipBrowserLaunch) Write-Output "TEST-INSTALL-OK"'
    }
    $script:downloadRoots = @()
    function Ensure-BootstrapPrerequisites([bool]$Consent, [bool]$Quiet) { }
    function Save-ReleaseDownload([uri]$Uri, [string]$Destination, [long]$MaxBytes) {
        $script:downloadRoots += (Split-Path -Parent $Destination)
        if ($Uri.Host -eq 'api.github.com') {
            [IO.File]::WriteAllText($Destination, (@{ draft=$false; prerelease=$false; tag_name='v1.2.3'; assets=@(@{name='OpenSprite-1.2.3-windows.zip'},@{name='OpenSprite-1.2.3-windows.zip.sha256'}) } | ConvertTo-Json -Depth 4))
        } elseif ($Uri.AbsolutePath.EndsWith('.sha256')) {
            [IO.File]::WriteAllText($Destination, ((Get-FileHash $script:fixture).Hash + '  OpenSprite-1.2.3-windows.zip'))
        } else { Copy-Item -LiteralPath $script:fixture -Destination $Destination }
    }
    $Version = '1.2.3'
    $output = Invoke-OpenSpriteBootstrap
    Assert-True ($output -contains 'TEST-INSTALL-OK') 'Installer was not invoked.'
    foreach ($path in $script:downloadRoots) { Assert-True (-not (Test-Path -LiteralPath $path)) 'Download temporary root was not removed.' }
    $Version = '9.9.9'
    Assert-Rejected { Invoke-OpenSpriteBootstrap }
    foreach ($path in ($script:downloadRoots | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $path) {
            Assert-True (@(Get-ChildItem -LiteralPath $path).Count -eq 1 -and (Test-Path (Join-Path $path 'failure.txt'))) 'Failure retained more than the diagnostic stage.'
            Remove-BootstrapTemp $path
        }
    }
    $FromSource = $true
    $Version = 'latest'
    function Get-OpenSpriteSource([string]$Destination) {
        $script:downloadRoots += (Split-Path -Parent $Destination)
        Expand-ReleaseArchive $script:fixture $Destination
    }
    function Ensure-BootstrapPrerequisites([bool]$Consent, [bool]$Quiet, [bool]$IncludeGit) {
        Assert-True $IncludeGit 'Source installation must request Git.'
    }
    function Save-ReleaseDownload { throw 'Source mode must not use Release assets.' }
    $output = Invoke-OpenSpriteBootstrap
    Assert-True ($output -contains 'TEST-INSTALL-OK') 'Source installer was not invoked.'
    foreach ($path in $script:downloadRoots) { Assert-True (-not (Test-Path -LiteralPath $path)) 'Source temporary root was not removed.' }
    $Version = '1.2.3'
    Assert-Rejected { Invoke-OpenSpriteBootstrap }
    $Version = 'latest'
    function Get-OpenSpriteSource([string]$Destination) { $script:failedSourceRoot = Split-Path -Parent $Destination; throw 'Injected clone failure' }
    Assert-Rejected { Invoke-OpenSpriteBootstrap }
    Assert-True (Test-Path (Join-Path $script:failedSourceRoot 'failure.txt')) 'Missing clone failure stage report.'
    Remove-BootstrapTemp $script:failedSourceRoot
    Write-Host 'Bootstrap safety and orchestration checks passed.'
} finally { Remove-BootstrapTemp $root }
