param([int]$Port = 18765)

$ErrorActionPreference = 'Stop'
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskProject = 'opensprite-test-' + [guid]::NewGuid().ToString('N').Substring(0, 10)
$taskPreviousPort = $env:OPENSPRITE_PORT
$taskBase = "http://localhost:$Port"

function Invoke-Compose {
    param([string[]]$Arguments)
    & docker compose --project-directory $taskRoot -p $taskProject @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $Arguments" }
}

function Assert-Equal($Actual, $Expected, [string]$Label) {
    if ($Actual -ne $Expected) { throw "$Label expected '$Expected', received '$Actual'." }
}

function Assert-Rejected([string]$Path, [hashtable]$Headers) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$taskBase$Path" -Method Put -Headers $Headers -ContentType 'application/json' -Body '{"locale":"en","timeZone":"UTC"}' | Out-Null
        throw 'Unsafe request was accepted.'
    } catch {
        if ($null -eq $_.Exception.Response) { throw }
        Assert-Equal ([int]$_.Exception.Response.StatusCode) 400 'Unsafe request'
    }
}

try {
    $env:OPENSPRITE_PORT = "$Port"
    Invoke-Compose -Arguments @('up', '-d', '--build', '--wait', '--wait-timeout', '120')
    Assert-Equal (Invoke-RestMethod "$taskBase/healthz").status 'ok' 'Health'
    Assert-Equal (Invoke-RestMethod "$taskBase/api/auth/status").state 'trusted_local' 'Access mode'
    $taskVersion = (Select-String -Path "$taskRoot/backend/pyproject.toml" -Pattern '^version = "([^"]+)"').Matches[0].Groups[1].Value
    Assert-Equal (Invoke-RestMethod "$taskBase/api/app-info").version $taskVersion 'Product version'
    $taskIndex = Invoke-WebRequest -UseBasicParsing "$taskBase/"
    Assert-Equal $taskIndex.StatusCode 200 'Frontend'
    $taskAssets = [regex]::Matches($taskIndex.Content, '(?:src|href)="(/assets/[^\"]+)"')
    if ($taskAssets.Count -eq 0) { throw 'Frontend assets are missing.' }
    foreach ($taskAsset in $taskAssets) {
        Assert-Equal (Invoke-WebRequest -UseBasicParsing "$taskBase$($taskAsset.Groups[1].Value)").StatusCode 200 'Frontend asset'
    }
    Assert-Rejected '/api/settings/general' @{ Origin = 'https://example.com' }
    Assert-Rejected '/api/settings/general' @{}
    $taskBody = '{"locale":"en","timeZone":"Asia/Taipei"}'
    $taskSettings = Invoke-RestMethod "$taskBase/api/settings/general" -Method Put -Headers @{ Origin = $taskBase } -ContentType 'application/json' -Body $taskBody
    Assert-Equal $taskSettings.timeZone 'Asia/Taipei' 'Settings write'
    Invoke-Compose -Arguments @('exec', '-T', 'opensprite', 'python', '-c', 'import os; from opensprite_backend.app_paths import build_app_paths; p=build_app_paths(); assert os.getuid()==10001; assert str(p.home)=="/home/opensprite/.opensprite"; assert p.general_settings_file.is_file(); assert p.database_file.is_relative_to(p.home); print("Non-root user and persistent paths verified")')
    Invoke-Compose -Arguments @('up', '-d', '--force-recreate', '--wait', '--wait-timeout', '120')
    $taskPersisted = Invoke-RestMethod "$taskBase/api/settings/general"
    Assert-Equal $taskPersisted.locale 'en' 'Persisted locale'
    Assert-Equal $taskPersisted.timeZone 'Asia/Taipei' 'Persisted time zone'
    Write-Host 'Docker smoke tests passed: health, frontend/assets, API, origin protection, non-root user, data paths and container recreation.'
} finally {
    try {
        Invoke-Compose -Arguments @('down')
    } finally {
        $env:OPENSPRITE_PORT = $taskPreviousPort
        Write-Host "Test data volume retained: ${taskProject}_opensprite-data"
    }
}
