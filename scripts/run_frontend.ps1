. (Join-Path $PSScriptRoot "common.ps1")

$npm = Get-NpmCommand
$frontendRoot = Join-Path (Get-RepoRoot) "frontend"

Push-Location $frontendRoot
try {
    & $npm run dev
}
finally {
    Pop-Location
}
