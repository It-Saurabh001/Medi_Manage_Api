# Run Flask development server
$env:FLASK_ENV = "development"
Write-Host "Starting Flask development server..." -ForegroundColor Green
python -m flask --app wsgi run --debug --host=0.0.0.0 --port=5000
