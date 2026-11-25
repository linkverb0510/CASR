param(
    [string]$HostAlias = "casr-cluster",
    [string]$RemoteRoot = "$env:CASR_REMOTE_ROOT",
    [string]$RunId = "",
    [string]$OutputDirectory = "",
    [int]$ConnectTimeoutSeconds = 10,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Assert-SafeHostAlias([string]$Value) {
    if ($Value -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
        throw "HostAlias must contain only letters, digits, dots, underscores, or hyphens."
    }
}

function Assert-SafeRemoteRoot([string]$Value) {
    if ($Value -notmatch '^/[A-Za-z0-9._/-]+$' -or $Value -match '(^|/)\.\.(/|$)') {
        throw "RemoteRoot must be an absolute POSIX path without '..' or shell metacharacters."
    }
}

function Assert-SafeRunId([string]$Value) {
    if ($Value -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
        throw "RunId must start with a letter or digit and contain only letters, digits, dots, underscores, or hyphens."
    }
}

try {
    Assert-SafeHostAlias $HostAlias
    Assert-SafeRemoteRoot $RemoteRoot
    Assert-SafeRunId $RunId
    if ($ConnectTimeoutSeconds -lt 1 -or $ConnectTimeoutSeconds -gt 120) {
        throw "ConnectTimeoutSeconds must be between 1 and 120."
    }

    $projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
    if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
        $OutputDirectory = Join-Path $projectRoot ("results/cluster/" + (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + $RunId)
    }
    $outputPath = [IO.Path]::GetFullPath($OutputDirectory)
    $archiveName = ".casr-collect-$RunId.tar.gz"
    $remoteArchive = "$RemoteRoot/$archiveName"
    $remoteCommand = "set -eu; cd '$RemoteRoot'; items=''; [ -d 'logs/$RunId' ] && items=`"`$items logs/$RunId`"; [ -d 'results/$RunId' ] && items=`"`$items results/$RunId`"; [ -n `"`$items`" ] || { echo 'No collectible artifacts for run $RunId' >&2; exit 3; }; tar -czf '$remoteArchive' `$items; sha256sum '$remoteArchive'"
    $sshOptions = @(
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=$ConnectTimeoutSeconds",
        "-o", "StrictHostKeyChecking=yes"
    )

    if ($DryRun) {
        [ordered]@{
            mode = "dry-run"
            action = "collect"
            host_alias = $HostAlias
            remote_root = $RemoteRoot
            run_id = $RunId
            output_directory = $outputPath
            remote_command = $remoteCommand
            steps = @("ssh-create-archive", "scp-download", "verify-sha256", "extract")
        } | ConvertTo-Json -Depth 5 -Compress
        exit 0
    }

    $ssh = Get-Command ssh.exe -ErrorAction Stop
    $scp = Get-Command scp.exe -ErrorAction Stop
    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -eq $tar) { $tar = Get-Command tar -ErrorAction Stop }

    $hashOutput = (& $ssh.Source @sshOptions $HostAlias $remoteCommand 2>&1 | Out-String).Trim()
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Remote artifact collection failed with exit code ${exitCode}: $hashOutput"
    }
    $hashMatch = [regex]::Match($hashOutput, '(?m)^([0-9a-fA-F]{64})\s+')
    if (-not $hashMatch.Success) { throw "Remote SHA-256 was not returned." }
    $remoteHash = $hashMatch.Groups[1].Value.ToLowerInvariant()

    $localArchive = Join-Path ([IO.Path]::GetTempPath()) ("casr-collect-" + [guid]::NewGuid().ToString("N") + ".tar.gz")
    try {
        $target = "${HostAlias}:$remoteArchive"
        & $scp.Source @sshOptions $target $localArchive
        if ($LASTEXITCODE -ne 0) { throw "scp download failed with exit code $LASTEXITCODE." }

        $localHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $localArchive).Hash.ToLowerInvariant()
        if ($localHash -ne $remoteHash) { throw "Downloaded archive SHA-256 does not match the remote archive." }

        New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
        & $tar.Source -xzf $localArchive -C $outputPath
        if ($LASTEXITCODE -ne 0) { throw "Local archive extraction failed with exit code $LASTEXITCODE." }

        [ordered]@{
            status = "PASS"
            action = "collect"
            run_id = $RunId
            sha256 = $localHash
            output_directory = $outputPath
            remote_archive = $remoteArchive
        } | ConvertTo-Json -Compress
    }
    finally {
        if (Test-Path -LiteralPath $localArchive) {
            Remove-Item -LiteralPath $localArchive -Force
        }
    }
}
catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
