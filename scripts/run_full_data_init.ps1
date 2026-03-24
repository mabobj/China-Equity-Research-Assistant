param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

. (Join-Path $PSScriptRoot "common.ps1")

Initialize-ProjectEnvironment

$python = Get-PythonInvocation
$backendRoot = Join-Path (Get-RepoRoot) "backend"

Push-Location $backendRoot
try {
    & $python.Command @($python.Arguments) -m app.scripts.full_data_init @ScriptArgs
}
finally {
    Pop-Location
}

