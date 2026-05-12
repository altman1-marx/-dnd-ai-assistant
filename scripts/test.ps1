$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    $env:PYTHONPATH = "src"
    python -m unittest discover -s tests
}
finally {
    Pop-Location
}

