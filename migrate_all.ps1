Write-Host "Upgrading DEV database..." -ForegroundColor Cyan
$env:DATABASE_URL = "mysql+pymysql://root:0203@localhost:3306/gen_ai_fsms"
alembic upgrade head

Write-Host "Upgrading TEST database..." -ForegroundColor Cyan
$env:DATABASE_URL = "mysql+pymysql://root:0203@localhost:3306/gen_ai_fsms_test"
alembic upgrade head

Write-Host "Both databases upgraded." -ForegroundColor Green
