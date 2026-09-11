[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\..\dist\release')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$git = Get-Command git -ErrorAction Stop
$revision = & $git.Source -c "safe.directory=$($root.Replace('\','/'))" -C $root rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $revision -notmatch '^[a-f0-9]{40}$') { throw 'A Git checkout is required for release packaging.' }
$status = & $git.Source -c "safe.directory=$($root.Replace('\','/'))" -C $root status --porcelain
if ($LASTEXITCODE -ne 0 -or $status) { throw 'Release packaging requires a clean committed checkout.' }
$versionMatch = [regex]::Match([IO.File]::ReadAllText((Join-Path $root 'backend\pyproject.toml')), '(?m)^version = "([0-9]+\.[0-9]+\.[0-9]+)"\r?$')
if (-not $versionMatch.Success) { throw 'Invalid product version.' }
$version = $versionMatch.Groups[1].Value
$files = @(& $git.Source -c "safe.directory=$($root.Replace('\','/'))" -C $root -c core.quotepath=false ls-files -- backend/src frontend/src)
if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate release source.' }
$files += @('backend/pyproject.toml','backend/uv.lock','backend/README.md',
    'frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/tsconfig.json','frontend/vite.config.ts','frontend/README.md',
    'installers/windows/install.ps1','installers/windows/access.ps1','installers/windows/launch.ps1','installers/windows/uninstall.ps1')
$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $output -Force | Out-Null
$name = "OpenSprite-$version-windows.zip"
$archive = Join-Path $output $name
if (Test-Path -LiteralPath $archive) { throw 'Output archive already exists; choose a fresh output directory.' }
$zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in ($files | Sort-Object -Unique)) {
        if ($file -match '(^|/)(\.env|node_modules|__pycache__|\.venv)(/|$)' -or $file -match '\.(pyc|log)$') { throw 'Generated or sensitive file in release source.' }
        $path = Join-Path $root $file
        if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Release source cannot contain links.' }
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $path, $file, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
    $entry = $zip.CreateEntry('release-source.json')
    $writer = [IO.StreamWriter]::new($entry.Open(), [Text.UTF8Encoding]::new($false))
    try { $writer.Write(([ordered]@{ version=$version; revision=$revision } | ConvertTo-Json -Compress)) } finally { $writer.Dispose() }
} finally { $zip.Dispose() }
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $output "$name.sha256"), "$hash  $name`n", [Text.UTF8Encoding]::new($false))
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'bootstrap.ps1') -Destination (Join-Path $output 'OpenSprite-install.ps1')
Write-Host "Packaged $version ($revision) in $output"
