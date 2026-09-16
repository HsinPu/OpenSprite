$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'bootstrap.ps1')

function Assert-Equal($Actual, $Expected) {
    if (($Actual -join ',') -ne ($Expected -join ',')) { throw "Expected $Expected; got $Actual" }
}

& {
    function Get-Command { param($Name, $ErrorAction) return $null }
    Assert-Equal @(Get-MissingPrerequisites) @('OpenJS.NodeJS.LTS', 'astral-sh.uv')
    Assert-Equal @(Get-MissingPrerequisites $true) @('OpenJS.NodeJS.LTS', 'astral-sh.uv', 'Git.Git')
}

& {
    $script:checks = 0
    $script:packages = @()
    function Get-MissingPrerequisites($IncludeGit) {
        if (-not $IncludeGit) { throw 'Git option was lost' }
        $script:checks++
        if ($script:checks -eq 1) { return @('OpenJS.NodeJS.LTS', 'astral-sh.uv', 'Git.Git') }
    }
    function Invoke-TestWinget {
        $script:packages += $args[2]
        if (($args -join ' ') -notlike '*--exact --source winget*--disable-interactivity*') { throw 'Unexpected winget arguments' }
        $global:LASTEXITCODE = 0
    }
    function Get-Command { param($Name, $ErrorAction) return @{ Source = 'Invoke-TestWinget' } }
    $savedPath = $env:PATH
    try { Ensure-BootstrapPrerequisites $true $true $true } finally { $env:PATH = $savedPath }
    Assert-Equal $script:packages @('OpenJS.NodeJS.LTS', 'astral-sh.uv', 'Git.Git')
    Assert-Equal $script:checks 2
}

& {
    function Get-MissingPrerequisites { return 'OpenJS.NodeJS.LTS' }
    function Invoke-TestWinget { $global:LASTEXITCODE = 1 }
    function Get-Command { param($Name, $ErrorAction) return @{ Source = 'Invoke-TestWinget' } }
    $rejected = $false
    try { Ensure-BootstrapPrerequisites $true $true } catch {
        $rejected = $_.Exception.Message -like 'Prerequisite installation failed:*'
    }
    if (-not $rejected) { throw 'winget failure must stop installation' }
}

& {
    function Get-MissingPrerequisites { return 'OpenJS.NodeJS.LTS' }
    function Get-Command { throw 'Noninteractive mode must not install without consent' }
    $rejected = $false
    try { Ensure-BootstrapPrerequisites $false $true } catch {
        $rejected = $_.Exception.Message -like 'Prerequisites missing.*'
    }
    if (-not $rejected) { throw 'Missing noninteractive consent guard' }
}
Write-Output 'Windows prerequisite isolation tests passed.'

# Exercise the documented entry with omitted SourceRoot. WhatIf must never run winget.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'install.ps1') -InstallPrerequisites -InstallGit -WhatIf
if ($LASTEXITCODE -ne 0) { throw 'Default source root / WhatIf check failed' }
