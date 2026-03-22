Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

function Import-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()

        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        Set-Item -Path "Env:$name" -Value $value
    }
}

function Initialize-ProjectEnvironment {
    $repoRoot = Get-RepoRoot
    Import-DotEnv -Path (Join-Path $repoRoot ".env")
    Import-DotEnv -Path (Join-Path $repoRoot "backend\.env")
}

function Get-PythonInvocation {
    $repoRoot = Get-RepoRoot
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $candidates = @()

    if ($env:PYTHON_EXECUTABLE) {
        $candidates += @{
            Command = $env:PYTHON_EXECUTABLE
            Arguments = @()
        }
    }

    $candidates += @{
        Command = $venvPython
        Arguments = @()
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyCommand) {
        $candidates += @{
            Command = $pyCommand.Source
            Arguments = @("-3.11")
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        $candidates += @{
            Command = $pythonCommand.Source
            Arguments = @()
        }
    }

    foreach ($candidate in $candidates) {
        if (-not (Test-Path $candidate.Command) -and $candidate.Command -notmatch "python|py\.exe|py$") {
            continue
        }

        try {
            & $candidate.Command @($candidate.Arguments) --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
        catch {
            continue
        }
    }

    throw "Python executable not found or not runnable. Please install Python 3.11+ or create a working .venv."
}

function Get-NpmCommand {
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -ne $npmCommand) {
        return $npmCommand.Source
    }

    $npmFallback = Get-Command npm -ErrorAction SilentlyContinue
    if ($null -ne $npmFallback) {
        return $npmFallback.Source
    }

    throw "npm executable not found. Please install Node.js and npm."
}
