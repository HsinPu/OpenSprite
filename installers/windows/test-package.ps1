[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap.ps1')
$root = Join-Path ([IO.Path]::GetTempPath()) ('opensprite-download-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $root 'installers/windows') -Force | Out-Null
try {
    foreach ($file in @('package.ps1','bootstrap.ps1')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $root 'installers/windows') }
    $files = @('backend/src/app.py','backend/uv.lock','backend/README.md','frontend/src/app.ts',
        'frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/tsconfig.json','frontend/vite.config.ts','frontend/README.md',
        'installers/windows/install.ps1','installers/windows/access.ps1','installers/windows/launch.ps1','installers/windows/uninstall.ps1',
        'docs/not-shipped.txt','frontend/tests/not-shipped.txt')
    foreach ($file in $files) {
        $path = Join-Path $root $file
        New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
        [IO.File]::WriteAllText($path, 'fixture')
    }
    [IO.File]::WriteAllText((Join-Path $root 'backend/pyproject.toml'), 'version = "1.2.3"')
    [IO.File]::WriteAllText((Join-Path $root '.gitignore'), "dist/`n")
    & git -C $root init --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Fixture git init failed.' }
    & git -c "safe.directory=$($root.Replace('\','/'))" -C $root add .
    if ($LASTEXITCODE -ne 0) { throw 'Fixture staging failed.' }
    & git -c "safe.directory=$($root.Replace('\','/'))" -c user.name=InstallerTest -c user.email=test@example.invalid -c commit.gpgsign=false -C $root commit --quiet -m fixture
    if ($LASTEXITCODE -ne 0) { throw 'Fixture commit failed.' }
    & (Join-Path $root 'installers/windows/package.ps1')
    $archive = Join-Path $root 'dist/release/OpenSprite-1.2.3-windows.zip'
    Test-ReleaseChecksum $archive "$archive.sha256" 'OpenSprite-1.2.3-windows.zip'
    Expand-ReleaseArchive $archive (Join-Path $root 'dist/expanded')
    $manifest = Get-Content (Join-Path $root 'dist/expanded/release-source.json') -Raw | ConvertFrom-Json
    if ($manifest.version -ne '1.2.3' -or $manifest.revision -notmatch '^[a-f0-9]{40}$') { throw 'Package provenance missing.' }
    if (Test-Path (Join-Path $root 'dist/expanded/docs')) { throw 'Package included docs.' }
    if (Test-Path (Join-Path $root 'dist/expanded/frontend/tests')) { throw 'Package included tests.' }
    [IO.File]::WriteAllText((Join-Path $root 'frontend/src/app.ts'), 'dirty')
    $rejected = $false
    try { & (Join-Path $root 'installers/windows/package.ps1') -OutputDirectory (Join-Path $root 'dist/dirty') } catch { $rejected = $true }
    if (-not $rejected) { throw 'Dirty release packaging was allowed.' }
    Write-Host 'Release packaging isolation checks passed.'
} finally { Remove-BootstrapTemp $root }
