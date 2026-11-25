param(
    [string]$HostAlias = "casr-cluster",
    [string]$RemoteRoot = "$env:CASR_REMOTE_ROOT",
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

try {
    Assert-SafeHostAlias $HostAlias
    Assert-SafeRemoteRoot $RemoteRoot
    if ($ConnectTimeoutSeconds -lt 1 -or $ConnectTimeoutSeconds -gt 120) {
        throw "ConnectTimeoutSeconds must be between 1 and 120."
    }

    $projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
    $archivePaths = @("src", "scripts", "tests", "examples", "experiments", "pyproject.toml", "uv.lock", "README.md", ".env.example", ".gitignore")
    foreach ($item in $archivePaths) {
        if (-not (Test-Path (Join-Path $projectRoot $item))) {
            throw "Required sync item is missing: $item"
        }
    }

    $sshOptions = @(
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=$ConnectTimeoutSeconds",
        "-o", "StrictHostKeyChecking=yes"
    )
    $archiveName = ".casr-sync-" + [guid]::NewGuid().ToString("N") + ".tar.gz"
    $remoteArchive = "$RemoteRoot/$archiveName"
    $remoteCommand = "set -eu; mkdir -p '$RemoteRoot'; tar -xzf '$remoteArchive' -C '$RemoteRoot'; rm -f '$remoteArchive'"

    if ($DryRun) {
        [ordered]@{
            mode = "dry-run"
            action = "sync"
            host_alias = $HostAlias
            remote_root = $RemoteRoot
            archive_items = @(
                "src", "scripts", "tests", "examples", "experiments", "pyproject.toml", "uv.lock", "README.md", ".env.example", ".gitignore",
                "scripts/cluster/prepare.sh", "scripts/cluster/run_experiment.sh"
            )
            steps = @("create-archive", "compute-sha256", "scp", "ssh-extract")
            remote_command = $remoteCommand
        } | ConvertTo-Json -Depth 5 -Compress
        exit 0
    }

    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -eq $tar) { $tar = Get-Command tar -ErrorAction Stop }
    $scp = Get-Command scp.exe -ErrorAction Stop
    $ssh = Get-Command ssh.exe -ErrorAction Stop

    $archivePath = Join-Path ([IO.Path]::GetTempPath()) ("casr-sync-" + [guid]::NewGuid().ToString("N") + ".tar.gz")
    try {
        $tarArguments = @(
            "-czf", $archivePath, "-C", $projectRoot,
            "--exclude=__pycache__", "--exclude=*.pyc", "--exclude=.pytest_cache"
        ) + $archivePaths
        & $tar.Source @tarArguments
        if ($LASTEXITCODE -ne 0) { throw "tar failed with exit code $LASTEXITCODE." }

        $sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
        $target = "${HostAlias}:$remoteArchive"
        & $scp.Source @sshOptions $archivePath $target
        if ($LASTEXITCODE -ne 0) { throw "scp failed with exit code $LASTEXITCODE." }

        & $ssh.Source @sshOptions $HostAlias $remoteCommand
        if ($LASTEXITCODE -ne 0) { throw "ssh extraction failed with exit code $LASTEXITCODE." }

        [ordered]@{
            status = "PASS"
            action = "sync"
            host_alias = $HostAlias
            remote_root = $RemoteRoot
            sha256 = $sha256
            bytes = (Get-Item -LiteralPath $archivePath).Length
        } | ConvertTo-Json -Compress
    }
    finally {
        if (Test-Path -LiteralPath $archivePath) {
            Remove-Item -LiteralPath $archivePath -Force
        }
    }
}
catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
