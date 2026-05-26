function Get-DatabaseUrlFromEnvFile([string]$path) {
    $line = Get-Content $path |
        Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } |
        Select-Object -First 1

    if (-not $line) {
        throw "DATABASE_URL was not found in $path"
    }

    return (($line -replace '^\s*DATABASE_URL\s*=\s*', '').Trim().Trim('"').Trim("'"))
}

$previousDatabaseUrl = $env:DATABASE_URL

try {
    Write-Host "Upgrading DEV database..." -ForegroundColor Cyan
    $env:DATABASE_URL = Get-DatabaseUrlFromEnvFile ".env"
    alembic upgrade head

    Write-Host "Upgrading TEST database..." -ForegroundColor Cyan
    $env:DATABASE_URL = Get-DatabaseUrlFromEnvFile ".env.test"
    alembic upgrade head

    Write-Host "Both databases upgraded." -ForegroundColor Green
}
finally {
    if ($null -eq $previousDatabaseUrl) {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
    else {
        $env:DATABASE_URL = $previousDatabaseUrl
    }
}