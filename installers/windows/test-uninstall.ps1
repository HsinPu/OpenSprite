$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'uninstall.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw "Uninstaller parse failed: $errors" }
# Execute the actual process-stop pipeline with fixture commands; never uninstall here.
$pipeline = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.PipelineAst] -and $node.Extent.Text.StartsWith('Get-CimInstance Win32_Process |')
}, $true)
if ($null -eq $pipeline) { throw 'Process-stop pipeline not found' }
$stopPipeline = [scriptblock]::Create($pipeline.Extent.Text)

function Invoke-StopTest {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([string]$Case)
    $escapedRoot = [regex]::Escape('C:\fixture\OpenSprite\app')
    $script:stopCalls = @()
    function Get-CimInstance {
        @(
            [pscustomobject]@{ ProcessId=101; CommandLine='C:\fixture\OpenSprite\app\uvicorn.exe opensprite_backend.installed_runtime' },
            [pscustomobject]@{ ProcessId=102; CommandLine='C:\fixture\OpenSprite\app\python.exe opensprite_backend.installed_runtime' },
            [pscustomobject]@{ ProcessId=103; CommandLine='C:\other\python.exe opensprite_backend.installed_runtime' }
        )
    }
    function Stop-Process {
        [CmdletBinding()]
        param([int]$Id, [switch]$Force)
        $script:stopCalls += $Id
        if ($Id -eq 102 -and $Case -ne 'success') {
            $errorId = if ($Case -eq 'exited') { 'NoProcessFoundForGivenId' } else { 'CouldNotStopProcess' }
            $exception = [InvalidOperationException]::new('Injected process failure')
            $PSCmdlet.ThrowTerminatingError([Management.Automation.ErrorRecord]::new($exception, $errorId, 'InvalidOperation', $Id))
        }
    }
    . $stopPipeline
}

Invoke-StopTest success -Confirm:$false
if (($script:stopCalls -join ',') -ne '101,102') { throw 'Unexpected process targets' }
Invoke-StopTest exited -Confirm:$false
if (($script:stopCalls -join ',') -ne '101,102') { throw 'Exited child was not exercised' }
$rejected = $false
try { Invoke-StopTest denied -Confirm:$false } catch { $rejected = $_.FullyQualifiedErrorId -like 'CouldNotStopProcess,*' }
if (-not $rejected) { throw 'A real stop failure must abort uninstall' }
Invoke-StopTest success -WhatIf
if ($script:stopCalls.Count -ne 0) { throw 'WhatIf stopped a process' }
Write-Output 'Windows uninstaller process-race tests passed.'

# Run the real uninstaller against disposable files, with registry/process commands
# isolated so these checks never stop the user's application or change startup.
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$summaryRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot ('opensprite-uninstall-summary-' + [Guid]::NewGuid().ToString('N'))))
if (-not $summaryRoot.StartsWith($tempRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe summary test root.' }
try {
    & {
        $summaryFixture = @{ Startup = $false; Failure = $false }
        function Get-CimInstance { @() }
        function Stop-Process { throw 'Summary tests must not stop real processes.' }
        function Get-ItemProperty { if ($summaryFixture.Startup) { [pscustomobject]@{ OpenSprite = 'fixture' } } }
        function Remove-ItemProperty { $summaryFixture.Startup = $false }
        function Start-Sleep { }
        function Remove-Item {
            [CmdletBinding()]
            param([string]$LiteralPath, [switch]$Recurse, [switch]$Force)
            if ($summaryFixture.Failure) { throw 'Injected application cleanup failure' }
            Microsoft.PowerShell.Management\Remove-Item @PSBoundParameters
        }
        foreach ($case in @('preserve', 'purge', 'preview', 'absent', 'failure')) {
            $caseRoot = Join-Path $summaryRoot $case
            $app = Join-Path $caseRoot 'app with spaces'
            $data = Join-Path $caseRoot '.opensprite'
            $summaryFixture.Startup = $case -ne 'absent'
            $summaryFixture.Failure = $case -eq 'failure'
            if ($case -ne 'absent') {
                New-Item -ItemType Directory -Path $app, $data -Force | Out-Null
                [IO.File]::WriteAllText((Join-Path $app 'program.txt'), 'test application')
                [IO.File]::WriteAllText((Join-Path $data 'keep.txt'), 'test user data')
            }
            $parameters = @{
                InstallRoot = $app; DataRoot = $data; StartupName = 'OpenSprite-Summary-Test'
                AllowCustomInstallRoot = $true; AllowCustomDataRoot = $true; Confirm = $false
                RemoveUserData = $case -in @('purge', 'preview'); WhatIf = $case -eq 'preview'
            }
            $output = [Collections.Generic.List[object]]::new()
            $caught = $false
            try { & (Join-Path $PSScriptRoot 'uninstall.ps1') @parameters 6>&1 | ForEach-Object { $output.Add($_) } }
            catch { if ($case -ne 'failure') { throw }; $caught = $true }
            $text = ($output | ForEach-Object { $_.ToString() }) -join "`n"
            $expectedApp = switch ($case) { 'absent' { 'Already absent' }; { $_ -in @('preview', 'failure') } { 'Retained' }; default { 'Removed' } }
            $expectedData = switch ($case) { 'absent' { 'Already absent' }; 'purge' { 'Removed' }; default { 'Retained' } }
            $expectedStartup = switch ($case) { 'absent' { 'Already absent' }; 'preview' { 'Retained' }; default { 'Removed' } }
            foreach ($message in @("Application: $expectedApp -- $app", "User data: $expectedData -- $data", "Startup entry: $expectedStartup --")) {
                if (-not $text.Contains($message)) { throw "Missing $case summary: $message" }
            }
            if ((Test-Path -LiteralPath $app) -ne ($case -in @('preview', 'failure'))) { throw "Unexpected $case application state." }
            if ($expectedData -eq 'Retained' -and [IO.File]::ReadAllText((Join-Path $data 'keep.txt')) -ne 'test user data') { throw 'User data was modified.' }
            if ($expectedData -ne 'Retained' -and (Test-Path -LiteralPath $data)) { throw 'Unexpected remaining data.' }
            if ($case -eq 'failure' -and (-not $caught -or -not $text.Contains('Uninstall stopped before completion.'))) { throw 'Cleanup failure must report partial state and still fail.' }
            if ($case -eq 'preview' -and -not $text.Contains('Preview only; no changes were made.')) { throw 'Preview was not labelled.' }
            if ($case -ne 'failure') {
                $result = @($output | Where-Object { $_ -is [pscustomobject] -and $_.PSObject.Properties.Name -contains 'InstallRootRemoved' })
                if ($result.Count -ne 1) { throw 'Uninstaller must retain its structured result.' }
            }
        }
    }
} finally {
    if (Test-Path -LiteralPath $summaryRoot) {
        if (-not $summaryRoot.StartsWith($tempRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe summary cleanup.' }
        Remove-Item -LiteralPath $summaryRoot -Recurse -Force
    }
}
Write-Output 'Windows uninstaller summary tests passed (preserve, purge, preview, absent, failure).'
