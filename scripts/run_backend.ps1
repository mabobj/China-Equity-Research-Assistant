. (Join-Path $PSScriptRoot "common.ps1")

Initialize-ProjectEnvironment

if (-not $env:APP_HOST) {
    $env:APP_HOST = "127.0.0.1"
}

if (-not $env:APP_PORT) {
    $env:APP_PORT = "8000"
}

$python = Get-PythonInvocation
$backendRoot = Join-Path (Get-RepoRoot) "backend"

if ($env:ENABLE_LLM_DEBATE -eq "true") {
    if (-not (Test-PythonModule -PythonInvocation $python -ModuleName "openai")) {
        throw "ENABLE_LLM_DEBATE=true，但当前 Python 环境未安装 openai 包。请执行：$($python.Command) -m pip install -r backend\\requirements.txt"
    }
}

Push-Location $backendRoot
try {
    & $python.Command @($python.Arguments) -m uvicorn app.main:app --reload --host $env:APP_HOST --port $env:APP_PORT
}
finally {
    Pop-Location
}
