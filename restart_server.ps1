# Restart MSS Server with Latest Code
Write-Host "🔄 Restarting MSS Server..." -ForegroundColor Cyan

# Check if server is running on port 5000
$port5000 = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($port5000) {
    Write-Host "⚠️  Server found on port 5000. Stopping..." -ForegroundColor Yellow
    $process = Get-Process -Id $port5000.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Write-Host "✅ Stopped old server process" -ForegroundColor Green
        Start-Sleep -Seconds 2
    }
}

# Check if server is running on port 8080
$port8080 = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
if ($port8080) {
    Write-Host "⚠️  Server found on port 8080. Stopping..." -ForegroundColor Yellow
    $process = Get-Process -Id $port8080.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Write-Host "✅ Stopped old server process" -ForegroundColor Green
        Start-Sleep -Seconds 2
    }
}

# Check current version
Write-Host "`n📦 Checking version..." -ForegroundColor Cyan
python -c "import sys; sys.path.insert(0, '.'); from web.api_server import APP_VERSION; print(f'Code version: {APP_VERSION}')" 2>$null

# Start server
Write-Host "`n🚀 Starting server with latest code..." -ForegroundColor Green
Write-Host "   Server will run on: http://localhost:5000" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to stop the server`n" -ForegroundColor Yellow

# Change to web directory and start
Set-Location web
python api_server.py

