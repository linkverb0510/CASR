param(
    [string]$HostAlias = "casr-cluster",
    [string]$RemoteRoot = "$env:CASR_REMOTE_ROOT",
    [int]$ConnectTimeoutSeconds = 10,
    [switch]$InstallDependencies,
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
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $logPath = Join-Path $projectRoot "logs/smoke-$timestamp.log"
    $installFlag = if ($InstallDependencies) { " --install" } else { "" }
    $command = "cd '$RemoteRoot' && bash scripts/cluster/prepare.sh --root '$RemoteRoot'$installFlag && if [ -x .venv/bin/python ]; then .venv/bin/python -m pytest -q; else python3 -m pytest -q; fi"
    $sshOptions = @(
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=$ConnectTimeoutSeconds",
        "-o", "StrictHostKeyChecking=yes"
    )

    if ($DryRun) {
        [ordered]@{
            mode = "dry-run"
            action = "smoke-test"
            host_alias = $HostAlias
            remote_root = $RemoteRoot
            install_dependencies = [bool]$InstallDependencies
            command = $command
            steps = @("ssh-prepare", "ssh-pytest", "save-log")
        } | ConvertTo-Json -Depth 5 -Compress
        exit 0
    }

    $ssh = Get-Command ssh.exe -ErrorAction Stop
    New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null
    & $ssh.Source @sshOptions $HostAlias $command 2>&1 | Tee-Object -FilePath $logPath
    $exitCode = $LASTEXITCODE

    [ordered]@{
        status = $(if ($exitCode -eq 0) { "PASS" } else { "FAIL" })
        action = "smoke-test"
        host_alias = $HostAlias
        remote_root = $RemoteRoot
        exit_code = $exitCode
        log_path = $logPath
    } | ConvertTo-Json -Compress
    exit $exitCode
}
catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
