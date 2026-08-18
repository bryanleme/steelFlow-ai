[CmdletBinding()]
param(
    [switch]$History
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$safeRoot = $projectRoot.Replace("\", "/")
$excludedAuditPath = ":(exclude)scripts/security_audit.ps1"

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".git"))) {
    throw "The resolved project root is not a Git repository: $projectRoot"
}

Push-Location $projectRoot
try {
    $tracked = @(git -c "safe.directory=$safeRoot" ls-files)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to enumerate tracked files."
    }

    $suspiciousPaths = @(
        $tracked | Where-Object {
            $_ -ne ".env.example" -and (
                $_ -match '(^|/)(\.env($|\.)|id_(rsa|dsa|ecdsa|ed25519)$|credentials|secrets?|\.npmrc$|\.pypirc$)' -or
                $_ -match '\.(pem|key|p12|pfx|jks|keystore|kdbx|sqlite|db|duckdb)$'
            )
        }
    )

    $secretPatterns = [ordered]@{
        private_key = '-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----'
        aws_key = 'AKIA[0-9A-Z]{16}'
        github_token = 'github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}'
        openai_key = 'sk-(proj-)?[A-Za-z0-9_-]{20,}'
        slack_token = 'xox[baprs]-[A-Za-z0-9-]{10,}'
        google_key = 'AIza[0-9A-Za-z_-]{30,}'
        jwt = 'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
        credential_url = 'https?://[^/@:\s]+:[^/@\s]+@'
        generic_assignment = '(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|pwd)\s*[:=]\s*["'']?[A-Za-z0-9_/+=.-]{8,}'
    }
    $privacyPatterns = [ordered]@{
        absolute_user_path = '([A-Za-z]:[\\/](Users|Documents and Settings)[\\/]|/home/|/Users/)'
        email_in_content = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
        private_network = '(10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)'
    }

    $refs = if ($History) {
        @(git -c "safe.directory=$safeRoot" rev-list --all)
    } else {
        @("HEAD")
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to enumerate Git history."
    }

    $secretLocations = [System.Collections.Generic.HashSet[string]]::new()
    $privacyLocations = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($ref in $refs) {
        foreach ($entry in $secretPatterns.GetEnumerator()) {
            $hits = @(git -c "safe.directory=$safeRoot" grep -I -i -l -E -e $entry.Value $ref -- . $excludedAuditPath 2>$null)
            if ($LASTEXITCODE -notin @(0, 1)) {
                throw "Secret scan failed for pattern $($entry.Key)."
            }
            foreach ($path in $hits) {
                [void]$secretLocations.Add("$($entry.Key):$path")
            }
        }
        foreach ($entry in $privacyPatterns.GetEnumerator()) {
            $hits = @(git -c "safe.directory=$safeRoot" grep -I -l -E -e $entry.Value $ref -- . $excludedAuditPath 2>$null)
            if ($LASTEXITCODE -notin @(0, 1)) {
                throw "Privacy scan failed for pattern $($entry.Key)."
            }
            foreach ($path in $hits) {
                [void]$privacyLocations.Add("$($entry.Key):$path")
            }
        }
    }

    $commitEmails = @(
        git -c "safe.directory=$safeRoot" log --all --format='%ae%n%ce' |
            Sort-Object -Unique
    )
    $nonPrivateCommitEmails = @(
        $commitEmails | Where-Object { $_ -notmatch '@users\.noreply\.github\.com$' }
    )
    $remoteUrl = git -c "safe.directory=$safeRoot" remote get-url origin
    $remoteHasCredentials = $remoteUrl -match 'https?://[^/@:]+:[^/@]+@'

    $result = [ordered]@{
        status = if (
            $suspiciousPaths.Count -eq 0 -and
            $secretLocations.Count -eq 0 -and
            $privacyLocations.Count -eq 0 -and
            $nonPrivateCommitEmails.Count -eq 0 -and
            -not $remoteHasCredentials
        ) { "PASS" } else { "FAIL" }
        scope = if ($History) { "all_reachable_history" } else { "HEAD" }
        commits_scanned = $refs.Count
        tracked_files = $tracked.Count
        suspicious_paths = $suspiciousPaths.Count
        high_confidence_secret_findings = $secretLocations.Count
        privacy_content_findings = $privacyLocations.Count
        non_noreply_commit_emails = $nonPrivateCommitEmails.Count
        remote_has_embedded_credentials = [bool]$remoteHasCredentials
    }
    $result | ConvertTo-Json
    if ($result.status -ne "PASS") {
        exit 1
    }
} finally {
    Pop-Location
}
