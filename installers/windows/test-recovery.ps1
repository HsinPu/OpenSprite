$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot "install.ps1"), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw "Installer parse failed: $errors" }
# Load only functions: never execute the installer or touch the real installation.
foreach ($name in @("Assert-ChildPath", "Get-InstallTool", "Invoke-RecoveryStep", "Restore-ApplicationRoot", "Get-PreviousStartupPort", "Stop-InstalledRuntime")) {
    $definition = $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $false) | Where-Object Name -eq $name
    . ([scriptblock]::Create($definition.Extent.Text))
}
$parent = [IO.Path]::GetFullPath((Join-Path ([IO.Path]::GetTempPath()) ("opensprite-recovery-test-" + [Guid]::NewGuid().ToString("N"))))
$temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
Assert-ChildPath $parent $temp
try {
    $root = Join-Path $parent "app"; $previous = Join-Path $parent "previous"
    New-Item -ItemType Directory -Path $root, $previous -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $previous "old.txt"), "previous")
    [IO.File]::WriteAllText((Join-Path $root "locked.txt"), "new")
    # Windows delete-sharing allows directory rename while a native file remains open.
    $handle = [IO.File]::Open((Join-Path $root "locked.txt"), 'Open', 'Read', [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
    try { $restored = Invoke-RecoveryStep "locked-root recovery" { Restore-ApplicationRoot $root $previous $parent $true } } finally { $handle.Dispose() }
    if (-not $restored) {
        if (-not (Test-Path -LiteralPath (Join-Path $previous "old.txt"))) { throw "Locked recovery lost previous app" }
        Restore-ApplicationRoot $root $previous $parent $true
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root "old.txt"))) { throw "Previous application was not restored" }
    if (@(Get-ChildItem -LiteralPath $parent -Directory -Filter '.app-failed-*').Count -ne 1) { throw "Failed app was not preserved" }
    if (Invoke-RecoveryStep "injected failure" { throw "injected" }) { throw "Failure was swallowed as success" }
    if (-not (Invoke-RecoveryStep "following step" { [IO.File]::WriteAllText((Join-Path $parent "continued"), "ok") })) { throw "Recovery did not continue" }
    $missing = $false
    try { Get-InstallTool @("opensprite-nonexistent-tool-" + [Guid]::NewGuid().ToString('N')) "test tool" | Out-Null } catch { $missing = $_.Exception.Message -like 'Missing prerequisite:*' }
    if (-not $missing) { throw "Missing tool did not fail preflight" }
    $launches = @($ast.FindAll({ param($node) $node -is [Management.Automation.Language.CommandAst] -and $node.Extent.Text.StartsWith('& (Join-Path') -and $node.Extent.Text -like '*launch.ps1*' -and $node.Extent.Text -like '*-InstallRoot*' }, $true))
    foreach ($launch in $launches) { if ($launch.Extent.Text -notlike '*-AllowCustomInstallRoot:*') { throw "Custom root authorization not forwarded" } }
    if ($launches.Count -ne 2) { throw "Expected install and rollback launch paths" }
    & {
        function Get-CimInstance { [pscustomobject]@{ CommandLine = 'C:\test\app\python.exe opensprite_backend.installed_runtime'; ProcessId = 12345 } }
        function Get-Process { [pscustomobject]@{ Id = 12345 } }
        function Stop-Process { [CmdletBinding()] param($InputObject, [switch]$Force) Write-Error 'Injected access denied' }
        if (Invoke-RecoveryStep 'injected shutdown failure' { Stop-InstalledRuntime 'C:\test\app' }) { throw 'Shutdown failure reported success' }
    }
    $guard = $ast.FindAll({ param($node) $node -is [Management.Automation.Language.IfStatementAst] -and $node.Extent.Text.StartsWith('if (-not $runtimeStopped)') }, $true)
    if (-not $guard -or $guard.Extent.Text -notlike '*throw $failure*') { throw 'Failed shutdown must abort rollback' }
    if ((Get-PreviousStartupPort 'powershell -File "C:\app\launch.ps1"') -ne 8765) { throw "Default previous port lost" }
    if ((Get-PreviousStartupPort 'powershell -File "C:\app\launch.ps1" -Port 9876') -ne 9876) { throw "Custom previous port lost" }
    if ($launches[1].Extent.Text -notlike '*-Port $previousPort *') { throw "Rollback must use previous port" }
    # Execute the real mutation statements with a helper that fails after a write.
    $source = $ast.Extent.Text
    foreach ($case in @(
        @{ Start = '$policyMutated = $true'; End = 'Set-LocalAccessPolicy $userDataRootPath $policyMode'; Flags = @('policyMutated') },
        @{ Start = '$bootstrapMutated = $true'; End = '$bootstrapToken = New-LocalAccessBootstrap $userDataRootPath -Reset:$ResetLocalAccess'; Flags = @('bootstrapMutated', 'accessMutated') }
    )) {
        $end = $source.IndexOf($case.End)
        $start = $source.LastIndexOf($case.Start, $end)
        if ($start -lt 0) { throw "Recovery flag must precede mutation" }
        & {
            $policyMutated = $false; $bootstrapMutated = $false; $accessMutated = $false
            $userDataRootPath = $parent; $policyMode = 'trusted_local'; $ResetLocalAccess = $true
            function Set-LocalAccessPolicy { throw 'injected post-write failure' }
            function New-LocalAccessBootstrap { throw 'injected post-write failure' }
            try { . ([scriptblock]::Create($source.Substring($start, $end + $case.End.Length - $start))) } catch { }
            foreach ($flag in $case.Flags) { if (-not (Get-Variable $flag -ValueOnly)) { throw "Lost recovery flag: $flag" } }
        }
    }
} finally {
    Assert-ChildPath $parent $temp
    if (Test-Path -LiteralPath $parent) { Remove-Item -LiteralPath $parent -Recurse -Force }
}
"Windows installer recovery tests passed."
