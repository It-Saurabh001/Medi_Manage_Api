# Run local debug SMTP server on localhost:1025
Write-Host "Starting local debug SMTP server on localhost:1025..." -ForegroundColor Cyan
python -m aiosmtpd -n -l localhost:1025
