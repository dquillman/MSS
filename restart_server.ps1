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
        Start-Sleep -Seconds 1
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
        Start-Sleep -Seconds 1
    }
}

# Determine Python Path (Use venv if available)
$VenvPython = "..\venv\Scripts\python.exe"
$GlobalPython = "python"
$PythonToUse = $GlobalPython

if (Test-Path $VenvPython) {
    $PythonToUse = $VenvPython
    Write-Host "🐍 Using Virtual Environment: $VenvPython" -ForegroundColor Green
} else {
    Write-Host "🐍 Using Global Python" -ForegroundColor Yellow
}

# Change to web directory
Set-Location web

# Start the server
Write-Host "`n🚀 Starting server..." -ForegroundColor Green
Write-Host "   URL: http://localhost:5000/studio.html" -ForegroundColor Cyan

# Launch Browser in background after a short delay
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:5000/studio.html"
} | Out-Null

# Run Python Server
& $PythonToUse api_server.py
