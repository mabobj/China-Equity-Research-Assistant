. (Join-Path $PSScriptRoot "common.ps1")

Initialize-ProjectEnvironment

$python = Get-PythonInvocation
$backendRoot = Join-Path (Get-RepoRoot) "backend"
$previousPluginAutoload = $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

Push-Location $backendRoot
try {
    if ($args.Count -gt 0) {
        & $python.Command @($python.Arguments) -m pytest @args
    }
    else {
        & $python.Command @($python.Arguments) -m pytest tests
    }
}
finally {
    if ($null -eq $previousPluginAutoload) {
        Remove-Item Env:PYTEST_DISABLE_PLUGIN_AUTOLOAD -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = $previousPluginAutoload
    }

    Pop-Location
}
