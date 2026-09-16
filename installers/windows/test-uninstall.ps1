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
