Set-StrictMode -Version Latest

function New-LocalAccessBootstrap([string]$Root, [switch]$Reset) {
    $configRoot = Join-Path $Root "config"
    $stateRoot = Join-Path $Root "state"
    $accessPath = Join-Path $configRoot "access.json"
    $bootstrapPath = Join-Path $stateRoot "access-bootstrap.json"
    New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null

    $tokenBytes = [byte[]]::new(32)
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    $random.GetBytes($tokenBytes)
    $random.Dispose()
    $token = [Convert]::ToBase64String($tokenBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $sha256 = [Security.Cryptography.SHA256]::Create()
    $hashBytes = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($token))
    $sha256.Dispose()
    $tokenHash = ([BitConverter]::ToString($hashBytes) -replace "-", "").ToLowerInvariant()
    $createdAt = [DateTimeOffset]::UtcNow
    $record = [ordered]@{
        version = 1
        tokenHash = $tokenHash
        createdAt = $createdAt.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        expiresAt = $createdAt.AddMinutes(30).ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    } | ConvertTo-Json -Compress
    $temporaryPath = Join-Path $stateRoot (".access-bootstrap-" + [Guid]::NewGuid().ToString("N") + ".tmp")
    $backupPath = $null
    [IO.File]::WriteAllText($temporaryPath, $record, [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $bootstrapPath -PathType Leaf) {
            $backupPath = Join-Path $stateRoot (".access-bootstrap-backup-" + [Guid]::NewGuid().ToString("N") + ".tmp")
            [IO.File]::Replace($temporaryPath, $bootstrapPath, $backupPath)
        }
        else {
            [IO.File]::Move($temporaryPath, $bootstrapPath)
        }
        if ($Reset -and (Test-Path -LiteralPath $accessPath -PathType Leaf)) {
            Remove-Item -LiteralPath $accessPath -Force
        }
        return $token
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
        if ($null -ne $backupPath -and (Test-Path -LiteralPath $backupPath)) { Remove-Item -LiteralPath $backupPath -Force }
        [Array]::Clear($tokenBytes, 0, $tokenBytes.Length)
    }
}
