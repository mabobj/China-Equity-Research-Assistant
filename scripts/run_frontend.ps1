. (Join-Path $PSScriptRoot "common.ps1")

Initialize-ProjectEnvironment

$npm = Get-NpmCommand
$frontendRoot = Join-Path (Get-RepoRoot) "frontend"

Push-Location $frontendRoot
try {
    & $npm run dev -- --hostname 127.0.0.1
}
finally {
    Pop-Location
}
